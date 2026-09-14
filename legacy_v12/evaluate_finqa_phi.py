# 依賴安裝指令（建議在虛擬環境中執行）：
# pip install openai tqdm
# 選用文字指標依賴：
# pip install bert-score rouge-score moverscore

"""
FinQA 評測腳本
使用 OpenAI 相容 API 對 FinQA 金融推理資料集進行非同步並行評測。
# 測試 Qwen3-4B-AWQ
python evaluate_finqa.py \
  --data-path test.json \
  --defense-model "Qwen/Qwen3-4B-AWQ" \
  --sample-size 50 \
  --verbose


"""

import argparse
import asyncio
import json
import logging
import math
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from tqdm.asyncio import tqdm as atqdm

# ── 選用文字評測依賴（未安裝時對應指標輸出 -1）──
try:
    from bert_score import score as _bert_score_fn
    _HAS_BERT_SCORE = True
except ImportError:
    _HAS_BERT_SCORE = False

try:
    from rouge_score import rouge_scorer as _rouge_scorer_mod
    _HAS_ROUGE = True
except ImportError:
    _HAS_ROUGE = False

try:
    from moverscore_v2 import word_mover_score as _wms_fn, get_idf_dict as _get_idf_dict
    _HAS_MOVER = True
except ImportError:
    _HAS_MOVER = False

# ──────────────────────────────────────────────
# 資料結構定義
# ──────────────────────────────────────────────

@dataclass
class SampleResult:
    """單一測試樣本的完整記錄"""
    index: int
    question: str
    ground_truth: str
    raw_response: str           # rank-1 候選的完整回覆
    extracted_answer: Optional[str]  # rank-1 提取的答案
    is_correct: bool            # rank-1 是否正確（等同 Accuracy）
    parse_failed: bool          # rank-1 是否解析失敗
    error_msg: str = ""
    candidates: list = field(default_factory=list)  # 全部 top-k 候選詳情


@dataclass
class EvalReport:
    """評測總報告"""
    model: str
    base_url: str
    dataset: str
    total: int = 0
    correct: int = 0
    wrong: int = 0
    parse_failed: int = 0
    accuracy: float = 0.0
    hit_rate_at_1: float = 0.0   # Hit Rate@1（%）= Accuracy，rank-1 答對率
    hit_rate_at_k: float = 0.0   # Hit Rate@k（%），top-k 任一答對率
    mrr: float = 0.0             # Mean Reciprocal Rank（over top-k）
    ndcg_at_5: float = 0.0       # NDCG@5（%，over top-k）
    bert_score_f1: float = -1.0  # BERTScore F1（%，-1 = 未安裝）
    rouge_1_f1:    float = -1.0  # ROUGE-1 F1（%）
    rouge_2_f1:    float = -1.0  # ROUGE-2 F1（%）
    rouge_3_f1:    float = -1.0  # ROUGE-3 F1（%）
    mover_score:   float = -1.0  # MoverScore（%，-1 = 未安裝）
    vram_gb:       float = -1.0  # 顯存消耗（GB，-1 = 未量測）
    cp_value:      float = -1.0  # 綜合 CP 值 = Accuracy(%) / 顯存(GB)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    samples: list = field(default_factory=list)


# ──────────────────────────────────────────────
# 設定 logging
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 顯存量測
# ──────────────────────────────────────────────

def _get_vram_gb(gpu_index: int = 0) -> float:
    """
    以 nvidia-smi 查詢指定 GPU 的已用顯存（MB → GB）。
    在推理完成後（模型仍載入 GPU）呼叫，取得較準確的使用量快照。
    若 nvidia-smi 不可用或查詢失敗，回傳 -1.0。
    """
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                f"--id={gpu_index}",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        mb = float(out.decode().strip().splitlines()[0])
        return round(mb / 1024, 3)
    except Exception:
        return -1.0


# ──────────────────────────────────────────────
# 資料集載入
# ──────────────────────────────────────────────

def _flatten_cell(v) -> str:
    """將 table cell 值（可能是 list 或純值）轉為字串"""
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v)


def _parse_table(table) -> str:
    """
    將 FinQA 的 table 欄位轉為易讀的文字表格。
    table 可以是：
      - list of list（行×列）
      - list of str（已字串化的行）
      - str（直接使用）
    """
    if isinstance(table, str):
        return table
    if not isinstance(table, list) or not table:
        return ""
    # list of list
    if isinstance(table[0], list):
        return "\n".join(" | ".join(_flatten_cell(cell) for cell in row) for row in table)
    # list of str / mixed
    return "\n".join(_flatten_cell(row) for row in table)


