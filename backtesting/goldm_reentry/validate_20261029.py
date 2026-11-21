import ast,json,math
from pathlib import Path
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
p=Path('backtesting/goldm_reentry/research_20261029.py');tree=ast.parse(p.read_text());ns={'datetime':datetime,'tz':ZoneInfo('Asia/Kolkata')}
for name in ['day','simulate','stats']:
 node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name);exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),ns)
base=1793244600
ns['rows']=[[base+i*60,100+i,102+i,99+i,101+i,1] for i in range(8)];ns['warm']=[]
date=ns['day'](base)
def e(st,brick,cross=None):return dict(st=st,brick=brick,cross=cross,qualified=bool(cross))
obs=[dict(i=0,day=date,events=[e('BULLISH','BULLISH','BULLISH')]),dict(i=1,day=date,events=[e('BULLISH','BULLISH')]),dict(i=2,day=date,events=[e('BEARISH','BEARISH','BEARISH')]),dict(i=3,day=date,events=[e('BEARISH','BEARISH')])]
a=ns['simulate'](obs,'reversal');assert a[0]['entry_at']==base+60 and a[0]['exit_at']==base+180;assert len(a)==1,'Exit observation must not reverse immediately'
b=ns['simulate'](obs,'next_aligned_brick');assert b[0]['entry_at']==base+120
c=ns['simulate']([dict(i=0,day=date,events=[e('BULLISH','BEARISH')]),dict(i=1,day=date,events=[e('BULLISH','BULLISH')])],'pullback_only');assert c[0]['entry_at']==base+120
a=ns['simulate'](obs,'reversal',1);assert a[0]['entry_at']==base+120
ns['rows'][2][0]+=1
assert not ns['simulate']([dict(i=1,day=date,events=[e('BULLISH','BULLISH','BULLISH')])],'reversal'),'Missing next candle must not create a fill'
out=Path('output/goldm-reentry-20261029')
m=json.loads((out/'manifest.json').read_text());counts={}
for f in out.glob('*-trades.json'):
 ts=json.loads(f.read_text());c=Counter(x['day'] for x in ts);assert max(c.values(),default=0)<=12
 for t in ts:
  assert t['exit_at']>=t['entry_at'];assert math.isfinite(t['points'])
 counts[f.name]=dict(c)
result={'checks':['next-open execution','no same-observation reversal','next aligned brick delayed entry','pullback confirmation','additional-minute delay','missing-candle no fill','12-entry daily cap in all exports','finite P&L and chronological fills'],'trade_counts_by_day':counts}
(out/'validation.json').write_text(json.dumps(result,indent=2))
print('8 replay integrity checks passed')
print('Comparison days with trades',sorted({d for c in counts.values() for d in c if d in m['chronological_comparison']}))

