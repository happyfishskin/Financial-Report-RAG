# 依賴安裝：
# pip install openai tqdm
# 選用文字指標：pip install bert-score rouge-score moverscore

"""
FinQA 評測腳本 — Google Gemini 版
透過 Google 的 OpenAI 相容端點呼叫 Gemini 模型。

# 設定 API Key（選擇其一）：
#   export GOOGLE_API_KEY="你的金鑰"
#   或在執行時加上 --api-key "你的金鑰"

# 執行範例：
python evaluate_finqa_google.py \\
  --data-path test.json \\
  --model "gemini-2.0-flash" \\
  --sample-size 50 \\
  --verbose
"""

import argparse
import asyncio
import json
import logging
import math
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from tqdm.asyncio import tqdm as atqdm

# ── 選用文字評測依賴 ──────────────────────────────────
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
    index: int
    question: str
    ground_truth: str
    raw_response: str
    extracted_answer: Optional[str]
    is_correct: bool
    parse_failed: bool
    error_msg: str = ""
    candidates: list = field(default_factory=list)


@dataclass
class EvalReport:
    model: str
    base_url: str
    dataset: str
    total: int = 0
    correct: int = 0
    wrong: int = 0
    parse_failed: int = 0
    accuracy: float = 0.0
    hit_rate_at_1: float = 0.0
    hit_rate_at_k: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    bert_score_f1: float = -1.0
    rouge_1_f1:    float = -1.0
    rouge_2_f1:    float = -1.0
    rouge_3_f1:    float = -1.0
    mover_score:   float = -1.0
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
# 資料集載入
# ──────────────────────────────────────────────

def _flatten_cell(v) -> str:
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return str(v)


def _parse_table(table) -> str:
    if isinstance(table, str):
        return table
    if not isinstance(table, list) or not table:
        return ""
    if isinstance(table[0], list):
        return "\n".join(" | ".join(_flatten_cell(cell) for cell in row) for row in table)
    return "\n".join(_flatten_cell(row) for row in table)


def load_finqa(data_path: str, sample_size: int) -> list[dict]:
    path = Path(data_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到資料集檔案：{data_path}")

    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError("test.json 必須是 JSON Array")

    logger.info("讀取本機資料集：%s，共 %d 筆原始資料", data_path, len(raw))

    samples = []
    skipped = 0
    for item in raw:
        qa_block = item.get("qa") or {}

        model_input = qa_block.get("model_input")
        if model_input and isinstance(model_input, list):
            context_parts = [
                entry[1] for entry in model_input
                if isinstance(entry, (list, tuple)) and len(entry) >= 2
            ]
            context = "\n".join(context_parts)
        else:
            parts = []
            pre = item.get("pre_text", [])
            parts.append(" ".join(pre) if isinstance(pre, list) else str(pre))
            table = item.get("table")
            if table:
                parts.append(_parse_table(table))
            post = item.get("post_text", [])
            parts.append(" ".join(post) if isinstance(post, list) else str(post))
            context = "\n".join(p for p in parts if p.strip())

        question = (item.get("question") or qa_block.get("question") or "")
        question = str(question).strip()

        answer = (
            qa_block.get("exe_ans")
            or qa_block.get("answer")
            or item.get("answer")
            or item.get("exe_ans")
        )
        answer = str(answer).strip() if answer is not None else ""

        if not question or not answer:
            skipped += 1
            continue

        samples.append({"context": context, "question": question, "answer": answer})

    logger.info("有效樣本：%d 筆，跳過：%d 筆", len(samples), skipped)

    if sample_size != -1:
        samples = samples[:sample_size]

    logger.info("實際評測樣本數：%d", len(samples))
    return samples


# ──────────────────────────────────────────────
# 提示詞構建
# ──────────────────────────────────────────────

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
        "2. In the \"answer\" field, write ONLY the final value:\n"
        "   - Numeric: a plain number with no units or symbols "
        "(e.g. 0.0861 for 8.61%—convert percentages to decimals by dividing by 100).\n"
        "   - Yes/No: exactly \"yes\" or \"no\" (lowercase).\n"
        "Your response MUST be a valid JSON object matching exactly this schema:\n"
        "{\"thought\": \"<string>\", \"answer\": \"<string>\"}\n"
        "Do NOT rename, add, or remove any keys. Output the JSON object only, no markdown fences."
    )


# ──────────────────────────────────────────────
# 答案提取（三層防禦機制）
# ──────────────────────────────────────────────