def load_finqa(data_path: str, sample_size: int) -> list[dict]:
    """
    從本機 test.json 讀取 FinQA 測試集。
    支援官方格式：每筆資料包含 pre_text、table、post_text 以及
    qa.question / qa.exe_ans（或頂層 question / answer）。
    回傳標準化的 {context, question, answer} 列表。
    """
    path = Path(data_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到資料集檔案：{data_path}")

    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError("test.json 必須是 JSON Array（每個元素為一筆樣本）")

    logger.info("讀取本機資料集：%s，共 %d 筆原始資料", data_path, len(raw))

    samples = []
    skipped = 0
    for item in raw:
        qa_block = item.get("qa") or {}

        # ── context：優先使用 qa.model_input（黃金標準證據） ──
        model_input = qa_block.get("model_input")
        if model_input and isinstance(model_input, list):
            # 每個元素為 [key, text]，取 text 部分拼接
            context_parts = [
                entry[1] for entry in model_input
                if isinstance(entry, (list, tuple)) and len(entry) >= 2
            ]
            context = "\n".join(context_parts)
        else:
            # 備用：拼接 pre_text + table + post_text
            parts = []
            pre = item.get("pre_text", [])
            parts.append(" ".join(pre) if isinstance(pre, list) else str(pre))
            table = item.get("table")
            if table:
                parts.append(_parse_table(table))
            post = item.get("post_text", [])
            parts.append(" ".join(post) if isinstance(post, list) else str(post))
            context = "\n".join(p for p in parts if p.strip())

        # ── question：優先頂層，否則從 qa 字典取 ──
        question = (
            item.get("question")
            or qa_block.get("question")
            or ""
        )
        question = str(question).strip()

        # ── answer (ground truth)：exe_ans 為計算結果，優先使用 ──
        answer = (
            qa_block.get("exe_ans")        # 官方格式：數值計算結果
            or qa_block.get("answer")      # 備用文字答案
            or item.get("answer")          # 部分版本放頂層
            or item.get("exe_ans")
        )
        # exe_ans 可能是 float/int，統一轉 str
        answer = str(answer).strip() if answer is not None else ""

        if not question or not answer:
            skipped += 1
            continue

        samples.append({
            "context":  context,
            "question": question,
            "answer":   answer,
        })

    logger.info("有效樣本：%d 筆，跳過（缺問題或答案）：%d 筆", len(samples), skipped)

    # 控制樣本數量
    if sample_size != -1:
        samples = samples[:sample_size]

    logger.info("實際評測樣本數：%d", len(samples))
    return samples


# ──────────────────────────────────────────────
# 提示詞構建（CoT 強制引導版）
# ──────────────────────────────────────────────

# 系統提示：定義角色與輸出規範，使用英文以配合 FinQA 英文資料集
SYSTEM_PROMPT = (
    "You are an expert financial analyst. "
    "You carefully read financial statements and data tables, "
    "then perform precise step-by-step numerical calculations. "
    "Always reason through the problem before stating your final answer."
)


def build_prompt(context: str, question: str) -> str:
    return (
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Instructions:\n"
        "1. In the \"thought\" field, briefly work through the calculation step by step.\n"
        "2. In the \"answer\" field, write ONLY the final text value.\n"
        "   - Numeric: a plain number string with no units or symbols.\n"
        "   - Yes/No: exactly \"yes\" or \"no\" (lowercase).\n"
        "Strictly output valid JSON object matching schema: {\"thought\": \"string\", \"answer\": \"string\"}."
    )


# ──────────────────────────────────────────────
# 答案提取（三層防禦機制）
# ──────────────────────────────────────────────

# 匹配 \boxed{...} 整體，內容可含任意非 } 字元
_BOXED_PATTERN = re.compile(r"\\boxed\{([^}]*)\}")

# 從任意文字中提取「數字 + 可選百分號」
# 支援：負號、千分位逗號、小數點、結尾百分號
# 例：-1,234.56%  →  完整匹配
_NUM_IN_TEXT = re.compile(r"-?[\d,]+(?:\.\d+)?%?")

# 是非題關鍵字（不區分大小寫）
_YES_NO = {"yes", "no"}

# 在任意行內偵測 yes/no 單詞（詞邊界匹配，避免誤抓 "yesterday" 等）
_YES_NO_IN_LINE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)

# 百分比語境關鍵字：用於語意智慧捕獲，偵測模型回覆末尾是否暗示答案為百分比
_PERCENT_CONTEXT = re.compile(r"%|percent(?:age)?", re.IGNORECASE)


# 激進清洗：去除 boxed 內所有非數字字元，只保留數字、小數點、負號、百分號
# 用於處理 \boxed{31.32 million}、\boxed{$8.61}、\boxed{8.61\%} 等髒輸出
_STRIP_UNITS = re.compile(r"[^\d.\-%]")

