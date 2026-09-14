# -*- coding: utf-8 -*-
"""解析層抽樣核對 v2：處理跨公司／跨季度之複合金標。
   以獨立解析器自 MOPS 原始財報 HTML 取值，逐分量與金標比對。"""
import json, re, glob, random, unicodedata, warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

def nz(s): return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(s or ''))).lower()
def numnorm(s):
    t=nz(s).replace(',','')
    m=re.fullmatch(r'[\(（](-?[\d.]+)[\)）]',t)
    if m: return '-'+m.group(1).lstrip('-')
    return t

FILES=['results/evidence_format_ablation.json',
       'results/evidence_format_ablation_ho_arch.json',
       'results/evidence_format_ablation_ho_colloq.json']
CO=re.compile(r'【([^】]+)】'); PER=re.compile(r'^\d{3}Q[1-4]$'); CODE=re.compile(r'^(\d{4})_')

name2code={}
for d in glob.glob('reports_html_copy/*'):
    b=d.split('/')[-1]
    if CODE.match(b):
        c,nm=b.split('_',1); name2code[nz(nm)]=c
def find_code(cn):
    z=nz(cn)
    for nm,c in name2code.items():
        if z in nm or nm.startswith(z): return c
    return None

pool=[]
for f in FILES:
    tag=('dev-arch' if f.endswith('ablation.json') else 'ho-arch' if 'ho_arch' in f else 'ho-colloq')
    for r in json.load(open(f))['results']:
        br=CO.findall(r['question'])
        if not r.get('gold_item') or not r.get('gold_column'): continue
        pers=[b for b in br if PER.fullmatch(b)]
        comps=[b for b in br if not PER.fullmatch(b) and nz(b)!=nz(r['gold_item'])
               and find_code(b)]
        if not pers or not comps: continue
        pool.append(dict(src=tag,id=r['id'],companies=comps,periods=pers,
                         item=r['gold_item'],col=r['gold_column'],gold=r['expected_answer']))

def parse_gold(g):
    """複合金標 'K: v ｜ K2: v2' → {K: v}；單值 → {None: v}"""
    parts=[p.strip() for p in re.split(r'[｜|]',str(g)) if p.strip()]
    out={}
    for p in parts:
        m=re.match(r'^(.+?)\s*[:：]\s*(.+)$',p)
        if m and len(parts)>1: out[nz(m.group(1))]=m.group(2).strip()
        else: out[None]=p
    return out

def extract(code, period, item, col):
    fs=glob.glob(f'reports_html_copy/{code}_*/{code}_{period}_財報.html')
    if not fs: return None,'無此期別 HTML'
    soup=BeautifulSoup(open(fs[0],encoding='utf-8',errors='ignore').read(),'lxml')
    key=nz(re.split(r'[A-Za-z(]',item)[0]) or nz(item)
    for t in soup.find_all('table'):
        trs=t.find_all('tr'); hdr=None
        for tr in trs:
            cs=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])]
            if any(c and (nz(col) in nz(c) or nz(c) in nz(col)) for c in cs): hdr=cs; break
        if not hdr: continue
        ci=[i for i,c in enumerate(hdr) if c and (nz(col) in nz(c) or nz(c) in nz(col))]
        if not ci: continue
        ci=ci[0]
        for tr in trs:
            cs=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])]
            if any(key and key in nz(c) for c in cs) and len(cs)>ci:
                return cs[ci], hdr[ci][:30]
    return None,'HTML 未定位到該（科目, 欄位）'

random.seed(20260823)
byk={}
for p in pool: byk.setdefault((tuple(p['companies']),tuple(p['periods'])),[]).append(p)
keys=sorted(byk, key=str); random.shuffle(keys)
sample=[random.choice(byk[k]) for k in keys[:20]]
print(f'可核對題庫 {len(pool)} 題，分層抽出 {len(sample)} 題（共 '
      f'{sum(len(s["companies"])*len(s["periods"]) for s in sample)} 個待比對儲存格）\n')

res=[]; ok=bad=miss=0
for s in sample:
    gm=parse_gold(s['gold']); cells=[]
    for c in s['companies']:
        for pr in s['periods']:
            code=find_code(c)
            v,note=extract(code,pr,s['item'],s['col']) if code else (None,'代號無法對應')
            # 對應金標分量：優先以期別為鍵，其次公司名，最後單值
            exp=gm.get(nz(pr)) or gm.get(nz(c)) or gm.get(None)
            if v is None: verdict='未能定位'; miss+=1
            elif exp is None: verdict='金標分量對不上'; miss+=1
            elif numnorm(v)==numnorm(exp): verdict='一致'; ok+=1
            else: verdict='不一致'; bad+=1
            cells.append(dict(company=c,period=pr,gold_part=exp,html=v,verdict=verdict,hdr=note))
            print(f"  [{verdict:<10}] {s['id']:<16} {c[:8]:<9}{pr}  金標={str(exp)[:18]:<19} HTML={v}")
    res.append({**s,'cells':cells})

n=ok+bad
print(f'\n=== 結果 ===')
print(f'比對儲存格 {n} 個：一致 {ok}、不一致 {bad}'+(f'（一致率 {ok/n*100:.1f}%）' if n else ''))
print(f'未能定位／無法對應 {miss} 個')
json.dump(dict(sampled_questions=len(sample),cells_compared=n,consistent=ok,
               inconsistent=bad,unlocatable=miss,detail=res),
          open('results/parser_provenance_check.json','w'),ensure_ascii=False,indent=2)
print('→ results/parser_provenance_check.json')
