"""Independent Decimal50 checks; external TradingView seeding is a separate gate."""
import argparse,csv,json,subprocess,tempfile,hashlib
from decimal import Decimal,localcontext
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('csv',type=Path);p.add_argument('--library',type=Path,default=Path('chart-workspace-studies.js'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
rows=[r for r in csv.DictReader(a.csv.open()) if r.get('provisional','0') not in ('1','true')]
broker=[{k:Decimal(r[k]) for k in ['open','high','low','close']} for r in rows]
flat=[dict(open=Decimal(100),high=Decimal(100),low=Decimal(100),close=Decimal(100)) for _ in range(100)]
trend=[dict(open=Decimal(i+100),high=Decimal(i+102),low=Decimal(i+99),close=Decimal(i+101)) for i in range(140)]
datasets={'broker':broker,'flat':flat,'trend':trend,'one':flat[:1],'empty':[]}
configs=[]
for name in ['UO','Vortex','KST','Coppock','Aroon']:
 configs.append({'name':name,'length':14,'inputs':{}})
for n in [1,2,9,50]:
 for name in ['Vortex','Aroon']:configs.append({'name':name,'length':n,'inputs':{}})
configs += [
 {'name':'UO','length':14,'inputs':dict(fast=1,middle=2,slow=5)},
 {'name':'KST','length':14,'inputs':dict(roc1=1,roc2=2,roc3=3,roc4=4,sma1=1,sma2=2,sma3=3,sma4=4,signalLength=2)},
 {'name':'Coppock','length':14,'inputs':dict(wmaLength=2,longRocLength=3,shortRocLength=1)}]
def mean(v,n,weights=False):
 out=[]
 for i in range(len(v)):
  w=v[max(0,i-n+1):i+1]
  out.append(None if len(w)<n or any(x is None for x in w) else (sum(x*(j+1) for j,x in enumerate(w))/Decimal(n*(n+1)//2) if weights else sum(w)/n))
 return out
def roc(v,n):return [None if i<n or v[i-n]==0 else (x-v[i-n])*100/v[i-n] for i,x in enumerate(v)]
def reference(b,c):
 name,n,inp=c['name'],c['length'],c['inputs'];v=[x['close'] for x in b];size=len(b)
 if name=='UO':
  bp=[];tr=[]
  for i,x in enumerate(b):
   prev=b[i-1]['close'] if i else None;lo=min(x['low'],prev) if prev is not None else x['low']
   bp.append(x['close']-lo);tr.append((max(x['high'],prev) if prev is not None else x['high'])-lo)
  components=[]
  for key,default in [('fast',7),('middle',14),('slow',28)]:
   k=inp.get(key,default);num,den=mean(bp,k),mean(tr,k)
   components.append([None if y is None or y==0 else x/y for x,y in zip(num,den)])
  return [[None if any(x is None for x in t) else 100*(4*t[0]+2*t[1]+t[2])/7 for t in zip(*components)]]
 if name=='Vortex':
  tr=[max(x['high'],b[i]['close'])-min(x['low'],b[i]['close']) for i,x in enumerate(b[1:])]
  den=mean(tr,n);out=[]
  for side in [0,1]:
   movement=[abs(x['high']-b[i]['low']) if side==0 else abs(x['low']-b[i]['high']) for i,x in enumerate(b[1:])]
   num=mean(movement,n)
   out.append(([None]+[None if y is None or y==0 else x/y for x,y in zip(num,den)]) if size else [])
  return out
 if name=='KST':
  comp=[mean(roc(v,inp.get('roc'+str(j+1),k)),inp.get('sma'+str(j+1),15 if j==3 else 10)) for j,k in enumerate([10,15,20,30])]
  kst=[None if any(x is None for x in t) else sum(x*(j+1) for j,x in enumerate(t)) for t in zip(*comp)]
  return [kst,mean(kst,inp.get('signalLength',9))]
 if name=='Coppock':
  long,short=roc(v,inp.get('longRocLength',14)),roc(v,inp.get('shortRocLength',11))
  return [mean([None if x is None or y is None else x+y for x,y in zip(long,short)],inp.get('wmaLength',10),True)]
 out=[[],[]]
 for i in range(size):
  for side,field in enumerate(['high','low']):
   if i<n:out[side].append(None);continue
   w=[x[field] for x in b[i-n:i+1]];target=max(w) if side==0 else min(w)
   age=next(j for j,x in enumerate(reversed(w)) if x==target)
   out[side].append(Decimal(100)*(n-age)/n)
 return out
with localcontext() as ctx:
 ctx.prec=50
 expected={name:[reference(b,c) for c in configs] for name,b in datasets.items()}
 with tempfile.TemporaryDirectory() as tmp:
  f=Path(tmp)/'input.json';f.write_text(json.dumps({'datasets':datasets,'configs':configs},default=float))
  js="const fs=require('fs');require(process.argv[1]);const d=JSON.parse(fs.readFileSync(process.argv[2])),o={},reg=globalThis.SectorPulseChartStudies.indicators;for(const [k,b] of Object.entries(d.datasets))o[k]=d.configs.map(c=>reg[c.name].run(b,b.map(x=>x.close),c.length,undefined,c.inputs));console.log(JSON.stringify(o));"
  actual=json.loads(subprocess.run(['node','-e',js,str(a.library.resolve()),str(f)],capture_output=True,text=True,check=True).stdout)
 results=[];numeric=missing=0;maximum=Decimal(0)
 for name,cases in expected.items():
  for ci,plots in enumerate(cases):
   bad=[];err=Decimal(0)
   assert len(plots)==len(actual[name][ci])
   for pi,values in enumerate(plots):
    got=actual[name][ci][pi];assert len(values)==len(got)
    for i,(x,y) in enumerate(zip(values,got)):
     if x is None:
      missing+=1
      if y is not None:bad.append([pi,i,'expected missing'])
     else:
      numeric+=1;e=None if y is None else abs(x-Decimal(str(y)))
      if e is None or e>Decimal('1e-8'):bad.append([pi,i,'numeric mismatch'])
      if e is not None:err=max(err,e);maximum=max(maximum,e)
   results.append({'dataset':name,'config':configs[ci],'mismatches':len(bad),'samples':bad[:4],'max_error':str(err)})
 report={'status':'PASS' if not any(r['mismatches'] for r in results) else 'FAIL','cases':len(results),'numeric_checks':numeric,'missing_checks':missing,'max_error':str(maximum),'results':results,'library_sha256':hashlib.sha256(a.library.read_bytes()).hexdigest(),'scope':'Independent Decimal50 standard formulas on broker OHLC, flat and trend data, empty and one-bar input. Does not establish native TradingView warmup or live/all-broker parity.'}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='results'}))
print(json.dumps([r for r in results if r['mismatches']][:8]));raise SystemExit(report['status']!='PASS')