# 最終答案行偵測：含「答案」「final」「therefore」等提示詞的非空行
_ANSWER_LINE_HINT = re.compile(
    r"(final\s*answer|therefore|答案|∴|=\s*-?[\d,]+(?:\.\d+)?%?)",
    re.IGNORECASE,
)


def _clean_boxed_content(raw: str) -> str:
    """
    激進清洗 boxed 內容，只保留有效數值字元。
    處理順序：
      1. LaTeX \\% → %（保留百分號語意）
      2. 移除所有空白
      3. 去除非數值字元（字母單位、貨幣符號等）
      4. 整理多餘的小數點與孤立負號
    範例：
      "31.32 million" → "31.32"
      "$8.61"         → "8.61"
      "8.61\\%"       → "8.61%"
      "-0.2243"       → "-0.2243"  （正確保留）
    """
    s = raw.replace("\\%", "%").replace(" ", "").strip()
    # 若整體是 yes/no，跳過數值清洗
    if s.lower() in _YES_NO:
        return s
    # 激進去除非數值字元，保留 - . % 與數字
    s = _STRIP_UNITS.sub("", s)
    # 去除孤立符號（如僅剩 "-" 或 "."）
    if re.fullmatch(r"[-%.]*", s):
        return ""
    return s


def extract_answer(text: str) -> Optional[str]:
    """
    三層防禦機制，從模型回覆中提取答案字串（數值或 yes/no）。

    第一層：\\boxed{} 標準 LaTeX 匹配（激進清洗版）
      - 取最後一個 \\boxed{} 的內容
      - 若內容為 yes/no → 直接回傳
      - 否則經 _clean_boxed_content 激進去除單位後，提取首個數值（含可選 %）
        例：\\boxed{31.32 million} → "31.32"
            \\boxed{$8.61}        → "8.61"
            \\boxed{8.61\\%}      → "8.61%"（normalize_number 轉為 0.0861）

    第二層：智慧末行兜底（僅在第一層完全失敗時啟用）
      - 優先掃描含「final answer」「答案」「therefore」「=」等提示詞的行
      - 若無提示詞行，回退至最後 3 行非空行
      - 每行先嘗試識別 yes/no，再提取最後一個（最終）數值

    第三層：百分比自動換算（在 normalize_number 中執行）
      - 提取到的 "8.61%" → normalize_number → 0.0861 再與 GT 比對
    """
    # ── 第一層：\boxed{} 匹配 ──
    matches = _BOXED_PATTERN.findall(text)
    if matches:
        raw = _clean_boxed_content(matches[-1])

        # 是非題：直接回傳小寫關鍵字
        if raw.lower() in _YES_NO:
            return raw.lower()

        # 數值題：從清洗後字串提取首個有效數字（含可選 %）
        if raw:
            nums = _NUM_IN_TEXT.findall(raw)
            if nums:
                return nums[0]
        # boxed 存在但清洗後無法解析（如 \boxed{N/A}），繼續向下

    # ── 第二層：智慧末行兜底 ──
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    # 優先搜尋含答案提示詞的行（從後往前，取最近的）
    hint_candidates = [ln for ln in lines if _ANSWER_LINE_HINT.search(ln)]
    scan_lines = hint_candidates[-3:] if hint_candidates else lines[-3:]

    for line in reversed(scan_lines):
        # 先嘗試 yes/no（詞邊界匹配，覆蓋「最終判斷是 yes」等混合句）
        yn_match = _YES_NO_IN_LINE.search(line)
        if yn_match:
            return yn_match.group(1).lower()
        # 再嘗試數字：取行內最後一個數值（通常是「= 0.2243」的結果）
        nums = _NUM_IN_TEXT.findall(line)
        if nums:
            return nums[-1]

    return None


def extract_answer_from_json(text: str) -> Optional[str]:
    """
    從 vLLM guided_json 回覆中提取 answer 欄位。

    流程：
      1. JSON 解析 → 取 answer 欄位
      2. 正規表達式備援（JSON 略有截斷時）
      3. 回退至原始 extract_answer（\\boxed{} 兜底）

    回傳已清理的答案字串，或 None（三層全失敗）。
    """
    stripped = text.strip()
    # ── 第一層：標準 JSON 解析 ──
    try:
        obj = json.loads(stripped)
        ans = obj.get("answer")
        if ans is not None:
            return str(ans).strip() or None
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    # ── 第二層：正規表達式擷取 "answer": "..." ──
    m = re.search(r'"answer"\s*:\s*"([^"]*)"', stripped)
    if m:
        val = m.group(1).strip()
        if val:
            return val

    # ── 第三層：回退至 \\boxed{} 三層防禦機制 ──
    return extract_answer(stripped)


