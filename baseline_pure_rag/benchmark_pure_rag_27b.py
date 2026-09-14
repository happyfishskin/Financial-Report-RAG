#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
純向量 RAG baseline（27B 大模型）— version10 規格書實作
=====================================================
研究問題：單靠「向量搜尋 Top-K 證據 ＋ 27B 模型生成」，能否解決財報數字的
欄位與資料列定位問題？

本腳本是**全新的獨立腳本**，刻意不沿用 version8/benchmark_evidence_format.py：
該腳本仍會呼叫 SLM Router（`_llm_intent_router`）與槽位補全
（`_enrich_intent_from_question`），並用抽出的公司／期別對 ChromaDB 做
metadata 硬過濾，不符合「完全純 RAG」的定義。

從既有系統只借用三樣**不含任何路由知識**的東西，以確保與凍結結果可比：
  1. `_BGEEmbedder`  —— 同一顆 bge-small-zh-v1.5，CPU 執行
  2. `_score_one`    —— 既有 EM／數值一致評分器（逐字不動）
  3. `_is_refusal`   —— 既有拒答判定
向量庫路徑與 collection 名亦讀自既有 `config/system_config.json`。

明確排除（規格書 §5）：SLM Router／意圖 JSON、Python 路由覆核、Fix 1–20、
公司別名表、科目同義詞／比率本體論、metadata 公司／期別／表格硬過濾、
Fact 與關係事實直查、Python 算術、二次檢索／改寫問句／重試。
模型只看得到「原始問題 ＋ Top-5 原始 Markdown 證據」。

用法：
    python3 benchmark_pure_rag_27b.py --suite main            # n=130 主要評測
    python3 benchmark_pure_rag_27b.py --suite ext             # n=820 延伸評測
    python3 benchmark_pure_rag_27b.py --suite all [--resume]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V8   = ROOT.parent / "system"
sys.path.insert(0, str(V8))

import rag_test_system_v14 as V          # noqa: E402  只借 embedder／評分器

# ══════════════════════════════════════════════════════════════════
# 固定設定（規格書 §3）——不得依測試結果調整
# ══════════════════════════════════════════════════════════════════
TOP_K            = 5          # 全庫語意搜尋 Top-K
TEMPERATURE      = 0.0
SEED             = 42
NUM_CTX          = 4096       # context 長度
MAX_OUT_TOKENS   = 384        # 輸出長度
# 證據字元預算：規格書 §4 要求模型看到「Top-5 原始 Markdown 證據」，故預算由
# 4,096 token 的 context 視窗反推，而非沿用某個既有常數：
#   可用 = 4096 − 384（輸出）− 200（prompt 樣板與 chat template 餘裕）= 3,512 tokens
# 本語料（中英雙語會計科目＋數字表格）實測約 0.43 token/字元；取保守值 0.55 換算
#   3,512 ÷ 0.55 ≈ 6,385 → 取 6,400 字元。
# 每題另記錄 prompt_tokens 與 ctx_overflow，若真有題目超出視窗會被標記出來稽核。
CONTEXT_MAX_CHARS = 6400

DEFAULT_OLLAMA   = "http://127.0.0.1:11434"
DEFAULT_MODEL    = "qwen3.8-27b-iq3xxs"
GGUF_PATH        = ROOT / "models" / "Qwen3.8-27B-UD-IQ3_XXS.gguf"

# ══════════════════════════════════════════════════════════════════
# 固定 Prompt（規格書 §6，逐字）
# ══════════════════════════════════════════════════════════════════
# 規格書的 prompt 本文寫「請只根據提供的財報證據」，故證據必須有安放之處；
# 除插入「財報證據」區塊外，其餘文字一字未改，亦未加入任何格式提示或範例。
PROMPT_TEMPLATE = """你是一個財報問答系統。請只根據提供的財報證據，填入題目的空格。

財報證據：
{context}

題目：
{question}

填空：
答案是「＿＿＿＿」。

規則：
1. 只填入空格中應填的最終答案。
2. 若證據不足，填入「找不到相關資料」。
3. 不得加入說明、推理過程、單位以外的文字，或證據中沒有的數字。"""