_BOXED_PATTERN    = re.compile(r"\\boxed\{([^}]*)\}")
_NUM_IN_TEXT      = re.compile(r"-?[\d,]+(?:\.\d+)?%?")
_YES_NO           = {"yes", "no"}
_YES_NO_IN_LINE   = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
_PERCENT_CONTEXT  = re.compile(r"%|percent(?:age)?", re.IGNORECASE)
_STRIP_UNITS      = re.compile(r"[^\d.\-%]")
_ANSWER_LINE_HINT = re.compile(
    r"(final\s*answer|therefore|答案|∴|=\s*-?[\d,]+(?:\.\d+)?%?)",
    re.IGNORECASE,
)


def _clean_boxed_content(raw: str) -> str:
    s = raw.replace("\\%", "%").replace(" ", "").strip()
    if s.lower() in _YES_NO:
        return s
    s = _STRIP_UNITS.sub("", s)
    if re.fullmatch(r"[-%.]*", s):
        return ""
    return s


def extract_answer(text: str) -> Optional[str]:
    matches = _BOXED_PATTERN.findall(text)
    if matches:
        raw = _clean_boxed_content(matches[-1])
        if raw.lower() in _YES_NO:
            return raw.lower()
        if raw:
            nums = _NUM_IN_TEXT.findall(raw)
            if nums:
                return nums[0]

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    hint_candidates = [ln for ln in lines if _ANSWER_LINE_HINT.search(ln)]
    scan_lines = hint_candidates[-3:] if hint_candidates else lines[-3:]

    for line in reversed(scan_lines):
        yn_match = _YES_NO_IN_LINE.search(line)
        if yn_match:
            return yn_match.group(1).lower()
        nums = _NUM_IN_TEXT.findall(line)
        if nums:
            return nums[-1]

    return None


def extract_answer_from_json(text: str) -> Optional[str]:
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        ans = obj.get("answer")
        if ans is not None:
            return str(ans).strip() or None
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    m = re.search(r'"answer"\s*:\s*"([^"]*)"', stripped)
    if m:
        val = m.group(1).strip()
        if val:
            return val

    return extract_answer(stripped)


def normalize_number(s: str) -> Optional[float]:
    if s is None:
        return None
    s = s.replace("\\%", "%").replace(" ", "").strip().replace(",", "")
    is_percent = s.endswith("%")
    s = s.rstrip("%")
    try:
        val = float(s)
        if is_percent:
            val /= 100.0
        return val
    except (ValueError, TypeError):
        return None


def is_correct(
    pred: Optional[str],
    truth: str,
    raw_response: str = "",
) -> tuple[bool, bool]:
    if pred is None:
        return False, True

    truth_lower = truth.strip().lower()

    if truth_lower in _YES_NO:
        if pred.strip().lower() == truth_lower:
            return True, False
        return False, (pred.strip().lower() not in _YES_NO)

    pred_val  = normalize_number(pred)
    truth_val = normalize_number(truth)

    if pred_val is None or truth_val is None:
        return False, True

    def within_tolerance(a: float, b: float) -> bool:
        abs_diff = abs(a - b)
        if abs_diff <= 0.01:
            return True
        if b != 0 and abs_diff / abs(b) <= 0.05:
            return True
        return False

    if within_tolerance(pred_val, truth_val):
        return True, False
    if within_tolerance(pred_val / 100.0, truth_val):
        return True, False
    if within_tolerance(pred_val * 100.0, truth_val):
        return True, False

    if pred_val > 1.0 and 0 < abs(truth_val) < 1.0:
        tail = raw_response[-100:] if raw_response else ""
        if _PERCENT_CONTEXT.search(tail):
            adjusted = pred_val / 100.0
            abs_diff = abs(adjusted - truth_val)
            rel_ok = (truth_val != 0) and (abs_diff / abs(truth_val) <= 0.10)
            if abs_diff <= 0.01 or rel_ok:
                return True, False

    if pred_val * truth_val < 0:
        abs_p, abs_t = abs(pred_val), abs(truth_val)
        for candidate in (abs_p, abs_p / 100.0, abs_p * 100.0):
            if within_tolerance(candidate, abs_t):
                return True, False

    return False, False


# ──────────────────────────────────────────────
# 排序評測指標
# ──────────────────────────────────────────────

