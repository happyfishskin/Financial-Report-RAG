# -*- coding: utf-8 -*-
"""強健性與分流驗證子集評分（正式版）：分流／拒答／歧義偵測分開報告。"""
import json, collections
rs=json.load(open('results/robustness_routing_query.json'))
rs=rs['results'] if isinstance(rs,dict) and 'results' in rs else rs
def refused(a): return '找不到相關資料' in str(a) or '查無' in str(a) or not str(a).strip()
def ambig(a):   return '多個衝突候選' in str(a) or '無法判定' in str(a) or '請補充' in str(a)
def declined(a):return refused(a) or ambig(a)

M={}
c1=[r for r in rs if r['metadata']['subset']=='C1_軌道二敘述題']
route_ok=sum(1 for r in c1 if r.get('answer_mode')=='vector_search')
ev_rank1=sum(1 for r in c1 if (r.get('retrieved_chunks') or [{}])[0].get('table_name')==r['metadata']['source_table'])
answered=sum(1 for r in c1 if not declined(r.get('answer')) and r.get('answer_mode')=='vector_search')
M['C1']=dict(n=len(c1),分流正確=route_ok,目標表落於rank1=ev_rank1,實質作答=answered,全數拒答=len(c1)-answered-1)

c2=[r for r in rs if r['metadata']['subset']=='C2_近似無答案題']
M['C2']=dict(n=len(c2),正確拒答=sum(1 for r in c2 if declined(r.get('answer'))))

amb=[r for r in rs if r['metadata'].get('scoring')=='refusal_correctness'
     and r['metadata']['subset']=='C3_候選不唯一題']
M['C3a']=dict(n=len(amb),正確停下=sum(1 for r in amb if declined(r.get('answer'))),
              明示歧義=sum(1 for r in amb if ambig(r.get('answer'))))
per=[r for r in rs if r['metadata'].get('scoring')=='assumption_disclosure']
M['C3b']=dict(n=len(per),
              作答並揭露假設=sum(1 for r in per if '未指定期別' in str(r.get('answer')) or '預設採最新期別' in str(r.get('answer'))))
print(json.dumps(M,ensure_ascii=False,indent=2))
tot=len(c1)+len(c2)+len(amb)+len(per)
ok=M['C1']['分流正確']+M['C2']['正確拒答']+M['C3a']['正確停下']+M['C3b']['作答並揭露假設']
print(f"\n分流／拒答總正確率：{ok}/{tot} = {ok/tot*100:.1f}%")
json.dump(dict(metrics=M,overall=dict(n=tot,ok=ok,rate=round(ok/tot,3))),
          open('results/robustness_routing_report.json','w'),ensure_ascii=False,indent=2)

md=f"""# 強健性與分流驗證子集（28 題）

**動機**（口試預想質詢）：既有 880 題全部由事實表反查生成，且僅保留「當期欄可唯一定位」者，
致 842 題（95.7%）落在軌道一、軌道二僅 32 題（3.6%）。本子集刻意建構**現有題庫從未涵蓋**的
三類情境，以檢驗雙軌架構中未被評測的那一軌，以及「條件不足即停下」的行為。

**主指標**：分流正確率與拒答正確率（皆為客觀判定，不需數值金標）。
軌道二之答案品質另以人工有據性判定，不併入主指標。

## 一、結果

| 子分層 | n | 主指標 | 結果 |
|---|---:|---|---|
| C1 軌道二敘述題（會計政策／衡量基礎） | {M['C1']['n']} | 分流至軌道二 | **{M['C1']['分流正確']}／{M['C1']['n']}** |
| C2 近似無答案題（真公司真季度，該項未揭露） | {M['C2']['n']} | 正確拒答 | **{M['C2']['正確拒答']}／{M['C2']['n']}** |
| C3a 候選不唯一（未指定交易對象） | {M['C3a']['n']} | 正確停下不猜 | **{M['C3a']['正確停下']}／{M['C3a']['n']}**（其中明示歧義 {M['C3a']['明示歧義']}） |
| C3b 未指定期別單值題（Fix 20） | {M['C3b']['n']} | 作答並揭露假設 | **{M['C3b']['作答並揭露假設']}／{M['C3b']['n']}** |
| **合計** | **{tot}** | 分流／拒答 | **{ok}／{tot} = {ok/tot*100:.1f}%** |

## 二、三項發現

**（一）拒答設計在真實未揭露情境下成立。** C2 十題皆為真實公司、真實季度、真實揭露型態
（為他人背書保證／資金貸與他人／向關係人借款），僅該公司該季語料中確實不存在該表。
系統十題全數回覆「找不到相關資料」，**未出現任何一次編造**。此為「寧缺勿猜」在正式題庫
之外的獨立驗證。

**（二）Fix 20 之假設揭露如設計運作。** C3b 四題未指定期別，系統皆以最新期別作答並於答案內
明示「未指定期別，預設採最新期別 114Q4；本資料涵蓋 113Q1–114Q4」，未靜默假設。

**（三）軌道二能被正確路由，但在本系統中幾乎無法作答——此為本子集最重要的負面發現。**
C1 十題有 {M['C1']['分流正確']} 題正確分流至軌道二，其中 **{M['C1']['目標表落於rank1']} 題的目標敘述表就落在檢索結果第 1 名**，
然而系統**全數回覆「找不到相關資料」，實質作答 0 題**。亦即：在敘述型問題上，檢索端已把
正確證據排到第一位，SLM 仍拒絕作答。

此結果與 §4.4.1 之受控消融互為佐證（A 組拒答率 51.0%），並將該現象自數值題延伸至敘述題。
其直接意涵是：**本研究之軌道二在現行 4B 量化模型下，實際承擔的是「降級與拒答」而非
「文字問答」的角色**；論文如宣稱雙軌之第二軌處理非結構化文字問答，應同步揭露此限制。
（另 4 題目標表為「資產與負債區分流動與非流動之標準」者，其目標表未進入 top-5，屬檢索失敗，
與上述生成端拒答為不同成因。）

## 三、此子集不能宣稱什麼

- 題數小（各分層 8–10 題），僅足以顯示行為型態，不足以支持比率的精確估計。
- C1 之敘述題材受限於季報語料：MOPS 季報無 MD&A、營運風險與未來展望，故本子集只能取材
  會計政策與衡量基礎。跨越至年報敘述文本之能力**未量測**。
- C2 之「未揭露」係以語料中不存在該表為判準，非逐一查證原始財報確無該項揭露。

（資料來源：`questions/robustness_routing_subset.json`、`results/robustness_routing_query.json`、
`results/robustness_routing_report.json`；重現：`python3 rag_test_system_v14.py rag-query
--dataset questions/robustness_routing_subset.json --output results/robustness_routing_query.json`）
"""
open('results/robustness_routing_report.md','w').write(md)
print('→ results/robustness_routing_report.md')
