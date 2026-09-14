# -*- coding: utf-8 -*-
"""建置「強健性與分流驗證子集」：
   C1 軌道二敘述題（語料有、但非數值事實表可答）
   C2 近似無答案題（真公司、真季度、真揭露型態，但該公司該季未揭露）
   C3 候選不唯一題（條件不足以唯一定位）
   主指標：分流正確率、拒答正確率。"""
import sqlite3, json, collections, random, re
random.seed(20260823)
c=sqlite3.connect('vector_db/chroma.sqlite3')
rows=c.execute("""select t.string_value tab, co.string_value comp, qu.string_value qt, cd.string_value code
                  from embedding_metadata t
                  join embedding_metadata co on t.id=co.id and co.key='company_name'
                  join embedding_metadata qu on t.id=qu.id and qu.key='quarter'
                  join embedding_metadata cd on t.id=cd.id and cd.key='company_code'
                  where t.key='table_name'""").fetchall()
have=collections.defaultdict(set); cq2code={}
for tab,comp,qt,code in rows:
    have[tab].add((comp,qt)); cq2code[(comp,qt)]=code
allcq=sorted({cq for s in have.values() for cq in s})

def pick(tab,k,exclude=set()):
    xs=sorted(have[tab]-exclude); random.shuffle(xs); return xs[:k]
def pick_missing(tab,k,exclude=set()):
    xs=sorted(set(allcq)-have[tab]-exclude); random.shuffle(xs); return xs[:k]

DS=[]; used=set()

# ── C1：軌道二敘述題（10）──────────────────────────────
C1=[('重大會計政策之彙總說明','本合併財務報告的遵循聲明是依據哪些準則編製的？',6),
    ('重大會計政策之彙總說明','合併報表的編製基礎及原則為何？',0),
    ('資產與負債區分流動與非流動之標準','所得稅費用在期中期間是如何評估與計算的？',4)]
for tab,qtext,k in C1:
    for comp,qt in pick(tab,k or 0,used):
        used.add((comp,qt))
        DS.append(dict(question_type='narrative_policy',
            question=f'根據【{comp}】{qt} 的財報附註，{qtext}',
            expected_answer='[敘述型，無單一數值金標；以人工有據性判定]',
            metadata=dict(target_route='vector_search', subset='C1_軌道二敘述題',
                          company_name=comp, quarter=qt, company_code=cq2code[(comp,qt)],
                          source_table=tab, scoring='human_groundedness')))

# ── C2：近似無答案題（10）─────────────────────────────
C2=[('為他人背書保證','為他人背書保證的期末餘額是多少？',4),
    ('資金貸與他人','資金貸與他人的本期最高餘額是多少？',3),
    ('向關係人借款','向關係人借款的期末餘額是多少？',3)]
for tab,qtext,k in C2:
    for comp,qt in pick_missing(tab,k,used):
        used.add((comp,qt))
        DS.append(dict(question_type='undisclosed_item',
            question=f'請查詢【{comp}】在【{qt}】的【{tab}】，{qtext}',
            expected_answer='找不到相關資料',
            metadata=dict(target_route='no_evidence', subset='C2_近似無答案題',
                          company_name=comp, quarter=qt, company_code=cq2code[(comp,qt)],
                          absent_table=tab, scoring='refusal_correctness',
                          note=f'該公司該季語料中不存在「{tab}」，屬真實未揭露而非虛構問題')))

# ── C3：候選不唯一題（8）─────────────────────────────
amb=pick('進貨',4,used); used|=set(amb)
for comp,qt in amb:
    DS.append(dict(question_type='ambiguous_counterparty',
        question=f'請查詢【{comp}】在【{qt}】的關係人進貨金額是多少？',
        expected_answer='[候選不唯一，應拒答或要求補充交易對象]',
        metadata=dict(target_route='refuse_or_clarify', subset='C3_候選不唯一題',
                      company_name=comp, quarter=qt, company_code=cq2code[(comp,qt)],
                      scoring='refusal_correctness',
                      note='未指定交易對象，同期可能對應多筆進貨金額')))
noper=[cq for cq in allcq if cq[1]=='114Q2'][:4]
for comp,qt in noper:
    DS.append(dict(question_type='ambiguous_no_period',
        question=f'請問【{comp}】的營業收入合計是多少？',
        expected_answer='[未指定期別；Fix 20 應採最新期別作答並揭露假設]',
        metadata=dict(target_route='latest_period_with_disclosure', subset='C3_候選不唯一題',
                      company_name=comp, company_code=cq2code[(comp,qt)],
                      scoring='assumption_disclosure',
                      note='未指定期別之單值題，Fix 20 應以最新期別作答並於答案內揭露')))

for i,d in enumerate(DS,1): d['id']=f'robust_{i:03d}'
json.dump(DS, open('questions/robustness_routing_subset.json','w'), ensure_ascii=False, indent=2)
cnt=collections.Counter(d['metadata']['subset'] for d in DS)
print(f'共 {len(DS)} 題'); [print(f'  {k}: {v}') for k,v in sorted(cnt.items())]
print('\n樣例：')
for s in ['C1_軌道二敘述題','C2_近似無答案題','C3_候選不唯一題']:
    e=next(d for d in DS if d['metadata']['subset']==s)
    print(f'  [{s}] {e["question"][:80]}')
print('\n→ questions/robustness_routing_subset.json')