def compute_ranking_metrics(samples: list[dict], k: int = 5) -> dict[str, float]:
    n = len(samples)
    if n == 0:
        return {
            "hit_rate_at_1":    0.0,
            f"hit_rate_at_{k}": 0.0,
            "mrr":              0.0,
            f"ndcg_at_{k}":     0.0,
        }

    hit1_sum = 0; hitk_sum = 0; rr_sum = 0.0; ndcg_sum = 0.0
    idcg = 1.0 / math.log2(2)

    for r in samples:
        candidates = r.get("candidates") or []
        if not candidates:
            candidates = [{"rank": 1, "is_correct": r["is_correct"]}]
        cands_k = candidates[:k]

        if cands_k and cands_k[0]["is_correct"]:
            hit1_sum += 1

        first_correct_rank = None
        for cand in cands_k:
            if cand["is_correct"]:
                first_correct_rank = cand["rank"]
                break

        if first_correct_rank is not None:
            hitk_sum += 1
            rr_sum += 1.0 / first_correct_rank

        dcg = (1.0 / math.log2(first_correct_rank + 1)) if first_correct_rank is not None else 0.0
        ndcg_sum += dcg / idcg

    return {
        "hit_rate_at_1":    round(hit1_sum  / n * 100, 4),
        f"hit_rate_at_{k}": round(hitk_sum  / n * 100, 4),
        "mrr":              round(rr_sum    / n,       6),
        f"ndcg_at_{k}":     round(ndcg_sum  / n * 100, 4),
    }


# ──────────────────────────────────────────────
# 文字相似度指標
# ──────────────────────────────────────────────

def compute_text_metrics(predictions: list[str], references: list[str]) -> dict[str, float]:
    results: dict[str, float] = {}

    if _HAS_ROUGE:
        scorer = _rouge_scorer_mod.RougeScorer(["rouge1", "rouge2", "rouge3"], use_stemmer=True)
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
        results["rouge_1_f1"] = results["rouge_2_f1"] = results["rouge_3_f1"] = -1.0

    if _HAS_BERT_SCORE:
        logger.info("計算 BERTScore…")
        _, _, F1 = _bert_score_fn(predictions, references, lang="en",
                                  model_type="bert-base-uncased", verbose=False)
        results["bert_score_f1"] = round(float(F1.mean()) * 100, 4)
    else:
        results["bert_score_f1"] = -1.0

    if _HAS_MOVER:
        logger.info("計算 MoverScore…")
        idf_refs  = _get_idf_dict(references)
        idf_preds = _get_idf_dict(predictions)
        scores = _wms_fn(references, predictions, idf_refs, idf_preds,
                         stop_words=[], n_gram=1, remove_subwords=True)
        results["mover_score"] = round(sum(scores) / len(scores) * 100, 4)
    else:
        results["mover_score"] = -1.0

    return results


# ──────────────────────────────────────────────
# Google Gemini API 呼叫（帶指數退避重試）
# ──────────────────────────────────────────────

# Google AI Studio 免費方案速率限制（Gemini 2.0 Flash）：
#   15 RPM / 1,000,000 TPM / 200 RPD
# 付費方案：1500 RPM。執行前確認自己的配額等級。
_GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


async def _call_with_retry(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    index: int,
    max_retries: int = 5,
) -> str:
    """
    單次 API 呼叫，遇到 429 Rate Limit 時使用指數退避重試。
    退避等待：5 → 10 → 20 → 40 → 80 秒。
    """
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                n=1,
                timeout=120.0,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower()
            is_last = attempt == max_retries - 1

            if is_last:
                raise

            wait = (2 ** attempt) * 5  # 5 / 10 / 20 / 40 秒
            if is_rate_limit:
                logger.warning(
                    "Rate limit (index=%d, attempt=%d/%d)，等待 %ds 後重試…",
                    index, attempt + 1, max_retries, wait,
                )
            else:
                logger.warning(
                    "API 錯誤 (index=%d, attempt=%d/%d)：%s，等待 %ds…",
                    index, attempt + 1, max_retries, e, wait,
                )
            await asyncio.sleep(wait)

    return ""  # 不可達，保留型別完整性