def normalize_number(s: str) -> Optional[float]:
    if s is None:
        return None
    
    # 清洗 LaTeX 符號與千分位
    s = s.replace("\\%", "%").replace(" ", "").strip().replace(",", "")
    
    # ── 🎯 新增：算式自動計算防禦層 ──
    # 如果裡面包含加減乘除符號（如 6.3/18.1*100），且不是純數字
    if any(op in s for op in ['+', '-', '*', '/']) and not re.fullmatch(r"^-?[\d.]+$", s):
        try:
            # 安全地用 eval 計算數學式結果
            # 處理可能帶有 % 的結尾
            is_percent = s.endswith("%")
            calc_str = s.rstrip("%")
            # 限制只允許數字與運算子，防止安全漏洞
            if re.fullmatch(r"[\d.+\-*/()]+", calc_str):
                val = float(eval(calc_str))
                if is_percent:
                    val /= 100.0
                return val
        except Exception:
            pass

    is_percent = s.endswith("%")
    s = s.rstrip("%")
    try:
        val = float(s)
        if is_percent:
            val /= 100.0
        return val
    except (ValueError, TypeError):
        return None





# ──────────────────────────────────────────────
# 排序評測指標
# ──────────────────────────────────────────────

def compute_ranking_metrics(
    samples: list[dict],
    k: int = 5,
) -> dict[str, float]:
    """
    計算 Hit Rate@1、Hit Rate@k、MRR、NDCG@k 四項 IR 排序指標。

    每題包含 k 個候選（儲存於 sample["candidates"]），依 API 回傳順序排列為
    rank-1 … rank-k。相關性為二元（答對=1，否則=0）；最多 1 個相關文件。

      Hit Rate@1 ：rank-1 是否答對（= Accuracy）
      Hit Rate@k ：top-k 任一候選是否答對（oracle recall）
      MRR        ：∑ 1/rank_first_correct / N
      NDCG@k     ：∑ DCG@k / IDCG@k / N
                   DCG@k  = 1/log₂(rank_first_correct + 1)  若 top-k 有正確候選
                          = 0                                 若 top-k 全錯
                   IDCG@k = 1/log₂(2) = 1.0  （唯一相關文件位於 rank-1 的完美分數）
                   ※ 每題至多 1 個相關文件，故 DCG 只計第一個答對的 rank，
                     不累加後續答對候選，確保 NDCG ∈ [0, 100%]

    Args:
        samples : asdict(SampleResult) 的列表，每筆含 "candidates" 欄位
        k       : 截斷值，預設 5

    Returns:
        {
            "hit_rate_at_1"  : float（%）,
            f"hit_rate_at_{k}": float（%）,
            "mrr"            : float（0–1）,
            f"ndcg_at_{k}"   : float（%）,
        }
    """
    n = len(samples)
    if n == 0:
        return {
            "hit_rate_at_1":     0.0,
            f"hit_rate_at_{k}":  0.0,
            "mrr":               0.0,
            f"ndcg_at_{k}":      0.0,
        }

    hit1_sum  = 0
    hitk_sum  = 0
    rr_sum    = 0.0
    ndcg_sum  = 0.0
    idcg      = 1.0 / math.log2(2)   # 唯一相關文件位於 rank-1 的理想 DCG

    for r in samples:
        candidates = r.get("candidates") or []
        if not candidates:
            # 兼容舊格式（無 candidates 欄位）
            candidates = [{"rank": 1, "is_correct": r["is_correct"]}]

        cands_k = candidates[:k]

        # ── Hit Rate@1 ──
        if cands_k and cands_k[0]["is_correct"]:
            hit1_sum += 1

        # ── Hit Rate@k & MRR ──
        first_correct_rank = None
        for cand in cands_k:
            if cand["is_correct"]:
                first_correct_rank = cand["rank"]
                break

        if first_correct_rank is not None:
            hitk_sum += 1
            rr_sum   += 1.0 / first_correct_rank

        # ── NDCG@k ──
        # 每題至多 1 個相關文件：DCG = 1/log₂(rank_first_correct + 1)
        # IDCG = 1/log₂(2) = 1.0，故 NDCG = DCG / 1.0 = DCG
        if first_correct_rank is not None:
            dcg = 1.0 / math.log2(first_correct_rank + 1)
        else:
            dcg = 0.0
        ndcg_sum += dcg / idcg   # idcg = 1.0，保留除法便於日後調整

    return {
        "hit_rate_at_1":     round(hit1_sum  / n * 100, 4),
        f"hit_rate_at_{k}":  round(hitk_sum  / n * 100, 4),
        "mrr":               round(rr_sum    / n,       6),
        f"ndcg_at_{k}":      round(ndcg_sum  / n * 100, 4),
    }


