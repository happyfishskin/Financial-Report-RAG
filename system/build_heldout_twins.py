#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out 孿生評測集生成器（build_heldout_twins.py）
====================================================
為五組主結果資料集各生成一份**同分布、但題目實例完全不重疊**的孿生集：

    dev（開發集，系統反覆修正所依據）              held-out 孿生集（本腳本產生）
    ─────────────────────────────────────────    ──────────────────────────────────
    system_architecture_test_questions_100_v4    heldout_arch_100.json
    customer_colloquial_test_questions_100_v2_v3 heldout_colloq_100.json
    customer_colloquial_natural_100              heldout_colloq_nat_100.json
    graph_capability_explicit                    heldout_graph_cap_30.json
    graph_routing_natural                        heldout_graph_nat_30.json

動機
────
現行主結果（架構 97.0%、口語 91.0%、純口語 100%、圖譜能力 100%、自然路由 100%）
全部量測在「系統曾據以反覆修正」的同一批題目上。Fix 1–17 的每一次迭代都看過這些
題目，因此這些數字是**開發集分數**，不足以支撐「本系統具備此準確率」的一般化宣稱。
孿生集把同一批模板、同一套金標方法論套用到**從未被任何修正看過的題目實例**上，
使 held-out 分數與開發集分數的落差可被直接量化。

三項設計約束
────────────
1. **同分布**：每組的題型組成、題數、題幹模板、金標格式與 dev 完全一致
   （逐型對照見 SPEC_ARCH / SPEC_COLLOQ）；僅抽樣實例不同。
2. **實例不重疊**：以語意主鍵（公司×期別×科目／交易三元鍵／被投資公司…）
   對 questions/ 下**全部** dev 題庫建立排除索引，抽樣時整組排除；
   另以正規化題幹字串做最後一道去重。
3. **金標零缺陷（生成時驗證）**：一律採 audit_datasets.py D1–D11 修正後之慣例——
   · 只取「當期欄」（欄位年 == 期別西元年），且該期當期欄之相異值必須唯一，
     否則整組候選丟棄（自動排除損益表 Q2/Q3 單季／累計並存的歧義組合）；
   · 跨期題採「各期均取該期當期欄」，metadata.column_header 為 {期別: 欄位} 字典
     （dev 的 R8 修正慣例），杜絕 D4「單一欄位標頭套用於兩期」；
   · 跨公司題所釘之欄位標頭其年份必須等於該期別西元年（避免 D2 比較欄）；
   · 排除「去年同期*」來源表（D7）、語料表頭誤併科目（D6）、非數值金標（D3）；
   · 圖譜題之鑑別子句必須在同公司同期唯一定位一列（沿用 dev 生成器同一判準）。

用法
────
    python3 build_heldout_twins.py                 # → questions/heldout/
    python3 build_heldout_twins.py --report        # 只印統計，不寫檔
    python3 build_heldout_twins.py --outdir DIR    # 指定輸出目錄
    python3 build_heldout_twins.py --project DIR   # 指定 version8 專案根目錄

產生後請執行 freeze_heldout_manifest.py 凍結預註冊 manifest（含 SHA256），
再依 manifest 所載指令跑 A3 全量評測。
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


def _arg(flag: str, default: str | None = None) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


ROOT = Path(_arg("--project", str(Path(__file__).resolve().parent))).resolve()
QDIR = ROOT / "questions"
OUTDIR = Path(_arg("--outdir", str(QDIR / "heldout"))).resolve()
FACTS = ROOT / "reports_csv_output" / "__all_company_all_period_numeric_facts.csv"
CHROMA = ROOT / "vector_db" / "chroma.sqlite3"

sys.path.insert(0, str(ROOT))

SEED = int(_arg("--seed", "20260726"))   # 孿生集抽樣種子（與任何 dev 生成器之種子皆不同）
# 第二份 held-out（`--ambig`）之候選歧義分層：獨立 RNG，不消耗主 rng 的抽樣序列，
# 故加上 --ambig 後前五組輸出仍與未加時逐位元相同（見 --verify-determinism）。
AMBIG = "--ambig" in sys.argv
# 第二份 held-out 須連同第一份一併排除，兩份才是互斥的獨立抽樣。
# 預設關閉 → 未加旗標時前五組輸出與凍結版逐位元相同。
EXCLUDE_HELDOUT = "--exclude-heldout" in sys.argv
AMBIG_SALT = 0x0A3B17
SPEC_AMBIG = {"investment_ambiguous": 30, "supply_chain_ambiguous": 30}

# ── 每組的題型組成（與 dev 逐型相同）────────────────────────────────────────
SPEC_ARCH = {
    "direct_numeric_lookup": 30,
    "cross_company_compare": 15,
    "cross_period_compare": 15,
    "vector_table_retrieval": 10,
    "investment_graph": 10,
    "related_party_transaction_graph": 8,
    "supply_chain_graph": 5,
    "risk_event_graph": 5,
    "mainland_investment_graph": 2,
}
SPEC_COLLOQ = {
    "colloquial_single_metric": 40,
    "colloquial_company_compare": 15,
    "colloquial_period_compare": 15,
    "colloquial_investment_question": 10,
    "colloquial_related_party_question": 10,
    "colloquial_supply_chain_question": 5,
    "colloquial_risk_question": 5,
}
N_COLLOQ_NAT = 100

# 口語單一指標題的 metric 配額（與 dev colloq v2_v3 相同）
COLLOQ_METRIC_QUOTA = {"cash": 12, "revenue": 12, "profit": 12, "assets": 4}

BROKEN_ITEMS = {
    "繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations",
}

_PERIOD_RE = re.compile(r"^(\d{3})Q([1-4])$")


# ══════════════════════════════════════════════════════════════════════
# 共用工具（與 audit_datasets.py 同語意）
# ══════════════════════════════════════════════════════════════════════
def roc_to_ad(period: str) -> int | None:
    m = _PERIOD_RE.match(str(period).strip())
    return int(m.group(1)) + 1911 if m else None


def col_years(col: str) -> set[int]:
    return {int(y) for y in re.findall(r"(20\d{2})", str(col))}


def norm_num(s) -> str | None:
    if s is None:
        return None
    t = str(s).strip()
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").strip().replace(",", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    v = float(t)
    return f"{-abs(v) if neg else v:.4f}"


def to_float(s) -> float | None:
    n = norm_num(s)
    return float(n) if n is not None else None


def norm_q(text: str) -> str:
    """題幹正規化（去空白與全形括號差異）供最終去重。"""
    return re.sub(r"[\s　（）()【】]", "", str(text))