async def query_model_google(
    client: AsyncOpenAI,
    sem: asyncio.Semaphore,
    model: str,
    context: str,
    question: str,
    index: int,
    pbar: atqdm,
    top_k: int = 1,
) -> list[tuple[str, str]]:
    """
    非同步呼叫 Google Gemini API。
    由於 Gemini 的 OpenAI 相容端點不支援 n>1，以序列迴圈實現 top-k：
      - k=1（rank-1）：temperature=0.0，確定性最高
      - k≥2（多樣候選）：temperature=0.5，產生差異化輸出
    候選間插入短暫延遲（args.request_delay），避免觸發速率限制。
    """
    prompt = build_prompt(context, question)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]

    async with sem:
        results: list[tuple[str, str]] = []
        for k in range(top_k):
            temp = 0.0 if k == 0 else 0.5
            try:
                content = await _call_with_retry(
                    client, model, messages, temp, 2048, index
                )
                if not content.strip():
                    results.append(("", "Gemini 回傳空字串"))
                else:
                    results.append((content, ""))
            except Exception as e:
                err = f"Gemini 呼叫失敗 (index={index}, k={k})：{type(e).__name__}: {e}"
                logger.warning(err)
                results.append(("", err))

            # 候選間節流：避免 429（只在還有後續候選時等待）
            if k < top_k - 1:
                await asyncio.sleep(1.5)

        pbar.update(1)
        return results


# ──────────────────────────────────────────────
# 評測主流程
# ──────────────────────────────────────────────

async def run_evaluation(args: argparse.Namespace) -> EvalReport:
    samples = load_finqa(args.data_path, args.sample_size)
    total   = len(samples)

    client = AsyncOpenAI(
        base_url=_GOOGLE_BASE_URL,
        api_key=args.api_key,
    )

    sem = asyncio.Semaphore(args.concurrency)

    report = EvalReport(
        model=args.model,
        base_url=_GOOGLE_BASE_URL,
        dataset="FinQA",
        total=total,
    )

    top_k = args.top_k
    logger.info(
        "開始評測（Google Gemini）：模型=%s，樣本數=%d，並行度=%d，top_k=%d",
        args.model, total, args.concurrency, top_k,
    )

    with atqdm(total=total, desc="評測進度", unit="sample") as pbar:
        tasks = [
            query_model_google(
                client=client,
                sem=sem,
                model=args.model,
                context=s["context"],
                question=s["question"],
                index=i,
                pbar=pbar,
                top_k=top_k,
            )
            for i, s in enumerate(samples)
        ]
        raw_results = await asyncio.gather(*tasks)

    # ── 評分 ──────────────────────────────────
    for i, candidates_raw in enumerate(raw_results):
        sample = samples[i]

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
            logger.warning("[解析失敗] 預期: %s | 末尾: ...%s", sample["answer"], reply_tail)
        else:
            report.wrong += 1
            status = "✗ Wrong"
            reply_tail = r1["raw_response"][-120:].replace("\n", " ").strip() if r1["raw_response"] else "(空回覆)"
            logger.warning(
                "[錯誤] 預期: %s | 提取: %s | 末尾: ...%s",
                sample["answer"], r1["extracted_answer"], reply_tail,
            )

        logger.debug(
            "Sample %d/%d [%s] | GT: %s | Pred: %s",
            i + 1, total, status, sample["answer"], r1["extracted_answer"],
        )

    report.accuracy = report.correct / total * 100 if total > 0 else 0.0

    # ── 排序指標 ──────────────────────────────
    rank_metrics = compute_ranking_metrics(report.samples, k=top_k)
    report.hit_rate_at_1 = rank_metrics["hit_rate_at_1"]
    report.hit_rate_at_k = rank_metrics.get(f"hit_rate_at_{top_k}", report.hit_rate_at_1)
    report.mrr           = rank_metrics["mrr"]
    report.ndcg_at_5     = rank_metrics.get(f"ndcg_at_{top_k}", 0.0)

    # ── 文字相似度指標 ─────────────────────────
    preds_text = [(s["extracted_answer"] or "") for s in report.samples]
    refs_text  = [s["ground_truth"] for s in report.samples]
    text_metrics = compute_text_metrics(preds_text, refs_text)
    report.bert_score_f1 = text_metrics["bert_score_f1"]
    report.rouge_1_f1    = text_metrics["rouge_1_f1"]
    report.rouge_2_f1    = text_metrics["rouge_2_f1"]
    report.rouge_3_f1    = text_metrics["rouge_3_f1"]
    report.mover_score   = text_metrics["mover_score"]

    return report


# ──────────────────────────────────────────────
# 輸出報告
# ──────────────────────────────────────────────