# ──────────────────────────────────────────────
# 文字相似度評測指標（BERTScore / ROUGE / MoverScore）
# ──────────────────────────────────────────────

def compute_text_metrics(
    predictions: list[str],
    references: list[str],
) -> dict[str, float]:
    """
    對 predictions（rank-1 提取答案或原始回覆）與 references（GT 字串）
    計算 BERTScore、ROUGE-1/2/3、MoverScore。

    未安裝對應套件時對應指標回傳 -1.0。
    所有比例指標均以百分比（0–100）回傳。

    安裝指令：
        pip install bert-score rouge-score moverscore
    """
    results: dict[str, float] = {}

    # ── ROUGE-1 / ROUGE-2 / ROUGE-3 ──
    if _HAS_ROUGE:
        scorer = _rouge_scorer_mod.RougeScorer(
            ["rouge1", "rouge2", "rouge3"], use_stemmer=True
        )
        r1, r2, r3 = [], [], []
        for pred, ref in zip(predictions, references):
            s = scorer.score(ref, pred)
            r1.append(s["rouge1"].fmeasure)
            r2.append(s["rouge2"].fmeasure)
            r3.append(s["rouge3"].fmeasure)
        results["rouge_1_f1"] = round(sum(r1) / len(r1) * 100, 4) if r1 else -1.0
        results["rouge_2_f1"] = round(sum(r2) / len(r2) * 100, 4) if r2 else -1.0
        results["rouge_3_f1"] = round(sum(r3) / len(r3) * 100, 4) if r3 else -1.0
    else:
        logger.warning("rouge-score 未安裝，ROUGE 指標跳過（pip install rouge-score）")
        results["rouge_1_f1"] = results["rouge_2_f1"] = results["rouge_3_f1"] = -1.0

    # ── BERTScore ──
    if _HAS_BERT_SCORE:
        logger.info("計算 BERTScore（首次執行將下載 BERT 模型）…")
        _, _, F1 = _bert_score_fn(
            predictions, references,
            lang="en",
            model_type="bert-base-uncased",  # 輕量模型；換 roberta-large 可提高精度
            verbose=False,
            device="cpu"
        )
        results["bert_score_f1"] = round(float(F1.mean()) * 100, 4)
    else:
        logger.warning("bert-score 未安裝，BERTScore 跳過（pip install bert-score）")
        results["bert_score_f1"] = -1.0

    # ── MoverScore ──
    if _HAS_MOVER:
        logger.info("計算 MoverScore…")
        idf_refs  = _get_idf_dict(references)
        idf_preds = _get_idf_dict(predictions)
        scores = _wms_fn(
            references, predictions,
            idf_refs, idf_preds,
            stop_words=[],
            n_gram=1,
            remove_subwords=True,
        )
        results["mover_score"] = round(sum(scores) / len(scores) * 100, 4)
    else:
        logger.warning("moverscore 未安裝，MoverScore 跳過（pip install moverscore）")
        results["mover_score"] = -1.0

    return results


# ──────────────────────────────────────────────
# 非同步 API 呼叫
# ──────────────────────────────────────────────

# vLLM guided_json Schema：強制模型輸出此結構，杜絕格式解析失敗
_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "Step-by-step reasoning and calculation process",
        },
        "answer": {
            "type": "string",
            "description": (
                "Final answer only: a plain decimal number (percentages divided by 100, "
                "e.g. 8.61% → \"0.0861\") or \"yes\"/\"no\". No units, no symbols."
            ),
        },
    },
    "required": ["thought", "answer"],
    "additionalProperties": False,
}


async def query_model(  # vLLM 後端專用
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    model: str,
    context: str,
    question: str,
    index: int,
    pbar: atqdm,
    top_k: int = 5,
) -> list[tuple[str, str]]:
    """
    非同步呼叫 Chat Completions API（vLLM 後端）。
    以 response_format=json_object 要求合法 JSON 輸出，
    結構約束（{thought, answer} 欄位名）完全依賴 build_prompt 中的文字 schema，
    不使用 extra_body guided_json（避免新版 vLLM 噴出 ignored 警告）。
    temperature=0.0 確保數學計算的確定性。
    回傳 list[(raw_response_text, error_msg)]，長度 = top_k。
    """
    prompt = build_prompt(context, question)
    async with sem:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.0,
                max_tokens=512,
                n=top_k,
                timeout=600.0,
                response_format={"type": "json_object"},
            )
            return [(choice.message.content or "", "") for choice in response.choices]
        except Exception as e:
            err = f"API 呼叫失敗 (index={index})：{type(e).__name__}: {e}"
            logger.warning(err)
            return [("", err)] * top_k
        finally:
            pbar.update(1)