# ══════════════════════════════════════════════════════════════════════
# 1. dev 題庫排除索引
# ══════════════════════════════════════════════════════════════════════
class Exclusions:
    """掃描 questions/*.json（不含 heldout/）建立語意主鍵排除索引。"""

    def __init__(self, qdir: Path, extra_dirs: "list[Path] | None" = None):
        self.dl: set = set()          # (code, period, item)
        self.cc: set = set()          # (frozenset(codes), period, item)
        self.cp: set = set()          # (code, frozenset(periods), item)
        self.vec: set = set()         # (code, period, table)
        self.inv: set = set()         # (company, period, investee/investor)
        self.rp: set = set()          # (company, period, payer, counterparty, account)
        self.sc: set = set()          # company_name
        self.risk: set = set()        # (company, period, item)
        self.ml: set = set()          # (company, period, investee)
        self.qtext: set = set()
        self.files: list[str] = []
        self.n_questions = 0

        scan = [qdir]
        # 第二份 held-out 需連同**第一份 held-out** 一併排除，兩份才算獨立抽樣。
        scan += list(extra_dirs or [])
        for d in scan:
            for p in sorted(d.glob("*.json")):
                data = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    continue
                self.files.append(p.name)
                self.n_questions += len(data)
                for q in data:
                    self._absorb(q)

    def _absorb(self, q: dict) -> None:
        md = q.get("metadata", {}) or {}
        t = str(q.get("question_type") or "")
        self.qtext.add(norm_q(q.get("question", "")))

        code = str(md.get("company_code") or "")
        name = str(md.get("company_name") or "")
        period = str(md.get("quarter") or "")
        item = str(md.get("item_name") or md.get("item_canonical") or "")
        codes = [str(c) for c in (md.get("companies") or []) if str(c)]
        periods = [str(p) for p in (md.get("periods") or []) if str(p)]

        # 數值型
        if item and period and code:
            self.dl.add((code, period, item))
        if codes and period and item:
            self.cc.add((frozenset(codes), period, item))
            for c in codes:
                self.dl.add((c, period, item))
        if code and len(periods) == 2 and item:
            self.cp.add((code, frozenset(periods), item))
            for p in periods:
                self.dl.add((code, p, item))
        # 純口語自然題以 metric 為鍵
        if md.get("metric") and code and period:
            self.dl.add((code, period, f"__metric__{md['metric']}"))

        # 向量定位題
        if "vector" in t and code and period and md.get("table_name"):
            self.vec.add((code, period, str(md["table_name"])))

        # 圖譜題（dev 各集的 company 鍵有時是代號、有時是名稱 → 兩者都放進去）
        who = [x for x in (code, name) if x]
        if md.get("investee_name"):
            tgt = self.ml if "mainland" in t else self.inv
            for w in who:
                tgt.add((w, period, str(md["investee_name"])))
        if md.get("investor_name"):
            for w in who:
                self.inv.add((w, period, str(md["investor_name"])))
        disc = md.get("discriminator")
        disc = disc if isinstance(disc, dict) else {}
        payer = md.get("transacting_party") or md.get("party_or_category") or md.get("payer")
        cpty = md.get("counterparty") or disc.get("value_2")
        acct = md.get("account_item") or disc.get("value_4")
        if payer:
            for w in who:
                self.rp.add((w, period, str(payer), str(cpty or ""), str(acct or "")))
                self.rp.add((w, period, str(payer), "", ""))   # 保守：同交易人整組排除
        if "supply" in t and name:
            self.sc.add(name)
        if "risk" in t and item:
            for w in who:
                self.risk.add((w, period, item))

    def summary(self) -> dict:
        return {
            "scanned_files": self.files,
            "scanned_questions": self.n_questions,
            "keys": {k: len(getattr(self, k)) for k in
                     ("dl", "cc", "cp", "vec", "inv", "rp", "sc", "risk", "ml", "qtext")},
        }


# ══════════════════════════════════════════════════════════════════════
# 2. 財報事實語料（當期欄唯一值）
# ══════════════════════════════════════════════════════════════════════
class Facts:
    def __init__(self, path: Path):
        df = pd.read_csv(path, dtype=str, low_memory=False,
                         keep_default_na=False, encoding="utf-8-sig")
        df.columns = [c.lstrip("﻿") for c in df.columns]
        df = df[df["value_raw"].str.strip() != ""]
        self.df = df
        self.name_of: dict[str, str] = {}
        self.code_of: dict[str, str] = {}
        self.idx: dict[tuple, list] = defaultdict(list)
        for r in df.itertuples(index=False):
            self.idx[(r.stock_code, r.period, r.table_name, r.item_name)].append(
                (r.column_header, r.value_raw, r.source_csv))
            self.name_of.setdefault(r.stock_code, r.company_name)
            self.code_of.setdefault(r.company_name, r.stock_code)
        self.periods = sorted(df["period"].unique())
        self.codes = sorted(df["stock_code"].unique())
        self._cur_cache: dict[tuple, tuple | None] = {}

    def current(self, code, period, table, item) -> tuple[str, str, str] | None:
        """
        回傳 (column_header, value_raw, source_csv)：該（公司,期別,表,科目）之
        **當期欄唯一值**；有歧義（多個相異值）、無當期欄、非數值、或屬去年同期
        來源表者一律回 None。
        """
        key = (code, period, table, item)
        if key in self._cur_cache:
            return self._cur_cache[key]
        out = self._current(code, period, table, item)
        self._cur_cache[key] = out
        return out

    def _current(self, code, period, table, item):
        if item in BROKEN_ITEMS or "去年同期" in str(table):
            return None
        ad = roc_to_ad(period)
        rows = self.idx.get((str(code), str(period), str(table), str(item)), [])
        hits = [(c, v, s) for c, v, s in rows
                if ad in col_years(c) and "去年同期" not in str(c)]
        if not hits:
            return None
        vals = {norm_num(v) for _c, v, _s in hits}
        if len(vals) != 1 or None in vals:
            return None
        return hits[0]

    def candidate_keys(self) -> list[tuple]:
        return list(self.idx.keys())


# ══════════════════════════════════════════════════════════════════════
# 3. 各題型生成器
# ══════════════════════════════════════════════════════════════════════
METRIC_KW = {
    "cash": ("現金及約當現金", "期末現金及約當現金餘額",
             "資產負債表帳列之現金及約當現金", "期初現金及約當現金餘額"),
    "revenue": ("營業收入合計", "營業收入"),
    "profit": ("本期淨利（淨損）", "營業毛利（毛損）", "營業利益（損失）"),
    "assets": ("資產總計",),
}
ORAL_STEMS = {
    "cash": ["幫我看一下{co}{q}現金水位是多少", "{co}在{q}的現金大概多少？",
             "{co}{q}手上現金有多少？"],
    "revenue": ["{co}{q}營收多少？", "幫我看一下{co}{q}的營業收入是多少",
                "{co}在{q}的營收大概多少？"],
    "profit": ["{co}{q}賺了多少？", "幫我看一下{co}{q}的獲利是多少",
               "{co}在{q}的淨利大概多少？"],
    "assets": ["{co}{q}資產規模多大？", "幫我看一下{co}{q}的資產總計"],
}


