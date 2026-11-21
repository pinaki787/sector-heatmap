"""Independent Decimal50 volume-indicator calculations on completed broker candles."""
import argparse,csv,json,hashlib,subprocess,tempfile
from pathlib import Path
from decimal import Decimal,localcontext
def ema(v,n):
 out=[];alpha=Decimal(2)/(n+1)
 for x in v:out.append(x if not out else out[-1]+alpha*(x-out[-1]))
 return out
def reference(rows,n):
 c=[r['close'] for r in rows];vol=[r['volume'] for r in rows]
 tp=[(r['high']+r['low']+r['close'])/3 for r in rows]
 ad=[];ob=[];total=Decimal(0);balance=Decimal(0);flow=[]
 for i,r in enumerate(rows):
  h,l=r['high'],r['low']
  f=(2*r['close']-h-l)/(h-l)*vol[i] if h>l else Decimal(0)
  flow.append(f);total+=f;ad.append(total)
  if i:balance+=(1 if c[i]>c[i-1] else -1 if c[i]<c[i-1] else 0)*vol[i]
  ob.append(balance)
 vw=[];cm=[];mf=[]
 for i in range(len(rows)):
  if i<n-1:vw.append(None);cm.append(None)
  else:
   a=i-n+1;v=sum(vol[a:i+1])
   vw.append(sum(c[j]*vol[j] for j in range(a,i+1))/v if v else None)
   cm.append(sum(flow[a:i+1])/v if v else None)
  if i<n:mf.append(None)
  else:
   pos=sum(tp[j]*vol[j] for j in range(i-n+1,i+1) if tp[j]>tp[j-1])
   neg=sum(tp[j]*vol[j] for j in range(i-n+1,i+1) if tp[j]<tp[j-1])
   mf.append(100*pos/(pos+neg) if pos+neg else None)
 force=[(c[i]-c[i-1])*vol[i] for i in range(1,len(c))]
 fast,slow=ema(ad,3),ema(ad,10)
 return {'OBV':ob,'ADL':ad,'VWMA':vw,'CMF':cm,'MFI':mf,'EFI':[None]+ema(force,n),'CHO':[a-b for a,b in zip(fast,slow)]}
def main():
 p=argparse.ArgumentParser();p.add_argument('csv_file',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--library',type=Path);a=p.parse_args()
 raw=[r for r in csv.DictReader(a.csv_file.open()) if r.get('provisional','').lower() not in ('true','1')]
 rows=[{k:Decimal(r[k]) for k in ('open','high','low','close','volume')} for r in raw]
 assert all(r['volume']>=0 for r in rows)
 root=Path(__file__).resolve().parents[1];library=a.library or root/'chart-workspace-studies.js';report=[]
 with localcontext() as ctx:
  ctx.prec=50
  datasets={'broker':rows,'zero_volume_flat':[dict(open=Decimal(100),high=Decimal(100),low=Decimal(100),close=Decimal(100),volume=Decimal(0)) for _ in range(50)]}
  for dataset,bars in datasets.items():
   for n in (1,14,20):
    expected=reference(bars,n)
    js="const fs=require('node:fs');require(process.argv[1]);const b=JSON.parse(fs.readFileSync(process.argv[2])),n=Number(process.argv[3]),v=b.map(x=>x.close),i=globalThis.SectorPulseChartStudies.indicators;console.log(JSON.stringify(Object.fromEntries(['OBV','ADL','VWMA','CMF','MFI','EFI','CHO'].map(k=>[k,i[k].run(b,v,n,undefined,{})[0]]))));"
    with tempfile.TemporaryDirectory() as folder:
     f=Path(folder)/'bars.json';f.write_text(json.dumps([{k:float(v) for k,v in b.items()} for b in bars]))
     actual=json.loads(subprocess.run(['node','-e',js,str(library.resolve()),str(f),str(n)],capture_output=True,text=True,check=True).stdout)
    for key,want in expected.items():
     got=actual[key];assert len(got)==len(want)
     missing=sum((x is None)!=(y is None) for x,y in zip(got,want))
     errors=[abs(Decimal(str(x))-y) for x,y in zip(got,want) if x is not None and y is not None]
     scaled=[e/max(Decimal(1),abs(y)) for e,y in zip([abs(Decimal(str(x))-y) for x,y in zip(got,want) if x is not None and y is not None],[y for x,y in zip(got,want) if x is not None and y is not None])]
     ok=not missing and max(scaled,default=0)<Decimal('1e-9')
     report.append(dict(dataset=dataset,indicator=key,length=n,numeric_points=len(errors),null_mismatches=missing,max_absolute_error=float(max(errors,default=0)),max_scaled_error=float(max(scaled,default=0)),passed=ok))
 result=dict(status='PASS' if all(r['passed'] for r in report) else 'FAIL',source_rows=len(rows),source_sha256=hashlib.sha256(a.csv_file.read_bytes()).hexdigest(),library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),results=report,scope='Independent Decimal formulas on identical broker candles plus zero-volume flat bars; external feed/seed and hosted rendering separate.')
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='results'}));print(json.dumps([r for r in report if not r['passed']]))
 if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