async def query_model_ollama(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    model: str,
    context: str,
    question: str,
    index: int,
    pbar: atqdm,
    top_k: int = 5,
) -> list[tuple[str, str]]:
    """
    專為 Ollama 後端設計的防超時、防斷線非同步呼叫工具（帶自動重試機制）。
    """
    prompt = build_prompt(context, question)
    target_temp = 0.6 if top_k > 1 else 0.2
    max_retries = 3  # 遇到空回覆或斷線時，最多重試 3 次
    
    async with sem:
        results = []
        for _ in range(top_k):
            success = False
            for attempt in range(max_retries):
                try:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user",   "content": prompt},
                        ],
                        temperature=target_temp, 
                        max_tokens=2048,     
                        n=1,
                        timeout=600.0,
                        response_format={"type": "json_object"}
                    )
                    
                    content = response.choices[0].message.content or "" if response.choices else ""
                    
                    # 🔍 核心防禦：如果拿到了空回覆，主動視為失敗並觸發重試！
                    if not content.strip() or content == "...(空回覆)":
                        raise ValueError("Ollama 回傳了空字串，可能遭遇排隊超時。")
                    
                    results.append((content, ""))
                    success = True
                    break  # 成功拿到資料，跳出重試迴圈
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        err = f"Ollama 呼叫徹底失敗 (index={index})：{type(e).__name__}: {e}"
                        logger.warning(err)
                        results.append(("", err))
                    else:
                        # 稍微冷卻 2 秒後重新排隊
                        await asyncio.sleep(2.0)
            
            if not success and len(results) < top_k:
                results.append(("", "重試耗盡仍無回覆"))
                
        pbar.update(1)
        return results
# ──────────────────────────────────────────────
# 評測主流程
# ──────────────────────────────────────────────