# ══════════════════════════════════════════════════════════════════
# 評測資料（規格書 §7）
# ══════════════════════════════════════════════════════════════════
QDIR = V8 / "questions"

# 主要評測：兩組 frozen held-out 的**數值題**（direct_lookup*），n=60+70=130。
# 與 results/evidence_format_ablation_ho_{arch,colloq}.json 之 held-out 部分
# 完全同題，可直接逐題比較。
MAIN_SETS = [
    ("held-out：架構 100 之數值題", QDIR / "heldout" / "heldout_arch_100.json"),
    ("held-out：口語 100 之數值題", QDIR / "heldout" / "heldout_colloq_100.json"),
]

# 延伸評測：三批預先保留 held-out 全量，n=360+420+40=820，須分題型報告。
EXT_SETS = [
    ("heldout：架構 100",     QDIR / "heldout"  / "heldout_arch_100.json"),
    ("heldout：口語 100",     QDIR / "heldout"  / "heldout_colloq_100.json"),
    ("heldout：口語自然 100", QDIR / "heldout"  / "heldout_colloq_nat_100.json"),
    ("heldout：圖譜能力 30",  QDIR / "heldout"  / "heldout_graph_cap_30.json"),
    ("heldout：圖譜自然 30",  QDIR / "heldout"  / "heldout_graph_nat_30.json"),
    ("heldout2：架構 100",     QDIR / "heldout2" / "heldout_arch_100.json"),
    ("heldout2：口語 100",     QDIR / "heldout2" / "heldout_colloq_100.json"),
    ("heldout2：口語自然 100", QDIR / "heldout2" / "heldout_colloq_nat_100.json"),
    ("heldout2：圖譜能力 30",  QDIR / "heldout2" / "heldout_graph_cap_30.json"),
    ("heldout2：圖譜自然 30",  QDIR / "heldout2" / "heldout_graph_nat_30.json"),
    ("heldout2：候選歧義 60",  QDIR / "heldout2" / "heldout_ambig_60.json"),
    ("heldout3：關係人歧義 40", QDIR / "heldout3" / "heldout_ambig_rp_40.json"),
]


