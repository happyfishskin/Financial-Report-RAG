# -*- coding: utf-8 -*-
"""A 組自報定位效度：沿用 pool_evidence_format.localized() 之判準，
   追查「自報定位正確但答錯」各題之錯誤答案實際來源。"""
import json, re, sys, importlib.util
import pandas as pd

spec=importlib.util.spec_from_file_location('pool','pool_evidence_format.py')
pool=importlib.util.module_from_spec(spec); spec.loader.exec_module(pool)

FACTS=str(__import__('pathlib').Path(__file__).resolve().parent / 'reports_csv_output') + '/__all_company_all_period_numeric_facts.csv'
FILES=['results/evidence_format_ablation.json','results/evidence_format_ablation_ho_arch.json','results/evidence_format_ablation_ho_colloq.json']

def numnorm(s):
    if s is None: return None
    t=str(s).strip().replace(',','').replace(' ','').replace('　','')
    m=re.fullmatch(r'[\(（]\s*(-?[\d.]+)\s*[\)）]',t)
    if m: return '-'+m.group(1).lstrip('-')
    return t if re.fullmatch(r'-?\d+(?:\.\d+)?%?',t) else None

rows=[]
for f in FILES:
    for r in json.load(open(f))['results']: rows.append(r)
G='A_raw_markdown'
locok=[r for r in rows if pool.localized(r,G)]
wrong=[r for r in locok if not pool.em(r,G)]
print(f'A 組：定位成功 {len(locok)}、其中取值仍失敗 {len(wrong)}、'
      f'失敗率 {len(wrong)/len(locok)*100:.1f}%   ← 對照論文表 4-8d（55／29／52.7%）')

print('載入事實表…', file=sys.stderr)
df=pd.read_csv(FACTS, low_memory=False,
    usecols=['company_name','period','table_name','item_name','column_header','value_raw'])
df['vn']=df['value_raw'].map(numnorm)

CO=re.compile(r'【([^】]+)】')
cls={'自報不實：實為同科目之其他期間欄':0,'自報不實：實為其他科目':0,
     '拒答（未產生數值）':0,'事實表查無此值（搬運毀損或捏造）':0}
detail=[]
for r in wrong:
    g=r['groups'][G]; ans=g.get('answer')
    br=CO.findall(r['question']); comp=br[0] if br else None; per=br[1] if len(br)>1 else None
    if pool.refused(r,G) or numnorm(ans) is None:
        v='拒答（未產生數值）'; cls[v]+=1
        detail.append(dict(id=r['id'],verdict=v,ans=ans,gold=r.get('expected_answer'))); continue
    a=numnorm(ans)
    m=df[(df['company_name'].astype(str).str.contains(str(comp),na=False,regex=False))
         &(df['period']==per)&(df['vn']==a)]
    if len(m)==0:
        v='事實表查無此值（搬運毀損或捏造）'; cls[v]+=1; found=None
    else:
        gi=pool._norm(r.get('gold_item'))
        same=m[m['item_name'].astype(str).map(lambda x: pool._norm(x)==gi)]
        if len(same)>0:
            v='自報不實：實為同科目之其他期間欄'; found=sorted(set(same['column_header'].astype(str)))[:3]
        else:
            v='自報不實：實為其他科目'; found=sorted(set(m['item_name'].astype(str)))[:2]
        cls[v]+=1
    detail.append(dict(id=r['id'],verdict=v,company=comp,period=per,
                       gold_item=r.get('gold_item'),gold_col=r.get('gold_column'),
                       gold=r.get('expected_answer'),ans=ans,actual_source=found))

n=len(wrong); mis=cls['自報不實：實為同科目之其他期間欄']+cls['自報不實：實為其他科目']
print(f'\n=== {n} 題「自報定位正確但答錯」之真實來源 ===')
for k,v in cls.items(): print(f'  {k:<26} {v:>3} 題 ({v/n*100:5.1f}%)')
print(f'\n自報不實（實為定位失敗）：{mis}/{n} = {mis/n*100:.1f}%')
print(f'自報可信（定位對、搬運或輸出失敗）：{n-mis}/{n} = {(n-mis)/n*100:.1f}%')
adj=(len(locok)-mis)
print(f'\n保守修正後：定位成功 {len(locok)} → {adj}；'
      f'定位成功下取值失敗率 {len(wrong)/len(locok)*100:.1f}% → {(n-mis)/adj*100:.1f}%')
json.dump(dict(loc_ok=len(locok),loc_ok_value_fail=n,classification=cls,
               misreported=mis,adjusted_loc_ok=adj,
               adjusted_value_fail_rate=round((n-mis)/adj,4),detail=detail),
          open('results/selfreport_validity.json','w'),ensure_ascii=False,indent=2)
print('→ results/selfreport_validity.json')