async def run_evaluation(args: argparse.Namespace) -> EvalReport:
    """主評測流程：載入資料 → 並行推理 → 評分 → 輸出報告"""

    # 1. 載入資料集
    samples = load_finqa(args.data_path, args.sample_size)
    total = len(samples)

    # 2. 初始化 OpenAI 相容客戶端
    client = AsyncOpenAI(
        base_url=args.defense_base_url,
        api_key=args.api_key,
    )

    # 3. 建立信號量（限制最大並行請求數）
    sem = asyncio.Semaphore(args.concurrency)

    report = EvalReport(
        model=args.defense_model,
        base_url=args.defense_base_url,
        dataset="FinQA",
        total=total,
    )

    # 4. 動態路由：依 base_url 中的埠號自動選擇推理後端
    #    port 8000 → vLLM（高並發 + guided_json 強制 JSON schema）
    #    其他（11434 等）→ Ollama（應用層重試，防空回覆）
    top_k = args.top_k
    use_vllm = "8000" in args.defense_base_url
    if use_vllm:
        backend_fn = query_model
        logger.info(
            "後端路由 → vLLM（guided_json 模式）：模型=%s，樣本數=%d，並行度=%d",
            args.defense_model, total, args.concurrency,
        )
    else:
        backend_fn = query_model_ollama
        logger.info(
            "後端路由 → Ollama（重試模式）：模型=%s，樣本數=%d，並行度=%d",
            args.defense_model, total, args.concurrency,
        )

    with atqdm(total=total, desc="評測進度", unit="sample") as pbar:
        tasks = [
            backend_fn(
                client=client,
                sem=sem,
                model=args.defense_model,
                context=s["context"],
                question=s["question"],
                index=i,
                pbar=pbar,
                top_k=top_k,
            )
            for i, s in enumerate(samples)
        ]
        # gather 收集所有結果（不中斷，失敗的回傳空字串列表）
        # raw_results: list[list[tuple[str, str]]]
        raw_results = await asyncio.gather(*tasks)

    # 4.5 量測顯存（模型仍在 GPU 上，此時快照最具代表性）
    if hasattr(args, "vram_gb") and args.vram_gb is not None:
        report.vram_gb = float(args.vram_gb)
        logger.info("顯存消耗（手動指定）：%.3f GB", report.vram_gb)
    else:
        report.vram_gb = _get_vram_gb()
        if report.vram_gb > 0:
            logger.info("顯存消耗（nvidia-smi 快照）：%.3f GB", report.vram_gb)
        else:
            logger.warning("nvidia-smi 不可用，顯存未量測；可用 --vram-gb 手動指定")

    # 5. 評分
    for i, candidates_raw in enumerate(raw_results):
        sample = samples[i]

        # 逐候選提取答案並判斷正確性（JSON 優先，fallback 至 \boxed{} 三層機制）
        candidate_details: list[dict] = []
        for rank, (raw_text, err_msg) in enumerate(candidates_raw, start=1):
            ext = extract_answer_from_json(raw_text)
            ok, fail = is_correct(ext, sample["answer"], raw_text)
            if err_msg:
                ok, fail = False, True
            candidate_details.append({
                "rank":             rank,
                "raw_response":     raw_text,
                "extracted_answer": ext,
                "is_correct":       ok,
                "parse_failed":     fail,
                "error_msg":        err_msg,
            })

        # rank-1 為主要評測基準
        r1 = candidate_details[0]
        correct, failed = r1["is_correct"], r1["parse_failed"]

        result = SampleResult(
            index=i,
            question=sample["question"],
            ground_truth=sample["answer"],
            raw_response=r1["raw_response"],
            extracted_answer=r1["extracted_answer"],
            is_correct=correct,
            parse_failed=failed,
            error_msg=r1["error_msg"],
            candidates=candidate_details,
        )

        report.samples.append(asdict(result))

        if correct:
            report.correct += 1
            status = "✓ Correct"
        elif failed:
            report.parse_failed += 1
            status = "? ParseFail"
            reply_tail = r1["raw_response"][-120:].replace("\n", " ").strip() if r1["raw_response"] else "(空回覆)"
            logger.warning(
                "[解析失敗] 預期: %s | 模型輸出末尾: ...%s",
                sample["answer"], reply_tail,
            )
        else:
            report.wrong += 1
            status = "✗ Wrong"
            reply_tail = r1["raw_response"][-120:].replace("\n", " ").strip() if r1["raw_response"] else "(空回覆)"
            logger.warning(
                "[錯誤] 預期: %s | 提取答案: %s | 模型輸出末尾: ...%s",
                sample["answer"], r1["extracted_answer"], reply_tail,
            )

        logger.debug(
            "Sample %d/%d [%s] | GT: %s | Rank-1 Pred: %s",
            i + 1, total, status, sample["answer"], r1["extracted_answer"],
        )

    report.accuracy = report.correct / total * 100 if total > 0 else 0.0

    # 6. 計算排序指標（真正的 top-k 多候選）
    rank_metrics = compute_ranking_metrics(report.samples, k=top_k)
    report.hit_rate_at_1 = rank_metrics["hit_rate_at_1"]
    report.hit_rate_at_k = rank_metrics.get(f"hit_rate_at_{top_k}", report.hit_rate_at_1)
    report.mrr           = rank_metrics["mrr"]
    report.ndcg_at_5     = rank_metrics.get(f"ndcg_at_{top_k}", 0.0)

    # 7. 計算文字相似度指標（以 rank-1 提取答案 vs GT 字串）
    preds_text = [
        (s["extracted_answer"] or "") for s in report.samples
    ]
    refs_text = [s["ground_truth"] for s in report.samples]
    text_metrics = compute_text_metrics(preds_text, refs_text)
    report.bert_score_f1 = text_metrics["bert_score_f1"]
    report.rouge_1_f1    = text_metrics["rouge_1_f1"]
    report.rouge_2_f1    = text_metrics["rouge_2_f1"]
    report.rouge_3_f1    = text_metrics["rouge_3_f1"]
    report.mover_score   = text_metrics["mover_score"]

    # 8. 綜合 CP 值
    if report.vram_gb > 0:
        report.cp_value = round(report.accuracy / report.vram_gb, 4)
    # else: cp_value 維持 -1.0（無法計算）

    return report


# ──────────────────────────────────────────────
# 輸出報告
# ──────────────────────────────────────────────