def print_report(report: EvalReport, top_k: int = 1) -> None:
    sep = "=" * 55

    def _fmt(v: float, pct: bool = True) -> str:
        return f"{v:.2f}%" if pct else f"{v:.4f}"

    def _na(v: float, pct: bool = True) -> str:
        return "N/A（未安裝）" if v < 0 else _fmt(v, pct)

    print(f"\n{sep}")
    print("       FinQA 評測結果報告（Google Gemini）")
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
    print(f"  Hit Rate@1   : {report.hit_rate_at_1:.2f}%")
    print(f"  Hit Rate@{top_k}  : {report.hit_rate_at_k:.2f}%")
    print(f"  MRR          : {report.mrr:.4f}")
    print(f"  NDCG@{top_k}      : {report.ndcg_at_5:.2f}%")
    print(sep)
    print("  ── 文字相似度指標（rank-1 vs GT）──")
    print(f"  ROUGE-1 F1   : {_na(report.rouge_1_f1)}")
    print(f"  ROUGE-2 F1   : {_na(report.rouge_2_f1)}")
    print(f"  ROUGE-3 F1   : {_na(report.rouge_3_f1)}")
    print(f"  BERTScore F1 : {_na(report.bert_score_f1)}")
    print(f"  MoverScore   : {_na(report.mover_score)}")
    print(f"{sep}\n")


def save_results(report: EvalReport, output_path: str) -> None:
    data = {
        "summary": {
            "model":         report.model,
            "base_url":      report.base_url,
            "dataset":       report.dataset,
            "timestamp":     report.timestamp,
            "total":         report.total,
            "correct":       report.correct,
            "wrong":         report.wrong,
            "parse_failed":  report.parse_failed,
            "accuracy_pct":  round(report.accuracy, 4),
            "hit_rate_at_1": round(report.hit_rate_at_1, 4),
            "hit_rate_at_k": round(report.hit_rate_at_k, 4),
            "mrr":           round(report.mrr, 6),
            "ndcg_at_5":     round(report.ndcg_at_5, 4),
            "bert_score_f1": round(report.bert_score_f1, 4),
            "rouge_1_f1":    round(report.rouge_1_f1, 4),
            "rouge_2_f1":    round(report.rouge_2_f1, 4),
            "rouge_3_f1":    round(report.rouge_3_f1, 4),
            "mover_score":   round(report.mover_score, 4),
        },
        "samples": report.samples,
    }
    Path(output_path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("詳細結果已儲存至：%s", output_path)


def _build_output_path(report: EvalReport) -> Path:
    model_short = report.model.split("/")[-1]
    model_short = re.sub(r'[\\/:*?"<>| ]', "_", model_short)
    acc_str = f"{report.accuracy:.2f}"
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    return out_dir / f"{model_short}_ACC{acc_str}.json"


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FinQA 金融推理資料集 LLM 評測工具（Google Gemini 版）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-path",   default="test.json",
                        help="本機 FinQA test.json 路徑")
    parser.add_argument("--model",       default="gemini-2.0-flash",
                        help="Gemini 模型名稱（gemini-2.0-flash / gemini-1.5-pro 等）")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GOOGLE_API_KEY", ""),
        help="Google AI Studio API Key（亦可用環境變數 GOOGLE_API_KEY 設定）",
    )
    parser.add_argument("--sample-size", type=int, default=50,
                        help="測試樣本數；-1 表示全部")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help=(
            "最大並行請求數。免費方案（15 RPM）建議 3，"
            "付費方案（1500 RPM）可調高至 20+"
        ),
    )
    parser.add_argument("--top-k",  type=int, default=1,
                        help="每題生成的候選答案數（k≥2 時後續候選 temperature=0.5）")
    parser.add_argument("--output", default=None,
                        help="結果輸出路徑（未指定時自動產生 results/{模型}_ACC{準確率}.json）")
    parser.add_argument("--verbose", action="store_true", help="顯示每筆樣本偵錯資訊")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.api_key:
        logger.error(
            "未提供 API Key！請設定環境變數 GOOGLE_API_KEY 或傳入 --api-key <KEY>"
        )
        sys.exit(1)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        report = asyncio.run(run_evaluation(args))
    except KeyboardInterrupt:
        logger.info("使用者中斷評測。")
        sys.exit(0)
    except Exception as e:
        logger.error("評測過程發生未預期錯誤：%s", e, exc_info=True)
        sys.exit(1)

    print_report(report, top_k=args.top_k)
    output_path = args.output if args.output else _build_output_path(report)
    save_results(report, str(output_path))


if __name__ == "__main__":
    main()