def load_items(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else raw.get("questions", [])


def is_numeric_q(item: dict) -> bool:
    """數值事實題 = target_route 以 direct_lookup 開頭（與既有消融取題一致）。"""
    return str(item.get("metadata", {}).get("target_route", "")).startswith("direct_lookup")


def build_suite(suite: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    if suite in ("main", "all"):
        for label, p in MAIN_SETS:
            for it in load_items(p):
                if is_numeric_q(it):
                    out.append((f"MAIN｜{label}", it))
    if suite in ("ext", "all"):
        for label, p in EXT_SETS:
            for it in load_items(p):
                out.append((f"EXT｜{label}", it))
    return out


# ══════════════════════════════════════════════════════════════════
# 檢索：ChromaDB 全庫 Top-5，無任何 metadata 過濾
# ══════════════════════════════════════════════════════════════════
def retrieve(collection, embedder, question: str, top_k: int = TOP_K) -> list[dict]:
    """
    純語意檢索：以**原始問題**向量化（不改寫、不擴充同義詞），
    對全庫查詢（where=None，不做公司／期別／表格過濾）。
    """
    emb = embedder.embed_query(question)
    res = collection.query(
        query_embeddings=[emb],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    return [
        {
            "content": doc,
            "company_code": meta.get("company_code", ""),
            "company_name": meta.get("company_name", ""),
            "quarter":      meta.get("quarter", ""),
            "table_name":   meta.get("table_name", ""),
            "source":       meta.get("source", ""),
            "score":        round(1.0 - float(dist), 4),
        }
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0],
                                   res["distances"][0])
    ]


def format_context(hits: list[dict],
                   max_chars: int = CONTEXT_MAX_CHARS) -> tuple[str, int]:
    """
    原始 Markdown 片段直送，不做 K-V 扁平化、不重排、不摘要。
    僅加上片段序號分隔；每個 chunk 首行本來就自帶
    「# 代號_公司  ｜ 期別 ｜ 表名」標頭（建庫時寫入的原文），故不另注入 metadata。

    回傳 (context, 進入視窗的片段數)。
    """
    if not hits:
        return "（無相關財報資料）", 0
    parts, total = [], 0
    for i, h in enumerate(hits, 1):
        block = f"【片段 {i}】\n{h['content']}"
        if total + len(block) > max_chars:
            # 尾端片段截斷後保留，而非整段丟棄——丟棄等於偷偷把 Top-5 變成 Top-2，
            # 與規格書 §4 不符；截斷至少讓該片段的表頭與前幾列進得了視窗。
            budget = max_chars - total - 40
            if budget > 200:
                parts.append(block[:budget].rstrip() + "\n…（片段過長已截斷）")
            break
        parts.append(block)
        total += len(block)
    return "\n\n---\n\n".join(parts), len(parts)


# ══════════════════════════════════════════════════════════════════
# Hit@5：正確來源是否進入 Top-5
# ══════════════════════════════════════════════════════════════════
def gold_sources(item: dict) -> list[tuple[str, str, str]] | None:
    """
    回傳金標來源 (company_code, quarter, table_name) 清單；無表格金標者回 None
    （圖譜題的證據不是財報數值表，不計 Hit@5）。
    """
    md = item.get("metadata", {}) or {}
    route = str(md.get("target_route", ""))
    table = str(md.get("table_name", "") or "")
    if route.startswith("graph_rag") or not table:
        return None
    if route == "direct_lookup_multi_company":
        return [(str(c), str(md.get("quarter", "")), table)
                for c in (md.get("companies") or [])]
    if route == "direct_lookup_multi_period":
        code = str(md.get("company_code", ""))
        return [(code, str(p), table) for p in (md.get("periods") or [])]
    return [(str(md.get("company_code", "")), str(md.get("quarter", "")), table)]


def hit_at_k(item: dict, hits: list[dict]) -> tuple[bool | None, bool | None]:
    """
    回傳 (strict, lenient)：
      strict  —— **所有**金標來源都進入 Top-5（批次題較嚴）
      lenient —— 任一金標來源進入 Top-5
    單來源題兩者相同。無金標表格者回 (None, None)。
    """
    golds = gold_sources(item)
    if not golds:
        return None, None
    got = {(h["company_code"], h["quarter"], h["table_name"]) for h in hits}
    flags = [g in got for g in golds]
    return (all(flags) if flags else False, any(flags))


# ══════════════════════════════════════════════════════════════════
# 生成：Ollama 原生 API（或 OpenAI 相容端點）
# ══════════════════════════════════════════════════════════════════
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _post(url: str, payload: dict, timeout: int = 900) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generate(backend: str, base_url: str, model: str, prompt: str) -> dict:
    """
    單次生成，一次就好——規格書禁止重試、改寫與二次檢索。
    回傳 {answer, raw, prompt_tokens, completion_tokens, latency_sec, error}
    """
    t0 = time.time()
    try:
        if backend == "ollama":
            r = _post(f"{base_url.rstrip('/')}/api/chat", {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,                       # 關閉思考鏈，輸出預算才夠
                "options": {
                    "temperature": TEMPERATURE,
                    "seed": SEED,
                    "num_ctx": NUM_CTX,
                    "num_predict": MAX_OUT_TOKENS,
                },
            })
            raw = (r.get("message") or {}).get("content", "") or ""
            ptok = int(r.get("prompt_eval_count") or 0)
            ctok = int(r.get("eval_count") or 0)
        else:                                          # llama.cpp / OpenAI 相容
            r = _post(f"{base_url.rstrip('/')}/v1/chat/completions", {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": TEMPERATURE,
                "seed": SEED,
                "max_tokens": MAX_OUT_TOKENS,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            })
            raw = ((r.get("choices") or [{}])[0].get("message") or {}).get("content", "") or ""
            usage = r.get("usage") or {}
            ptok = int(usage.get("prompt_tokens") or 0)
            ctok = int(usage.get("completion_tokens") or 0)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        return {"answer": "找不到相關資料", "raw": "", "prompt_tokens": 0,
                "completion_tokens": 0, "latency_sec": round(time.time() - t0, 2),
                "error": f"{type(exc).__name__}: {exc}"[:200]}

    ans = _THINK_RE.sub("", raw)
    ans = re.sub(r"</?think>", "", ans).strip()
    # 模型若照樣式回「答案是「X」。」則取引號內容；否則原樣送評分器
    m = re.search(r"[「『]([^」』]*)[」』]", ans)
    if m and m.group(1).strip():
        ans = m.group(1).strip()
    ans = ans.strip().strip("。").strip()
    return {"answer": ans or "找不到相關資料", "raw": raw[:600],
            "prompt_tokens": ptok, "completion_tokens": ctok,
            "latency_sec": round(time.time() - t0, 2), "error": ""}


# ══════════════════════════════════════════════════════════════════
# 執行前記錄：模型檔名、大小、SHA256、GPU（規格書 §3）
# ══════════════════════════════════════════════════════════════════
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def gpu_snapshot() -> dict:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20).stdout.strip().splitlines()[0]
        name, tot, used = (x.strip() for x in out.split(","))
        return {"gpu": name, "vram_total_mib": int(tot), "vram_used_mib": int(used)}
    except Exception:                                   # noqa: BLE001
        return {"gpu": "", "vram_total_mib": 0, "vram_used_mib": 0}