def gen_direct_lookup(facts: Facts, ex: Exclusions, rng: random.Random,
                      n: int, style: str, quota: dict | None = None) -> list[dict]:
    keys = facts.candidate_keys()
    rng.shuffle(keys)
    out: list[dict] = []
    per_company: Counter = Counter()
    got: Counter = Counter()
    cap_per_company = max(2, n // 8)
    for code, period, table, item in keys:
        if len(out) >= n:
            break
        if (code, period, item) in ex.dl:
            continue
        metric = None
        if quota is not None:
            for m, kws in METRIC_KW.items():
                if any(item.startswith(k) for k in kws):
                    metric = m
                    break
            if metric is None or got[metric] >= quota.get(metric, 0):
                continue
            # dev 題庫（含純口語自然集）以 (公司,期別,metric) 為題目實例：
            # 同一格指標即使換一個科目名，仍屬同一實例，一併排除。
            if (code, period, f"__metric__{metric}") in ex.dl:
                continue
        if per_company[code] >= cap_per_company:
            continue
        cur = facts.current(code, period, table, item)
        if cur is None:
            continue
        col, val, src = cur
        co = facts.name_of.get(code, code)
        if style == "arch":
            question = f"請查詢【{co}】在【{period}】的【{item}】（{col}）是多少？"
        else:
            stem = rng.choice(ORAL_STEMS[metric]).format(co=co, q=period)
            question = f"{stem}（科目：【{item}】）（表：【{table}】）（{col}）"
        if norm_q(question) in ex.qtext:
            continue
        md = {
            "target_route": "direct_lookup_or_vector",
            "company_code": code, "company_name": co, "quarter": period,
            "table_name": table, "item_name": item, "column_header": col,
            "source_csv": src,
        }
        if metric:
            md["metric"] = metric
            got[metric] += 1
            ex.dl.add((code, period, f"__metric__{metric}"))
        per_company[code] += 1
        ex.dl.add((code, period, item))
        ex.qtext.add(norm_q(question))
        out.append({
            "question_type": ("direct_numeric_lookup" if style == "arch"
                              else "colloquial_single_metric"),
            "question": question, "expected_answer": val, "metadata": md,
        })
    return out


def gen_cross_company(facts: Facts, ex: Exclusions, rng: random.Random,
                      n: int, style: str) -> list[dict]:
    """同期別、同科目、同一「當期欄」標頭下比較兩家公司。"""
    groups: dict[tuple, list] = defaultdict(list)
    for (code, period, table, item) in facts.candidate_keys():
        ad = roc_to_ad(period)
        cur = facts.current(code, period, table, item)
        if cur is None:
            continue
        col, val, _s = cur
        if ad not in col_years(col):
            continue
        groups[(period, table, item, col)].append((code, val))

    cands = [(k, v) for k, v in groups.items() if len(v) >= 2]
    rng.shuffle(cands)
    out: list[dict] = []
    used_items: Counter = Counter()
    cap_per_item = max(1, n // 5)
    for (period, table, item, col), members in cands:
        if len(out) >= n:
            break
        if used_items[item] >= cap_per_item:
            continue
        rng.shuffle(members)
        (ca, va), (cb, vb) = members[0], members[1]
        if (frozenset((ca, cb)), period, item) in ex.cc:
            continue
        if (ca, period, item) in ex.dl or (cb, period, item) in ex.dl:
            continue
        fa, fb = to_float(va), to_float(vb)
        if fa is None or fb is None or fa == fb:
            # 兩家同值時，只讀一欄即可得分，無法鑑別「是否真的分別查了兩家」
            continue
        na, nb = facts.name_of.get(ca, ca), facts.name_of.get(cb, cb)
        if na == nb:
            continue
        if style == "arch":
            question = (f"請比較【{na}】與【{nb}】在【{period}】的【{item}】"
                        f"（{col}）分別是多少？")
            gold = f"{na}: {va} ｜ {nb}: {vb}"
        else:
            if fa == fb:
                continue                      # 口語型需判斷「較高」，同值無意義
            winner = na if fa > fb else nb
            zh = item.split(" ")[0]
            stem = rng.choice([
                f"{na}跟{nb}在{period}的數字差多少？先列出兩家的數字",
                f"幫我比一下{na}和{nb}，{period}的{zh}各是多少？",
                f"{period}時，{na}和{nb}誰的{zh}比較高？",
            ])
            question = f"{stem}（科目：【{item}】）（{col}）"
            gold = f"{na}: {va} ｜ {nb}: {vb} ｜ 較高: {winner}"
        if norm_q(question) in ex.qtext:
            continue
        ex.cc.add((frozenset((ca, cb)), period, item))
        ex.dl.add((ca, period, item))
        ex.dl.add((cb, period, item))
        ex.qtext.add(norm_q(question))
        used_items[item] += 1
        out.append({
            "question_type": ("cross_company_compare" if style == "arch"
                              else "colloquial_company_compare"),
            "question": question, "expected_answer": gold,
            "metadata": {
                "target_route": "direct_lookup_multi_company",
                "quarter": period, "table_name": table, "item_name": item,
                "column_header": col, "companies": [ca, cb],
            },
        })
    return out


def gen_cross_period(facts: Facts, ex: Exclusions, rng: random.Random,
                     n: int, style: str) -> list[dict]:
    """同公司同科目、兩期別各取「該期當期欄」（dev 之 R8 修正慣例）。"""
    by_ci: dict[tuple, list] = defaultdict(list)
    for (code, period, table, item) in facts.candidate_keys():
        cur = facts.current(code, period, table, item)
        if cur is None:
            continue
        by_ci[(code, table, item)].append((period, cur[0], cur[1]))

    cands = [(k, v) for k, v in by_ci.items() if len(v) >= 2]
    rng.shuffle(cands)
    out: list[dict] = []
    used_items: Counter = Counter()
    cap_per_item = max(1, n // 5)
    for (code, table, item), plist in cands:
        if len(out) >= n:
            break
        if used_items[item] >= cap_per_item:
            continue
        pl = list(plist)
        rng.shuffle(pl)
        (p1, c1, v1), (p2, c2, v2) = sorted(pl[:2])
        if c1 == c2:
            continue                       # 兩期必須各有自己的當期欄
        if (code, frozenset((p1, p2)), item) in ex.cp:
            continue
        if (code, p1, item) in ex.dl or (code, p2, item) in ex.dl:
            continue
        f1, f2 = to_float(v1), to_float(v2)
        if f1 is None or f2 is None or f1 == f2:
            # 兩期同值時，照抄同一欄即可得分（audit R8 所指之退化情形）
            continue
        co = facts.name_of.get(code, code)
        trend = "上升" if f2 > f1 else "下降"
        if style == "arch":
            question = (f"請比較【{co}】在【{p1}】與【{p2}】的【{item}】"
                        f"各是多少（各期均取該期當期欄）？")
            gold = f"{p1}: {v1} ｜ {p2}: {v2}"
        else:
            zh = item.split(" ")[0]
            stem = rng.choice([
                f"幫我看{co}{p1}跟{p2}的{zh}差異",
                f"{co}這兩季({p1}、{p2})的{zh}各是多少？",
                f"{co}從{p1}到{p2}，{zh}有變多嗎？",
            ])
            question = f"{stem}（科目：【{item}】）（各期均取該期當期欄）？"
            gold = f"{p1}: {v1} ｜ {p2}: {v2} ｜ 趨勢: {trend}"
        if norm_q(question) in ex.qtext:
            continue
        ex.cp.add((code, frozenset((p1, p2)), item))
        ex.dl.add((code, p1, item))
        ex.dl.add((code, p2, item))
        ex.qtext.add(norm_q(question))
        used_items[item] += 1
        out.append({
            "question_type": ("cross_period_compare" if style == "arch"
                              else "colloquial_period_compare"),
            "question": question, "expected_answer": gold,
            "metadata": {
                "target_route": "direct_lookup_multi_period",
                "company_code": code, "company_name": co,
                "periods": [p1, p2], "table_name": table, "item_name": item,
                "column_header": {p1: c1, p2: c2},
            },
        })
    return out


def gen_vector_table(ex: Exclusions, rng: random.Random, n: int) -> list[dict]:
    """向量表格定位題：金標取自 ChromaDB metadata（系統實際查詢的同一索引）。"""
    if not CHROMA.exists():
        print("  [warn] 找不到 vector_db/chroma.sqlite3，略過向量題")
        return []
    con = sqlite3.connect(str(CHROMA))
    rows = con.execute(
        "select id, key, string_value from embedding_metadata "
        "where key in ('company_code','quarter','table_name','source','company_name')"
    ).fetchall()
    con.close()
    recs: dict[int, dict] = defaultdict(dict)
    for rid, k, v in rows:
        if v is not None:
            recs[rid][k] = v
    trip: dict[tuple, set] = defaultdict(set)
    names: dict[str, str] = {}
    for m in recs.values():
        code, q, tbl, src = (m.get("company_code"), m.get("quarter"),
                             m.get("table_name"), m.get("source"))
        if code and q and tbl and src:
            trip[(code, q, tbl)].add(src)
            if m.get("company_name"):
                names.setdefault(code, m["company_name"])

    keys = sorted(k for k, v in trip.items() if len(v) == 1)
    rng.shuffle(keys)
    out: list[dict] = []
    per_company: Counter = Counter()
    cap = max(1, n // 5)
    for code, quarter, tbl in keys:
        if len(out) >= n:
            break
        if (code, quarter, tbl) in ex.vec:
            continue
        if per_company[code] >= cap:
            continue
        # 表名須為中文且長度足夠（系統以精確比對優先命中）
        if not re.search(r"[一-鿿]", tbl) or len(tbl) < 3:
            continue
        src = next(iter(trip[(code, quarter, tbl)]))
        co = names.get(code, code)
        question = (f"請從向量檢索的 Markdown 表格中找出【{co}】【{quarter}】的"
                    f"【{tbl}】表，並說明這張表主要揭露哪類財報資訊。")
        if norm_q(question) in ex.qtext:
            continue
        ex.vec.add((code, quarter, tbl))
        ex.qtext.add(norm_q(question))
        per_company[code] += 1
        out.append({
            "question_type": "vector_table_retrieval",
            "question": question,
            "expected_answer": f"應檢索到來源表 {src}；表名為「{tbl}」。",
            "metadata": {
                "target_route": "vector_search", "company_code": code,
                "company_name": co, "quarter": quarter, "table_name": tbl,
                "source_md": src,
            },
        })
    return out


# ── 圖譜題（沿用 generate_graph_routing_natural_100.py 之判準）──────────────
def gen_investment(v14, nodes, edges, ex: Exclusions, rng: random.Random,
                   n: int, style: str) -> list[dict]:
    inv = edges[edges["type"] == "INVESTS_IN"].copy()
    out: list[dict] = []
    groups = list(inv.groupby(["report_company_name", "report_period", "source"]))
    rng.shuffle(groups)
    for (co, period, src), g in groups:
        if len(out) >= n:
            break
        if not co or not period:
            continue
        investor = v14._gkg_resolve_node_name(src, nodes)
        if not investor:
            continue
        for field, label in (("location", "所在地為"), ("main_business", "主要業務為")):
            if field not in g.columns:
                continue
            vc = g[field].fillna("").value_counts()
            uniq = sorted(val for val, c in vc.items() if val and c == 1)
            if not uniq:
                continue
            val = rng.choice(uniq)
            row = g[g[field] == val].iloc[0]
            investee = v14._gkg_resolve_node_name(row["target"], nodes)
            if not investee or len(str(val)) < 3:
                continue
            if ((co, period, investee) in ex.inv or (co, period, investor) in ex.inv):
                continue
            if style == "arch":
                question = (f"根據投資關係圖譜，【{co}】在【{period}】揭露的投資方"
                            f"【{investor}】投資了哪一家{label}【{val}】的被投資公司？")
            else:
                question = (f"{co}在{period}揭露的被投資公司裡，{investor}投到誰？"
                            f"（我指的是{label}【{val}】的那一家）")
            if norm_q(question) in ex.qtext:
                continue
            ex.inv.add((co, period, investee))
            ex.inv.add((co, period, investor))
            ex.qtext.add(norm_q(question))
            out.append({
                "question_type": ("investment_graph" if style == "arch"
                                  else "colloquial_investment_question"),
                "question": question, "expected_answer": investee,
                "metadata": {"target_route": "graph_rag_investment",
                             "company_name": co, "quarter": period,
                             "investor_name": investor, "investee_name": investee,
                             "discriminator": {"column": field, "value": val}},
            })
            break
    return out[:n]


def gen_related_party(rp, ex: Exclusions, rng: random.Random,
                      n: int, style: str) -> list[dict]:
    sub = rp[rp["amount_summary"].fillna("").str.contains("value_2=", regex=False)].copy()
    # 大陸投資列另有專屬題型（D10：來源表決定 question_type）
    sub = sub[~sub["source_csv"].fillna("").str.contains("大陸", na=False)]
    kv = re.compile(r"(value_\d+)=([^;]+)")
    out: list[dict] = []
    rows = list(sub.itertuples(index=False))
    rng.shuffle(rows)
    for r in rows:
        if len(out) >= n:
            break
        d = dict(kv.findall(str(r.amount_summary)))
        payer = str(r.party_or_category or "").strip()
        counterparty = d.get("value_2", "").strip()
        account = d.get("value_4", "").strip()
        amount = d.get("value_5", "").strip()
        if not (payer and counterparty and account and amount):
            continue
        if to_float(amount) is None:
            continue
        same = sub[(sub.report_stock_id == r.report_stock_id)
                   & (sub.report_period == r.report_period)
                   & (sub.party_or_category.fillna("").str.strip() == payer)
                   & sub.amount_summary.fillna("").str.contains(
                       re.escape(f"value_2={counterparty}"), regex=True)
                   & sub.amount_summary.fillna("").str.contains(
                       re.escape(f"value_4={account}"), regex=True)]
        if len(same) != 1:
            continue
        co, period = r.report_company_name, r.report_period
        if ((co, period, payer, counterparty, account) in ex.rp
                or (co, period, payer, "", "") in ex.rp):
            continue
        if style == "arch":
            question = (f"根據關係人交易圖譜，【{co}】在【{period}】，【{payer}】與"
                        f"【{counterparty}】之間的【{account}】交易金額是多少？")
        else:
            question = (f"幫我看{co}{period}關係人交易裡，{payer}跟{counterparty}"
                        f"之間的{account}交易金額是多少？")
        if norm_q(question) in ex.qtext:
            continue
        ex.rp.add((co, period, payer, counterparty, account))
        ex.rp.add((co, period, payer, "", ""))
        ex.qtext.add(norm_q(question))
        out.append({
            "question_type": ("related_party_transaction_graph" if style == "arch"
                              else "colloquial_related_party_question"),
            "question": question, "expected_answer": amount,
            "metadata": {"target_route": "graph_rag_related_party",
                         "company_name": co, "quarter": period,
                         "party_or_category": payer,
                         "transacting_party": payer, "counterparty": counterparty,
                         "account_item": account,
                         "source_csv": str(r.source_csv),
                         "discriminator": {"value_2": counterparty,
                                           "value_4": account}},
        })
    return out[:n]


def gen_mainland(rp, ex: Exclusions, rng: random.Random, n: int) -> list[dict]:
    ml = rp[rp["source_csv"].fillna("").str.contains("大陸", na=False)].copy()
    out: list[dict] = []
    groups = list(ml.groupby(["report_company_name", "report_period"]))
    rng.shuffle(groups)
    for (co, period), g in groups:
        if len(out) >= n or not co:
            continue
        vc = g["account"].fillna("").value_counts()
        uniq = [b for b, c in vc.items() if b and c == 1 and len(str(b)) >= 4]
        rng.shuffle(uniq)
        for biz in uniq[:1]:
            row = g[g["account"] == biz].iloc[0]
            investee = str(row["party_or_category"] or "").strip()
            m = re.search(r"本期認列投資損益\s*=\s*([^;]+)", str(row["amount_summary"]))
            profit = m.group(1).strip() if m else ""
            if not (investee and profit):
                continue
            if (co, period, investee) in ex.ml:
                continue
            question = (f"根據大陸投資圖譜，【{co}】在【{period}】投資之大陸事業中，"
                        f"主要業務為【{biz}】的被投資公司是哪一家？"
                        f"其本期認列投資損益是多少？")
            if norm_q(question) in ex.qtext:
                continue
            ex.ml.add((co, period, investee))
            ex.qtext.add(norm_q(question))
            out.append({
                "question_type": "mainland_investment_graph",
                "question": question,
                "expected_answer": f"{investee}；本期認列投資損益：{profit}",
                "metadata": {"target_route": "graph_rag_mainland_investment",
                             "company_name": co, "quarter": period,
                             "main_business": biz, "investee_name": investee,
                             "value_attribute": "本期認列投資損益",
                             "value_raw": profit,
                             "source_csv": str(row["source_csv"])},
            })
    return out[:n]


def gen_supply_chain(ex: Exclusions, rng: random.Random,
                     n: int, style: str) -> list[dict]:
    p = ROOT / "supply_chain_graph_output" / "company_table.csv"
    df = pd.read_csv(p, dtype=str)
    df.columns = [c.lstrip("﻿") for c in df.columns]
    stage_seg: dict[str, set] = defaultdict(set)
    for r in df.itertuples(index=False):
        co = str(getattr(r, "company_name", "") or "").strip()
        stage = str(getattr(r, "stage", "") or "").strip()
        seg = str(getattr(r, "segment", "") or "").strip()
        if co and stage and stage.lower() != "nan":
            stage_seg[co].add((stage, seg))
    rows = list(df.itertuples(index=False))
    rng.shuffle(rows)
    out, seen = [], set()
    for r in rows:
        if len(out) >= n:
            break
        co = str(getattr(r, "company_name", "") or "").strip()
        stage = str(getattr(r, "stage", "") or "").strip()
        seg = str(getattr(r, "segment", "") or "").strip()
        if (not (co and stage) or co in seen or co in ex.sc or len(co) < 2
                or stage.lower() == "nan" or len(stage_seg.get(co, ())) != 1):
            continue
        seen.add(co)
        ans = f"{stage}；{seg}" if seg and seg.lower() != "nan" else stage
        if style == "arch":
            question = f"根據半導體產業鏈圖譜，【{co}】屬於哪個產業鏈階段與 segment？"
        else:
            question = rng.choice([f"{co}在產業鏈圖譜裡被分到哪個類別？",
                                   f"{co}在半導體產業鏈算哪一段？"])
        if norm_q(question) in ex.qtext:
            continue
        ex.sc.add(co)
        ex.qtext.add(norm_q(question))
        out.append({
            "question_type": ("supply_chain_graph" if style == "arch"
                              else "colloquial_supply_chain_question"),
            "question": question, "expected_answer": ans,
            "metadata": {"target_route": "graph_rag_supply_chain",
                         "company_name": co, "stage": stage, "segment": seg},
        })
    return out


def gen_risk(v14, nodes, edges, ex: Exclusions, rng: random.Random,
             n: int, style: str) -> list[dict]:
    ev = nodes[nodes["label"].fillna("") == "RiskEvidence"].copy()
    ev_edges = edges[edges["type"] == "EVIDENCES"]
    tgt_name: dict = {}
    out: list[dict] = []
    groups = list(ev.groupby(["company_name", "period", "item_name"]))
    rng.shuffle(groups)
    for (co, period, item), g in groups:
        if len(out) >= n:
            break
        if not (co and period and item):
            continue
        m = re.match(r"(\d{4})Q([1-4])", str(period))
        roc_period = (f"{int(m.group(1)) - 1911}Q{m.group(2)}" if m
                      else (str(period) if _PERIOD_RE.match(str(period)) else None))
        if not roc_period:
            continue
        if (co, roc_period, item) in ex.risk:
            continue
        labels: list[str] = []
        for eid in g["id"]:
            for t in ev_edges[ev_edges["source"] == eid]["target"]:
                nm = tgt_name.setdefault(t, v14._gkg_resolve_node_name(t, nodes))
                if nm and nm not in labels:
                    labels.append(nm)
        if not labels:
            continue
        zh = re.match(r"[^A-Za-z]*", str(item)).group(0).strip()
        if len(zh) < 3:
            continue
        if style == "arch":
            question = (f"根據風險事件圖譜，【{co}】在【{roc_period}】的財務科目"
                        f"【{item}】被標記為哪一類風險候選？")
        else:
            question = rng.choice([
                f"{co}在{roc_period}的{item}，系統會標成什麼風險候選？",
                f"幫我判斷{co}{roc_period}的{item}會被歸到哪種財報風險？",
            ])
        if norm_q(question) in ex.qtext:
            continue
        ex.risk.add((co, roc_period, item))
        ex.qtext.add(norm_q(question))
        out.append({
            "question_type": ("risk_event_graph" if style == "arch"
                              else "colloquial_risk_question"),
            "question": question, "expected_answer": ";".join(labels),
            "metadata": {"target_route": "graph_rag_risk_event",
                         "company_name": co, "quarter": roc_period,
                         "item_name": item, "matched_risks": ";".join(labels)},
        })
    return out[:n]


# ── 純口語自然題（沿用 generate_colloquial_natural_100.py 之金標策略）──────
COMPANY_ALIASES: dict[str, str] = {
    "台積電": "台灣積體電路製造", "聯電": "聯華電子", "聯發科": "聯發科技",
    "聯詠": "聯詠科技", "瑞昱": "瑞昱半導體", "南亞科": "南亞科技",
    "華邦電": "華邦電子", "日月光": "日月光投資控股", "日月光投控": "日月光投資控股",
    "大聯大": "大聯大控股", "世界先進": "世界先進積體電路",
    "力積電": "力晶積成電子製造", "群聯": "群聯電子", "穩懋": "穩懋半導體",
    "環球晶": "環球晶圓", "京元電": "京元電子", "智原": "智原科技",
    "景碩": "景碩科技", "京鼎": "京鼎精密科技", "力旺": "力旺電子",
    "力成": "力成科技", "祥碩": "祥碩科技", "旺矽": "旺矽科技",
    "辛耘": "辛耘企業", "家登": "家登精密工業", "致茂": "致茂電子",
    "達興": "達興材料", "中華精測": "中華精測科技", "創意電子": "創意電子",
    "台灣光罩": "台灣光罩", "新應材": "新應材",
}

ITEM_SPECS: list[dict] = [
    {"canonical": "營業收入合計", "table": "損益", "metric": "revenue",
     "templates": ["{co}{q}營收多少？", "{co}{q}的營收是多少啊？",
                   "想知道{co}在{q}的營業收入有多少", "幫我看一下{co}{q}營收",
                   "欸 {co}{q}業績做了多少？"]},
    {"canonical": "本期淨利（淨損）", "table": "損益", "metric": "net_income",
     "templates": ["{co}{q}賺了多少錢？", "{co}{q}淨利多少？",
                   "幫我查{co}{q}賺多少", "{co}在{q}稅後賺了多少啊？"]},
    {"canonical": "營業毛利（毛損）", "table": "損益", "metric": "gross_profit",
     "templates": ["{co}{q}毛利多少？", "幫我看{co}{q}的毛利",
                   "{co}在{q}毛利做了多少啊？"]},
    {"canonical": "營業利益（損失）", "table": "損益", "metric": "op_income",
     "templates": ["{co}{q}本業賺多少？", "{co}{q}營業利益多少？",
                   "想知道{co}{q}本業獲利多少"]},
    {"canonical": "基本每股盈餘（虧損）", "table": "損益", "metric": "eps",
     "templates": ["{co}{q}EPS多少？", "{co}{q}每股賺多少？",
                   "幫我查一下{co}{q}的每股盈餘"]},
    {"canonical": "資產總計", "table": "資產負債", "metric": "total_assets",
     "templates": ["{co}{q}總資產多少？", "{co}在{q}資產規模多大？",
                   "幫我看{co}{q}的資產總額"]},
    {"canonical": "負債總計", "table": "資產負債", "metric": "total_liabilities",
     "templates": ["{co}{q}總負債多少？", "{co}{q}欠了多少錢？",
                   "想知道{co}{q}負債有多少"]},
    {"canonical": "權益總計", "table": "資產負債", "metric": "total_equity",
     "templates": ["{co}{q}股東權益多少？", "{co}{q}淨值多少？",
                   "幫我查{co}{q}的權益總計"]},
    {"canonical": "現金及約當現金", "table": "資產負債", "metric": "cash",
     "templates": ["{co}{q}手上現金有多少？", "{co}{q}現金水位多少？",
                   "欸 {co}{q}帳上現金還剩多少啊？", "{co}{q}現金部位多大？"]},
    {"canonical": "營業活動之淨現金流入（流出）", "table": "現金流量", "metric": "cfo",
     "templates": ["{co}{q}營業活動現金流多少？", "{co}{q}本業現金流進來多少？",
                   "幫我看{co}{q}營運現金流量"]},
]


def gen_colloq_natural(facts: Facts, ex: Exclusions, rng: random.Random,
                       n: int) -> list[dict]:
    df = facts.df
    pool: list[dict] = []
    for alias, full in COMPANY_ALIASES.items():
        code = facts.code_of.get(full)
        if not code:
            continue
        for q in facts.periods:
            for spec in ITEM_SPECS:
                if (code, q, f"__metric__{spec['metric']}") in ex.dl:
                    continue
                pat = re.escape(spec["canonical"]) + r"(?:[^一-鿿]|$)"
                sub = df[(df["stock_code"] == code) & (df["period"] == q)
                         & df["table_name"].str.contains(spec["table"], na=False)
                         & df["item_name"].str.match(pat, na=False)]
                if sub.empty:
                    continue
                cur = sub[sub["column_header"].str.contains(
                    str(roc_to_ad(q)), na=False)]
                if cur.empty:
                    continue
                vals = {v.strip() for v in cur["value_raw"]}
                if len(vals) != 1:
                    continue
                row = cur.iloc[0]
                pool.append({"alias": alias, "full": full, "code": code,
                             "quarter": q, "spec": spec,
                             "gold": {"value": row["value_raw"].strip(),
                                      "table_name": row["table_name"],
                                      "column_header": row["column_header"]}})
    by_metric: dict[str, list] = defaultdict(list)
    for c in pool:
        by_metric[c["spec"]["metric"]].append(c)
    print(f"  純口語可抽樣池（已扣除 dev 佔用）：{len(pool)} 組 / "
          f"{len(by_metric)} 種 metric")
    per = max(1, n // max(1, len(by_metric)))
    chosen, used = [], set()
    for metric in sorted(by_metric):
        cands = by_metric[metric]
        rng.shuffle(cands)
        cnt = 0
        for c in cands:
            key = (c["code"], c["quarter"], metric)
            if key in used:
                continue
            used.add(key)
            chosen.append(c)
            cnt += 1
            if cnt >= per:
                break
    rest = [c for m in by_metric.values() for c in m
            if (c["code"], c["quarter"], c["spec"]["metric"]) not in used]
    rng.shuffle(rest)
    while len(chosen) < n and rest:
        c = rest.pop()
        key = (c["code"], c["quarter"], c["spec"]["metric"])
        if key in used:
            continue
        used.add(key)
        chosen.append(c)
    chosen = chosen[:n]
    rng.shuffle(chosen)

    out = []
    for c in chosen:
        question = rng.choice(c["spec"]["templates"]).format(
            co=c["alias"], q=c["quarter"])
        if norm_q(question) in ex.qtext:
            continue
        ex.qtext.add(norm_q(question))
        out.append({
            "question_type": "colloquial_natural",
            "question_style": "customer_colloquial_natural",
            "question": question,
            "expected_answer": c["gold"]["value"],
            "metadata": {
                "target_route": "direct_lookup_or_vector",
                "metric": c["spec"]["metric"], "company_alias": c["alias"],
                "company_name": c["full"], "company_code": c["code"],
                "quarter": c["quarter"],
                "item_canonical": c["spec"]["canonical"],
                "item_name": c["spec"]["canonical"],
                "table_name": c["gold"]["table_name"],
                "column_header": c["gold"]["column_header"],
            },
        })
    return out


# ══════════════════════════════════════════════════════════════════════
# 4. 由 arch 孿生集之圖譜子集派生能力題／自然路由題（與 build_canonical_v4 同法）
# ══════════════════════════════════════════════════════════════════════
_SOURCE_HINT_RE = re.compile(r"^根據[^，]{2,12}圖譜，")
_GRAPH_TYPES = ("investment_graph", "related_party_transaction_graph",
                "supply_chain_graph", "risk_event_graph",
                "mainland_investment_graph")


def to_natural(question: str) -> str:
    q = _SOURCE_HINT_RE.sub("", question).strip()
    return q.replace("【", "").replace("】", "")


def derive_graph_sets(arch: list[dict]) -> tuple[list[dict], list[dict]]:
    graph_qs = [q for q in arch if q.get("question_type") in _GRAPH_TYPES]
    cap, nat = [], []
    for i, q in enumerate(graph_qs, 1):
        c = json.loads(json.dumps(q, ensure_ascii=False))
        c["id"] = f"ho_graph_cap_{i:03d}"
        c.setdefault("metadata", {})["force_route"] = "graph_rag"
        c["metadata"]["test_purpose"] = "graph_capability"
        c["metadata"]["heldout_twin_of"] = "graph_capability_explicit.json"
        cap.append(c)

        nrec = json.loads(json.dumps(q, ensure_ascii=False))
        nrec["id"] = f"ho_graph_nat_{i:03d}"
        nrec["question"] = to_natural(nrec["question"])
        nrec.setdefault("metadata", {})["test_purpose"] = "graph_routing"
        nrec["metadata"]["expected_route"] = "graph_rag"
        nrec["metadata"]["heldout_twin_of"] = "graph_routing_natural.json"
        nat.append(nrec)
    return cap, nat


# ══════════════════════════════════════════════════════════════════════
EXPECT = {"heldout_ambig_60.json": sum(SPEC_AMBIG.values()),
          "heldout_arch_100.json": 100, "heldout_colloq_100.json": 100,
          "heldout_colloq_nat_100.json": 100, "heldout_graph_cap_30.json": 30,
          "heldout_graph_nat_30.json": 30}


# ══════════════════════════════════════════════════════════════════════
# 候選歧義分層（第二份 held-out 專用；`--ambig`）
# ══════════════════════════════════════════════════════════════════════
# 第一份孿生集之生成判準要求「鑑別子句必須唯一定位一列」（見本檔開頭第 3 條），
# 因此**構造上**不可能含候選不唯一的題目——`measure_relation_ambiguity.py` 量得
# 第一份 held-out 四組候選歧義率 0.0%，是規則的必然，不是系統的表現。
#
# 本分層刻意抽「候選本來就不唯一」的實例，並採 **A 案語意：全部列出才算對**：
#   · 題幹明寫「請全部列出」，不給鑑別子句；
#   · 金標為全部候選之**集合**（`metadata.expected_set`），評分順序無關；
#   · `expected_answer` 以系統之全列並列格式 `" ｜ ".join(...)` 正規化書寫，
#     使字串 EM 與集合 EM 可並列報告（兩者差距即「順序／格式」造成的低估）。
#
# 兩個子分層的機制對照（預註冊時據此寫預測）：
#   supply_chain_ambiguous → 系統**有**全列並列分支（Fix 9，gate 為題幹含「全部列出」）
#   investment_ambiguous   → 系統**無**全列分支，`_gkg_pattern_direct_answer` 取
#                            `inv.iloc[-1]["target"]`（單一被投資公司）
def gen_investment_ambiguous(v14, nodes, edges, ex: Exclusions,
                             rng: random.Random, n: int) -> list[dict]:
    """投資關係多候選題：同一（公司, 期別, 投資方）揭露 ≥2 家被投資公司。"""
    inv = edges[edges["type"] == "INVESTS_IN"].copy()
    out: list[dict] = []
    groups = list(inv.groupby(["report_company_name", "report_period", "source"]))
    rng.shuffle(groups)
    for (co, period, src), g in groups:
        if len(out) >= n:
            break
        if not co or not period:
            continue
        investor = v14._gkg_resolve_node_name(src, nodes)
        if not investor:
            continue
        names: list[str] = []
        for t in dict.fromkeys(g["target"].tolist()):
            nm = v14._gkg_resolve_node_name(t, nodes)
            if nm and nm not in names:
                names.append(nm)
        if len(names) < 2:                      # 本分層只要多候選
            continue
        if (co, period, investor) in ex.inv:
            continue
        if any((co, period, nm) in ex.inv for nm in names):
            continue
        question = (f"根據投資關係圖譜，【{co}】在【{period}】揭露的投資方"
                    f"【{investor}】投資了哪些被投資公司？請全部列出。")
        if norm_q(question) in ex.qtext:
            continue
        ex.inv.add((co, period, investor))
        for nm in names:
            ex.inv.add((co, period, nm))
        ex.qtext.add(norm_q(question))
        gold = sorted(names)
        out.append({
            "question_type": "investment_ambiguous",
            "question": question,
            "expected_answer": " ｜ ".join(gold),
            "metadata": {"target_route": "graph_rag_investment",
                         "company_name": co, "quarter": period,
                         "investor_name": investor,
                         "answer_semantics": "set", "set_delimiter": "｜",
                         "expected_set": gold, "n_candidates": len(gold),
                         "system_has_listall_branch": False},
        })
    return out[:n]


def gen_supply_chain_ambiguous(ex: Exclusions, rng: random.Random,
                               n: int) -> list[dict]:
    """產業鏈多階段題：同一公司橫跨 ≥2 個 (stage, segment) 組合。"""
    p = ROOT / "supply_chain_graph_output" / "company_table.csv"
    df = pd.read_csv(p, dtype=str)
    df.columns = [c.lstrip("\ufeff") for c in df.columns]
    stage_seg: dict[str, list] = defaultdict(list)
    for r in df.itertuples(index=False):
        co = str(getattr(r, "company_name", "") or "").strip()
        stage = str(getattr(r, "stage", "") or "").strip()
        seg = str(getattr(r, "segment", "") or "").strip()
        if not (co and stage) or stage.lower() == "nan":
            continue
        # segment 缺值會使金標與系統輸出格式不一致（系統寫 "階段；segment"），
        # 本分層僅取兩者皆完整者，避免量到格式差異而非能力差異。
        if not seg or seg.lower() == "nan":
            continue
        combo = f"{stage}；{seg}"
        if combo not in stage_seg[co]:
            stage_seg[co].append(combo)
    cands = sorted(co for co, v in stage_seg.items() if len(v) >= 2 and len(co) >= 2)
    rng.shuffle(cands)
    out: list[dict] = []
    for co in cands:
        if len(out) >= n:
            break
        if co in ex.sc:
            continue
        question = (f"根據半導體產業鏈圖譜，【{co}】涵蓋哪些產業鏈階段與 "
                    f"segment？請全部列出。")
        if norm_q(question) in ex.qtext:
            continue
        ex.sc.add(co)
        ex.qtext.add(norm_q(question))
        gold = sorted(stage_seg[co])
        out.append({
            "question_type": "supply_chain_ambiguous",
            "question": question,
            "expected_answer": " ｜ ".join(gold),
            "metadata": {"target_route": "graph_rag_supply_chain",
                         "company_name": co,
                         "answer_semantics": "set", "set_delimiter": "｜",
                         "expected_set": gold, "n_candidates": len(gold),
                         "system_has_listall_branch": True},
        })
    return out[:n]


def build_ambig(v14, nodes, edges) -> list[dict]:
    """候選歧義分層：獨立 RNG（不影響前五組），排除索引含第一份 held-out。"""
    rng = random.Random(SEED ^ AMBIG_SALT)
    ex = Exclusions(QDIR, extra_dirs=[QDIR / "heldout"])
    print(f"  排除索引（含第一份 held-out）：{len(ex.files)} 檔 / "
          f"{ex.n_questions} 題")
    amb = gen_investment_ambiguous(v14, nodes, edges, ex, rng,
                                   SPEC_AMBIG["investment_ambiguous"])
    amb += gen_supply_chain_ambiguous(ex, rng,
                                      SPEC_AMBIG["supply_chain_ambiguous"])
    order = list(SPEC_AMBIG)
    amb.sort(key=lambda q: order.index(q["question_type"]))
    for i, q in enumerate(amb, 1):
        q["id"] = f"ho2_ambig_{i:03d}"
        q["metadata"]["heldout_stratum"] = "candidate_ambiguity"
        q["metadata"]["gold_semantics"] = "A：全部列出才算對（集合相等，順序無關）"
    return amb


def build(report_only: bool = False) -> dict:
    rng = random.Random(SEED)
    print("▶ 載入 dev 題庫排除索引 …")
    ex = Exclusions(QDIR,
                    extra_dirs=[QDIR / "heldout"] if EXCLUDE_HELDOUT else None)
    s = ex.summary()
    print(f"  掃描 {len(s['scanned_files'])} 個題庫、{s['scanned_questions']} 題")
    print(f"  語意主鍵：{s['keys']}")

    print("▶ 載入財報事實語料 …")
    facts = Facts(FACTS)
    print(f"  {len(facts.df):,} 筆事實、{len(facts.codes)} 家公司、"
          f"{len(facts.periods)} 個期別")

    print("▶ 載入圖譜 …")
    import rag_test_system_v14 as v14        # noqa: E402
    nodes, edges = v14._load_all_compiled_graphs()
    rp = pd.read_csv(ROOT / "related_party_graph_output"
                     / "related_party_transaction_table.csv", dtype=str)
    rp.columns = [c.lstrip("﻿") for c in rp.columns]

    # ── arch 孿生集 ────────────────────────────────────────────────
    print("▶ 生成 heldout_arch_100 …")
    arch: list[dict] = []
    arch += gen_direct_lookup(facts, ex, rng, SPEC_ARCH["direct_numeric_lookup"], "arch")
    arch += gen_cross_company(facts, ex, rng, SPEC_ARCH["cross_company_compare"], "arch")
    arch += gen_cross_period(facts, ex, rng, SPEC_ARCH["cross_period_compare"], "arch")
    arch += gen_vector_table(ex, rng, SPEC_ARCH["vector_table_retrieval"])
    arch += gen_investment(v14, nodes, edges, ex, rng,
                           SPEC_ARCH["investment_graph"], "arch")
    arch += gen_related_party(rp, ex, rng,
                              SPEC_ARCH["related_party_transaction_graph"], "arch")
    arch += gen_supply_chain(ex, rng, SPEC_ARCH["supply_chain_graph"], "arch")
    arch += gen_risk(v14, nodes, edges, ex, rng, SPEC_ARCH["risk_event_graph"], "arch")
    arch += gen_mainland(rp, ex, rng, SPEC_ARCH["mainland_investment_graph"])
    order = list(SPEC_ARCH)
    arch.sort(key=lambda q: order.index(q["question_type"]))
    for i, q in enumerate(arch, 1):
        q["id"] = f"ho_arch_{i:03d}"
        q["metadata"]["heldout_twin_of"] = "system_architecture_test_questions_100_v4.json"

    # ── colloq 孿生集 ──────────────────────────────────────────────
    print("▶ 生成 heldout_colloq_100 …")
    colloq: list[dict] = []
    colloq += gen_direct_lookup(facts, ex, rng, SPEC_COLLOQ["colloquial_single_metric"],
                                "colloq", quota=COLLOQ_METRIC_QUOTA)
    colloq += gen_cross_company(facts, ex, rng,
                                SPEC_COLLOQ["colloquial_company_compare"], "colloq")
    colloq += gen_cross_period(facts, ex, rng,
                               SPEC_COLLOQ["colloquial_period_compare"], "colloq")
    colloq += gen_investment(v14, nodes, edges, ex, rng,
                             SPEC_COLLOQ["colloquial_investment_question"], "colloq")
    colloq += gen_related_party(rp, ex, rng,
                                SPEC_COLLOQ["colloquial_related_party_question"], "colloq")
    colloq += gen_supply_chain(ex, rng,
                               SPEC_COLLOQ["colloquial_supply_chain_question"], "colloq")
    colloq += gen_risk(v14, nodes, edges, ex, rng,
                       SPEC_COLLOQ["colloquial_risk_question"], "colloq")
    order_c = list(SPEC_COLLOQ)
    colloq.sort(key=lambda q: order_c.index(q["question_type"]))
    for i, q in enumerate(colloq, 1):
        q["id"] = f"ho_colloq_{i:03d}"
        q["metadata"]["heldout_twin_of"] = \
            "customer_colloquial_test_questions_100_v2_v3.json"

    # ── 純口語自然孿生集 ──────────────────────────────────────────
    print("▶ 生成 heldout_colloq_nat_100 …")
    nat100 = gen_colloq_natural(facts, ex, rng, N_COLLOQ_NAT)
    for i, q in enumerate(nat100, 1):
        q["id"] = f"ho_colloq_nat_{i:03d}"
        q["metadata"]["heldout_twin_of"] = "customer_colloquial_natural_100.json"

    # ── 圖譜兩組 ──────────────────────────────────────────────────
    print("▶ 派生 heldout_graph_cap_30 / heldout_graph_nat_30 …")
    cap, natg = derive_graph_sets(arch)

    ambig: list[dict] = []
    if AMBIG:
        print("▶ 生成 heldout_ambig_60（候選歧義分層）…")
        ambig = build_ambig(v14, nodes, edges)

    sets = {
        "heldout_arch_100.json": arch,
        "heldout_colloq_100.json": colloq,
        "heldout_colloq_nat_100.json": nat100,
        "heldout_graph_cap_30.json": cap,
        "heldout_graph_nat_30.json": natg,
    }
    if AMBIG:
        sets["heldout_ambig_60.json"] = ambig

    print("\n── 產出摘要 ──────────────────────────────────────────")
    ok = True
    for name, data in sets.items():
        c = Counter(q["question_type"] for q in data)
        good = len(data) == EXPECT[name]
        ok &= good
        print(f"{'✓' if good else '✗'} {name:30} {len(data):>3}/{EXPECT[name]}")
        for t, k in c.most_common():
            print(f"      {t:<36} {k}")
    if not ok:
        print("\n[WARN] 有資料集未達目標題數——可抽樣池可能被排除索引耗盡。")

    if report_only:
        print("\n--report：未寫檔。")
        return sets

    OUTDIR.mkdir(parents=True, exist_ok=True)
    for name, data in sets.items():
        (OUTDIR / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ 已寫入 {OUTDIR}")
    return sets


if __name__ == "__main__":
    build(report_only="--report" in sys.argv)