def print_report(report: EvalReport, top_k: int = 5) -> None:
    """在終端機列印易讀的評測摘要"""
    sep = "=" * 55

    def _fmt(v: float, pct: bool = True) -> str:
        return f"{v:.2f}%" if pct else f"{v:.4f}"

    def _na(v: float, pct: bool = True) -> str:
        return "N/A（未安裝）" if v < 0 else _fmt(v, pct)

    print(f"\n{sep}")
    print("          FinQA 評測結果報告")
    print(sep)
    print(f"  模型         : {report.model}")
    print(f"  API 端點     : {report.base_url}")
    print(f"  測試時間     : {report.timestamp}")
    print(sep)
    print(f"  總測試數     : {report.total}")
    print(f"  正確數       : {report.correct}")
    print(f"  錯誤數       : {report.wrong}")
    print(f"  解析失敗數   : {report.parse_failed}")
    print(sep)
    print(f"  Accuracy     : {report.accuracy:.2f}%")
    print(sep)
    print(f"  ── 排序評測指標（Top-{top_k} 候選）──")
    print(f"  Hit Rate@1   : {report.hit_rate_at_1:.2f}%   （rank-1 答對率 = Accuracy）")
    print(f"  Hit Rate@{top_k}  : {report.hit_rate_at_k:.2f}%   （top-{top_k} 任一答對率）")
    print(f"  MRR          : {report.mrr:.4f}")
    print(f"  NDCG@{top_k}      : {report.ndcg_at_5:.2f}%")
    print(sep)
    print("  ── 文字相似度指標（rank-1 vs GT）──")
    print(f"  ROUGE-1 F1   : {_na(report.rouge_1_f1)}")
    print(f"  ROUGE-2 F1   : {_na(report.rouge_2_f1)}")
    print(f"  ROUGE-3 F1   : {_na(report.rouge_3_f1)}")
    print(f"  BERTScore F1 : {_na(report.bert_score_f1)}")
    print(f"  MoverScore   : {_na(report.mover_score)}")
    print(sep)
    print("  ── 綜合效率指標 ──")
    if report.vram_gb > 0:
        print(f"  顯存消耗     : {report.vram_gb:.3f} GB")
        print(f"  CP 值        : {report.cp_value:.4f}   （Accuracy% / 顯存GB）")
    else:
        print("  顯存消耗     : N/A（請加 --vram-gb 指定）")
        print("  CP 值        : N/A")
    print(f"{sep}\n")


def save_results(report: EvalReport, output_path: str) -> None:
    """將完整評測結果（含所有樣本詳情）儲存為 JSON"""
    data = {
        "summary": {
            "model":          report.model,
            "base_url":       report.base_url,
            "dataset":        report.dataset,
            "timestamp":      report.timestamp,
            "total":          report.total,
            "correct":        report.correct,
            "wrong":          report.wrong,
            "parse_failed":   report.parse_failed,
            "accuracy_pct":   round(report.accuracy, 4),
            # 排序指標
            "hit_rate_at_1":  round(report.hit_rate_at_1, 4),
            "hit_rate_at_k":  round(report.hit_rate_at_k, 4),
            "mrr":            round(report.mrr, 6),
            "ndcg_at_5":      round(report.ndcg_at_5, 4),
            # 文字相似度指標（-1 = 未安裝對應套件）
            "bert_score_f1":  round(report.bert_score_f1, 4),
            "rouge_1_f1":     round(report.rouge_1_f1, 4),
            "rouge_2_f1":     round(report.rouge_2_f1, 4),
            "rouge_3_f1":     round(report.rouge_3_f1, 4),
            "mover_score":    round(report.mover_score, 4),
            # 效率指標
            "vram_gb":        report.vram_gb,
            "cp_value":       report.cp_value,
        },
        "samples": report.samples,
    }
    Path(output_path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("詳細結果已儲存至：%s", output_path)


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FinQA 金融推理資料集 LLM 評測工具",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-path",
        default="test.json",
        help="本機 FinQA test.json 檔案路徑",
    )
    parser.add_argument(
        "--defense-model",
        default="Qwen/Qwen3-8B-AWQ",
        help="要測試的模型名稱",
    )
    parser.add_argument(
        "--defense-base-url",
        default="http://127.0.0.1:8000/v1",
        help="OpenAI 相容 API 伺服器端點",
    )
    parser.add_argument(
        "--api-key",
        default="fake-key-for-local",
        help="API 金鑰（本地伺服器可填任意值）",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=50,
        help="測試樣本數；-1 表示全部",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="最大並行 API 請求數（避免衝垮本地伺服器）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="每題生成的候選答案數（n=top_k）；>1 時自動升溫至 0.6 以產生多樣候選",
    )
    parser.add_argument(
        "--output",
        default="results.json",
        help="詳細結果輸出路徑",
    )
    parser.add_argument(
        "--vram-gb",
        type=float,
        default=None,
        help=(
            "模型推理時的顯存消耗（GB），用於計算 CP 值。"
            "未指定時自動以 nvidia-smi 快照量測。"
            "範例：Qwen3-4B-AWQ 約 3.5，Qwen3-8B-AWQ 約 6.2"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="顯示每筆樣本的偵錯資訊",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 執行非同步評測主流程
    try:
        report = asyncio.run(run_evaluation(args))
    except KeyboardInterrupt:
        logger.info("使用者中斷評測。")
        sys.exit(0)
    except Exception as e:
        logger.error("評測過程發生未預期錯誤：%s", e, exc_info=True)
        sys.exit(1)

    # 列印報告並儲存結果
    print_report(report, top_k=args.top_k)
    save_results(report, args.output)


if __name__ == "__main__":
    main()
