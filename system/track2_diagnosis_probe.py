# -*- coding: utf-8 -*-
"""軌道二拒答成因診斷探針（不修改系統，僅離線重問）。

設計：
  A 組（robust_001~006）：沿用系統實跑時 **檢索到的同一批片段**，
      僅將數值抽取契約換成敘述型契約 → 隔離「契約層」變因。
  B 組（robust_007~010）：系統檢索未命中目標表，改以 oracle 片段
      （自 ChromaDB 直取金標來源表）餵入敘述型契約 → 隔離「檢索層」變因。
兩組皆不改動 rag_test_system_v14.py。
"""
import json, re, sys, requests, chromadb

VLLM = "http://localhost:8000/v1/chat/completions"
MODEL = "Qwen/Qwen3-4B-AWQ"

NARRATIVE_PROMPT = """\
你是台灣財報審計員。以下是財報附註的原文片段，請據此回答問題。

【判定規則】
1. 只能引用片段中出現的文字，嚴禁補充片段以外的知識或憑記憶作答。
2. 公司與期間必須與問題相符；不符或片段中無相關敘述 → status=not_found。
3. 這是**敘述型**問題，答案是文字說明，不是數值。不要嘗試抽取數字。
4. 作答須忠實摘述原文用語（如準則名稱、條號、衡量方式），不得改寫其意。

【輸出格式】只輸出一個 JSON 物件：
  status     : ok | not_found
  answer_text: 文字答案（status=ok 時必填，繁體中文，80 字內）
  evidence_id: 依據的片段編號（例如 "片段1"）
"""

def ask(question, context):
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": NARRATIVE_PROMPT},
            {"role": "user", "content": f"問題：{question}\n\n財報資料片段：\n{context}"},
        ],
        "temperature": 0.0, "max_tokens": 512,
    }
    r = requests.post(VLLM, json=body, timeout=180)
    if r.status_code == 400:
        return {"status": "ctx_overflow", "raw": r.text[:160]}
    r.raise_for_status()
    txt = r.json()["choices"][0]["message"]["content"]
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        return json.loads(m.group(0)) if m else {"status": "parse_fail", "raw": txt[:200]}
    except Exception:
        return {"status": "parse_fail", "raw": txt[:200]}

MAX_CTX_CHARS = 5200   # Qwen3-4B max_model_len=4096 tokens，中文約 1.4 char/token

def fmt(chunks):
    """片段格式化並截斷至模型視窗內（僅取前 N 個片段、每段設上限）。"""
    parts, used = [], 0
    for i, c in enumerate(chunks, 1):
        body = c.get('content', '') or ''
        head = (f"[片段{i}] {c.get('company_name','')} {c.get('quarter','')} "
                f"表名：{c.get('table_name','')}\n")
        room = MAX_CTX_CHARS - used - len(head)
        if room <= 200:
            break
        parts.append(head + body[:room])
        used += len(head) + min(len(body), room)
    return "\n\n".join(parts)

res = json.load(open("results/robustness_routing_query.json"))
res = res["results"] if isinstance(res, dict) and "results" in res else res
c1 = [r for r in res if str(r["metadata"].get("subset", "")).startswith("C1")]
qs = json.load(open("questions/robustness_routing_subset.json"))
qs = qs if isinstance(qs, list) else qs.get("questions", qs)
qid = {q["question"]: q.get("id") for q in qs}

cli = chromadb.PersistentClient(path="vector_db")
col = cli.get_collection("financial_reports_md")

def oracle(code, quarter, table):
    got = col.get(where={"$and": [{"company_code": {"$eq": code}},
                                  {"quarter": {"$eq": quarter}}]},
                  include=["metadatas", "documents"])
    for m, d in zip(got["metadatas"], got["documents"]):
        if (m.get("table_name") or "") == table:
            return [{"company_name": m.get("company_name", ""), "quarter": quarter,
                     "table_name": table, "content": d}]
    return []

out = []
for r in c1:
    m = r["metadata"]
    rid = qid.get(r["question"], "?")
    top1_ok = bool(r.get("retrieved_chunks")) and \
        r["retrieved_chunks"][0].get("table_name") == m.get("source_table")
    if top1_ok:
        grp, chunks = "A_契約層", r["retrieved_chunks"]
    else:
        grp = "B_檢索層"
        chunks = oracle(m.get("company_code"), m.get("quarter"), m.get("source_table"))
    if not chunks:
        out.append({"id": rid, "group": grp, "probe": {"status": "no_chunk"}}); continue
    got = ask(r["question"], fmt(chunks))
    out.append({"id": rid, "group": grp, "question": r["question"],
                "company": m.get("company_name"), "quarter": m.get("quarter"),
                "source_table": m.get("source_table"),
                "system_answer": r.get("answer"),
                "system_mode": r.get("answer_mode"),
                "probe": got})
    print(f"[{rid}] {grp} → {got.get('status')} | {str(got.get('answer_text',''))[:70]}", flush=True)

json.dump(out, open("results/track2_diagnosis_probe.json", "w"),
          ensure_ascii=False, indent=2)
ok = sum(1 for o in out if o["probe"].get("status") == "ok")
print(f"\n=== 探針：{ok}/{len(out)} 作答（原系統 0/10）===")
for g in ("A_契約層", "B_檢索層"):
    sub = [o for o in out if o["group"] == g]
    print(f"  {g}: {sum(1 for o in sub if o['probe'].get('status')=='ok')}/{len(sub)}")