# ══════════════════════════════════════════════════════════════════
# 匯總
# ══════════════════════════════════════════════════════════════════
def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0}
    hs = [r for r in rows if r["hit5_strict"] is not None]
    lat = [r["latency_sec"] for r in rows]
    return {
        "n": n,
        "exact": sum(1 for r in rows if r["scores"]["exact_match"]),
        "em": round(sum(1 for r in rows if r["scores"]["exact_match"]) / n, 4),
        "numeric": sum(1 for r in rows if r["scores"]["numeric_match"]),
        "numeric_rate": round(sum(1 for r in rows if r["scores"]["numeric_match"]) / n, 4),
        "refusals": sum(1 for r in rows if r["refused"]),
        "refusal_rate": round(sum(1 for r in rows if r["refused"]) / n, 4),
        "hit5_scored_n": len(hs),
        "hit5_strict": round(sum(1 for r in hs if r["hit5_strict"]) / len(hs), 4) if hs else None,
        "hit5_lenient": round(sum(1 for r in hs if r["hit5_lenient"]) / len(hs), 4) if hs else None,
        "avg_latency_sec": round(sum(lat) / n, 2),
        "avg_chunks_in_context": round(sum(r.get("chunks_in_context", 0)
                                            for r in rows) / n, 2),
        "ctx_overflow": sum(1 for r in rows if r.get("ctx_overflow")),
        "avg_prompt_tokens": round(sum(r["prompt_tokens"] for r in rows) / n, 1),
        "avg_completion_tokens": round(sum(r["completion_tokens"] for r in rows) / n, 1),
        "errors": sum(1 for r in rows if r["error"]),
    }


def group_by(rows: list[dict], key: str) -> dict:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(str(r.get(key, "")), []).append(r)
    return {k: summarize(v) for k, v in sorted(out.items())}


