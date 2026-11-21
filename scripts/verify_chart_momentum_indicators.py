"""Independent Decimal50 momentum formulas on completed broker candles."""
import argparse,csv,json,hashlib,subprocess,tempfile
from pathlib import Path
from decimal import Decimal,localcontext
def smooth(v,n):
 values=[];out=[]
 for x in v:
  if x is None:out.append(None);continue
  values.append(x);out.append(sum(values[-n:])/n if len(values)>=n else None)
 return out
def reference(b,n):
 c=[r['close'] for r in b];out={k:[] for k in ['Momentum','ROC','CMO','CCI','WilliamsR','StochRaw']}
 for i,r in enumerate(b):
  out['Momentum'].append(c[i]-c[i-n] if i>=n else None)
  out['ROC'].append(100*(c[i]-c[i-n])/c[i-n] if i>=n and c[i-n] else None)
  changes=[c[j]-c[j-1] for j in range(max(1,i-n+1),i+1)]
  magnitude=sum(abs(x) for x in changes)
  out['CMO'].append(100*sum(changes)/magnitude if i>=n and magnitude else None)
  window=c[max(0,i-n+1):i+1];mean=sum(window)/n if i>=n-1 else None
  dev=sum(abs(x-mean) for x in window)/n if mean is not None else None
  out['CCI'].append((c[i]-mean)/(Decimal('.015')*dev) if dev else None)
  hi=max(x['high'] for x in b[max(0,i-n+1):i+1]);lo=min(x['low'] for x in b[max(0,i-n+1):i+1])
  out['WilliamsR'].append(-100*(hi-c[i])/(hi-lo) if i>=n-1 and hi>lo else None)
  out['StochRaw'].append(100*(c[i]-lo)/(hi-lo) if i>=n-1 and hi>lo else None)
 out['StochK']=smooth(out.pop('StochRaw'),3);out['StochD']=smooth(out['StochK'],3)
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('csv_file',type=Path);p.add_argument('--library',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 rows=[r for r in csv.DictReader(a.csv_file.open()) if r.get('provisional','').lower() not in ('1','true')]
 bars=[{k:Decimal(r[k]) for k in ('open','high','low','close')} for r in rows]
 root=Path(__file__).resolve().parents[1];library=a.library or root/'chart-workspace-studies.js'
 def synthetic(values):return [dict(open=x,high=x+1,low=x-1,close=x) for x in map(Decimal,values)]
 datasets={'broker':bars,'flat':synthetic(['100']*50),'impulse_then_flat':synthetic(['100','103.7','101.1']+['101.1']*47)}
 results=[]
 with localcontext() as ctx:
  ctx.prec=50
  for name,b in datasets.items():
   for n in (1,14,20):
    want=reference(b,n)
    js="const fs=require('node:fs');require(process.argv[1]);const b=JSON.parse(fs.readFileSync(process.argv[2])),n=Number(process.argv[3]),v=b.map(x=>x.close),i=globalThis.SectorPulseChartStudies.indicators;const out=Object.fromEntries(['Momentum','ROC','CMO','CCI','WilliamsR'].map(k=>[k,i[k].run(b,v,n)[0]]));[out.StochK,out.StochD]=i.Stochastic.run(b,v,n,undefined,{smoothK:3,smoothD:3});console.log(JSON.stringify(out));"
    with tempfile.TemporaryDirectory() as folder:
     f=Path(folder)/'bars.json';f.write_text(json.dumps([{k:float(v) for k,v in r.items()} for r in b]))
     actual=json.loads(subprocess.run(['node','-e',js,str(library.resolve()),str(f),str(n)],capture_output=True,text=True,check=True).stdout)
    for key,expected in want.items():
     got=actual[key];assert len(got)==len(expected)
     mismatch=[i for i,(x,y) in enumerate(zip(got,expected)) if (x is None)!=(y is None)]
     errors=[abs(Decimal(str(x))-y) for x,y in zip(got,expected) if x is not None and y is not None]
     maximum=max(errors,default=Decimal(0))
     results.append(dict(dataset=name,indicator=key,length=n,numeric_points=len(errors),null_mismatches=len(mismatch),first_null_mismatch=mismatch[:3],max_absolute_error=str(maximum),passed=not mismatch and maximum<Decimal('1e-8')))
 report=dict(status='PASS' if all(x['passed'] for x in results) else 'FAIL',source_rows=len(rows),source_sha256=hashlib.sha256(a.csv_file.read_bytes()).hexdigest(),library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),results=results,scope='Close source supplied to source-selectable studies; independent Decimal50 formulas, broker and flat/impulse cases. Not external TradingView feed/seeding or hosted rendering parity.')
 a.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='results'}));print(json.dumps([x for x in results if not x['passed']]))
 if report['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
