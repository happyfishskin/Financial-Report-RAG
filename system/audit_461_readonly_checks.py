"""Read-only diagnostics: no model calls, no edits to system/data/results/deck."""
import ast
import json
import re
from pathlib import Path
from typing import Any
import pandas as pd
from scipy.stats import binomtest

ROOT=Path(__file__).parent
source=ROOT/'rag_test_system_v14.py'
tree=ast.parse(source.read_text())
functions={'_normalize','_extract_numbers','_risk_label_set','_is_risk_label_set','_score_one','_graphrag_entity_table_lookup'}
constants={'_RISK_LABEL_VOCAB','_RISK_SPLIT_RE','_ENTITY_QA_RE','_PERIOD_LABEL_RE'}
nodes=[]
for n in tree.body:
    if isinstance(n,ast.FunctionDef) and n.name in functions: nodes.append(n)
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets): nodes.append(n)
ns={'pd':pd,'re':re,'Any':Any}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
for pred,gold in [('100','-100'),('100','(100)'),('200、100','100、200')]:
    print('NUMERIC_CHECK',json.dumps({'pred':pred,'gold':gold,'scores':ns['_score_one'](pred,gold)},ensure_ascii=False))

df=pd.DataFrame([dict(company_name='測試公司',table_name='測試表',item_name='測試對象',column_header='本期',period='113Q1',value_raw='100')])
question='在【測試公司】的【測試表】中，被投資公司【測試對象】的【本期】是多少？'
result=ns['_graphrag_entity_table_lookup'](question,{'quarters':['114Q2']},df)
print('RELATION_PERIOD_MISS',json.dumps({'requested':'114Q2','available':['113Q1'],'returned':result},ensure_ascii=False))
question='在【測試公司】的【錯誤表名】中，被投資公司【測試對象】的【不存在的欄位】是多少？'
print('RELATION_TABLE_COLUMN_MISS',ns['_graphrag_entity_table_lookup'](question,{'quarters':['113Q1']},df))

r=ROOT.parent/'version10'/'results'
rows=[json.loads((r/f).read_text())['results'] for f in ['pure_rag_4b_main.json','pure_rag_27b_main.json','track1_off_embed_ablation.json','track1_off_27b.json']]
def keyed(rows,arm=None):
    return {(x['dataset'],x['id']):bool((x['arms'][arm] if arm else x)['scores']['exact_match']) for x in rows}
maps=[keyed(rows[0]),keyed(rows[1]),keyed(rows[2],'A'),keyed(rows[3])]
for tag,i,j in [('pure4→27',0,1),('filtered4→27',2,3),('4pure→filtered',0,2),('27pure→filtered',1,3)]:
    a,b=maps[i],maps[j]
    assert a.keys()==b.keys()
    only_a=sum(a[k] and not b[k] for k in a);only_b=sum(not a[k] and b[k] for k in a)
    print('PAIRED',tag,dict(n=len(a),correct_a=sum(a.values()),correct_b=sum(b.values()),only_a=only_a,only_b=only_b,p=binomtest(only_a,only_a+only_b,.5).pvalue if only_a+only_b else 1))

all_rows=[];ho_rows=[]
for filename in ['evidence_format_ablation.json','evidence_format_ablation_ho_arch.json','evidence_format_ablation_ho_colloq.json']:
    d=json.loads((ROOT/'results'/filename).read_text());all_rows.extend(d['results'])
    if '_ho_' in filename:ho_rows.extend(d['results'])
for label,rr in [('pooled',all_rows),('heldout_only',ho_rows)]:
    print('ABC',label,'n',len(rr),{g:sum(x['groups'][g]['scores']['exact_match'] for x in rr) for g in ['A_raw_markdown','B_flattened_kv','C_fact_lookup']})
config=json.loads((ROOT/'config/system_config.json').read_text())
q='台積電114Q2賺了多少利潤？'
matches=[(syn,canon) for canon,syns in config['financial_ontology'].items() for syn in syns if syn in q]
print('ONTOLOGY_LONGEST_CONFIG_MATCH',max(matches,key=lambda x:len(x[0])))