def write_report(payload: dict, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    env, md = payload["environment"], []
    md.append("# 純向量 RAG baseline（27B 大模型）\n")
    md.append(f"- 生成模型：`{env['model_file']}`（{env['model_size_gb']} GB，"
              f"SHA256 `{env['model_sha256'][:16]}…`）")
    md.append(f"- 推論引擎：{env['backend']}｜Embedding：{env['embed_model']}（CPU）")
    md.append(f"- 向量庫：{env['chroma_collection']}（{env['chunk_count']:,} chunks）"
              f"｜Top-K={env['top_k']}｜全庫檢索、無 metadata 過濾")
    md.append(f"- temperature={env['temperature']}｜seed={env['seed']}"
              f"｜num_ctx={env['num_ctx']}｜輸出上限={env['max_out_tokens']} tokens")
    md.append(f"- GPU：{env['gpu']}｜VRAM 峰值 {env['vram_peak_mib']:,} MiB / "
              f"{env['vram_total_mib']:,} MiB\n")

    def table(title: str, blocks: dict) -> None:
        md.append(f"\n## {title}\n")
        md.append("| 題組 | n | EM | 數值一致 | 拒答率 | Hit@5(嚴) | Hit@5(寬) | "
                  "平均延遲 | 輸入 tok | 輸出 tok |")
        md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for k, s in blocks.items():
            if not s.get("n"):
                continue
            h1 = f"{s['hit5_strict']:.1%}" if s["hit5_strict"] is not None else "—"
            h2 = f"{s['hit5_lenient']:.1%}" if s["hit5_lenient"] is not None else "—"
            md.append(f"| {k} | {s['n']} | {s['em']:.1%}（{s['exact']}/{s['n']}） | "
                      f"{s['numeric_rate']:.1%} | {s['refusal_rate']:.1%} | {h1} | {h2} | "
                      f"{s['avg_latency_sec']:.1f}s | {s['avg_prompt_tokens']:.0f} | "
                      f"{s['avg_completion_tokens']:.0f} |")

    for sec in payload["sections"]:
        table(sec["title"], {"合計": sec["overall"]})
        table(f"{sec['title']}｜分題組", sec["by_dataset"])
        table(f"{sec['title']}｜分題型", sec["by_question_type"])

    md.append("\n## 結論界線\n")
    md.append(payload["caveat"])
    Path(f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


CAVEAT = (
    "本實驗僅評估單一 27B、IQ3_XXS 量化模型在固定純 RAG 設定下的表現；結果不代表"
    "所有大型模型或所有量化設定的能力。若大型模型提升 EM，僅表示其讀表能力較佳；"
    "是否能取代確定性查表，仍須與相同 held-out 題組上的 Fact 直查結果比較。"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="main", choices=["main", "ext", "all"])
    ap.add_argument("--backend", default="ollama", choices=["ollama", "openai"])
    ap.add_argument("--base-url", default=DEFAULT_OLLAMA)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--gguf", default=str(GGUF_PATH))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "results" / "pure_rag_27b"))
    ap.add_argument("--resume", action="store_true",
                    help="沿用既有 checkpoint，只補跑未完成的題目")
    ap.add_argument("--skip-sha", action="store_true", help="跳過 SHA256（除錯用）")
    args = ap.parse_args()

    items = build_suite(args.suite)
    if args.limit:
        items = items[:args.limit]
    if not items:
        print("✗ 沒有題目")
        return 2

    gguf = Path(args.gguf)
    env = {
        "backend": f"{args.backend} @ {args.base_url}｜model={args.model}",
        "model_file": gguf.name,
        "model_size_gb": round(gguf.stat().st_size / 1e9, 2) if gguf.exists() else 0,
        "model_sha256": ("" if (args.skip_sha or not gguf.exists()) else sha256_of(gguf)),
        "model_source": "unsloth/Qwen3.8-27B-GGUF",
        "embed_model": V.DEFAULT_EMBED_MODEL,
        "chroma_collection": V._CHROMA_COLLECTION,
        "top_k": TOP_K, "temperature": TEMPERATURE, "seed": SEED,
        "num_ctx": NUM_CTX, "max_out_tokens": MAX_OUT_TOKENS,
        "context_max_chars": CONTEXT_MAX_CHARS,
    }
    env.update(gpu_snapshot())
    env["vram_peak_mib"] = env.get("vram_used_mib", 0)

    import chromadb
    embedder = V._BGEEmbedder(V.DEFAULT_EMBED_MODEL, device="cpu")
    client = chromadb.PersistentClient(path=str(V.DEFAULT_VECTOR_DB))
    collection = client.get_collection(name=V._CHROMA_COLLECTION)
    env["chunk_count"] = collection.count()

    ckpt = Path(f"{args.out}_checkpoint.json")
    done: dict[str, dict] = {}
    if args.resume and ckpt.exists():
        done = {r["key"]: r for r in json.loads(ckpt.read_text(encoding="utf-8"))}
        print(f"[resume] 已載入 {len(done)} 題結果")

    print(f"題目：{len(items)}｜suite={args.suite}｜"
          f"chunks={env['chunk_count']:,}｜模型={env['model_file']}")

    rows: list[dict] = []
    t0 = time.time()
    for i, (label, it) in enumerate(items, 1):
        key = f"{label}#{it.get('id')}"
        if key in done:
            rows.append(done[key])
            continue
        q, gold = it["question"], str(it.get("expected_answer", ""))
        hits = retrieve(collection, embedder, q)
        ctx, n_ctx_chunks = format_context(hits)
        gen = generate(args.backend, args.base_url, args.model,
                       PROMPT_TEMPLATE.format(context=ctx, question=q))
        strict, lenient = hit_at_k(it, hits)
        rec = {
            "key": key, "dataset": label, "id": it.get("id"),
            "question_type": it.get("question_type", ""),
            "target_route": (it.get("metadata", {}) or {}).get("target_route", ""),
            "question": q, "expected_answer": gold, "answer": gen["answer"],
            "raw": gen["raw"], "scores": V._score_one(gen["answer"], gold),
            "refused": V._is_refusal(gen["answer"]),
            "hit5_strict": strict, "hit5_lenient": lenient,
            "retrieved": [{k: h[k] for k in
                           ("company_code", "quarter", "table_name", "source", "score")}
                          for h in hits],
            "chunks_in_context": n_ctx_chunks, "context_chars": len(ctx),
            "ctx_overflow": gen["prompt_tokens"] > NUM_CTX - MAX_OUT_TOKENS,
            "prompt_tokens": gen["prompt_tokens"],
            "completion_tokens": gen["completion_tokens"],
            "latency_sec": gen["latency_sec"], "error": gen["error"],
        }
        rows.append(rec)

        used = gpu_snapshot().get("vram_used_mib", 0)
        env["vram_peak_mib"] = max(env["vram_peak_mib"], used)
        mark = "✓" if rec["scores"]["exact_match"] else "✗"
        hm = "—" if strict is None else ("H" if strict else "-")
        print(f"  [{i:4d}/{len(items)}] {mark}{hm} {gen['latency_sec']:5.1f}s  "
              f"{q[:38]}  →  {rec['answer'][:24]}")
        if i % 20 == 0:
            ckpt.parent.mkdir(parents=True, exist_ok=True)
            ckpt.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    sections = []
    for tag, title in (("MAIN", "主要評測：兩組 frozen held-out 數值題（n=130）"),
                       ("EXT",  "延伸評測：三批 held-out 全量（n=820）")):
        sub = [r for r in rows if r["dataset"].startswith(tag)]
        if sub:
            sections.append({
                "tag": tag, "title": title,
                "overall": summarize(sub),
                "by_dataset": group_by(sub, "dataset"),
                "by_question_type": group_by(sub, "question_type"),
            })

    payload = {
        "title": "純向量 RAG baseline（27B 大模型）— version10",
        "research_question": "單靠「向量搜尋 Top-K 證據＋27B 模型生成」，"
                             "能否解決財報數字的欄位與資料列定位問題？",
        "design": {
            "pipeline": "原始問題 → bge-small-zh-v1.5 → ChromaDB 全庫 Top-5 → "
                        "原始 Markdown → 27B 單次生成 → 既有 EM 評分器",
            "excluded": ["SLM Router／意圖 JSON", "Python 路由覆核", "Fix 1–20",
                         "公司別名表", "科目同義詞／比率本體論",
                         "metadata 公司／期別／表格硬過濾",
                         "Fact 數值直查與關係事實直查", "Python 算術",
                         "二次檢索／改寫問句／重試", "依測試結果調參"],
            "prompt": PROMPT_TEMPLATE,
        },
        "environment": env,
        "suite": args.suite, "n": len(rows),
        "elapsed_sec": round(time.time() - t0, 1),
        "sections": sections,
        "caveat": CAVEAT,
        "results": rows,
    }
    write_report(payload, Path(args.out))
    print(f"\n輸出：{args.out}.json / {args.out}.md")
    for sec in sections:
        s = sec["overall"]
        print(f"  {sec['title']}：EM {s['em']:.1%}（{s['exact']}/{s['n']}）"
              f"｜Hit@5 {s['hit5_strict']}｜拒答 {s['refusal_rate']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
