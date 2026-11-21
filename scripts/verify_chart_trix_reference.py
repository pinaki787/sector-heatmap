"""Independent Decimal50 native log-change TRIX reference on positive prices."""
import argparse,csv,json,hashlib,subprocess,tempfile
from pathlib import Path
from decimal import Decimal,localcontext
p=argparse.ArgumentParser();p.add_argument('csv_file',type=Path);p.add_argument('--library',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
rows=[r for r in csv.DictReader(a.csv_file.open()) if r.get('provisional','0') not in ('1','true')]
values=[Decimal(r['close']) for r in rows]
datasets={'broker':values,'flat':[Decimal(100)]*80,'small':[Decimal('.1')+Decimal('.0005')*i for i in range(200)],'alternating':[Decimal(100)+Decimal(i%5)*Decimal('2.7') for i in range(150)],'unit':[Decimal(1)]*80,'one':[Decimal(100)],'empty':[]}
periods=[1,2,9,18,50]
with localcontext() as ctx:
 ctx.prec=50
 def ema(v,n):
  out=[]
  for x in v:out.append(x if not out else (out[-1]*(n-1)+2*x)/(n+1))
  return out
 want={}
 for name,v in datasets.items():
  logs=[x.ln() for x in v];want[name]={}
  for n in periods:
   s=ema(ema(ema(logs,n),n),n)
   want[name][str(n)]=[None]+[(s[i]-s[i-1])*10000 for i in range(1,len(s))] if s else []
 with tempfile.TemporaryDirectory() as temp:
  file=Path(temp)/'input.json';file.write_text(json.dumps({'datasets':{k:[float(x) for x in v] for k,v in datasets.items()},'periods':periods}))
  js="const fs=require('fs');require(process.argv[1]);const d=JSON.parse(fs.readFileSync(process.argv[2])),t=globalThis.SectorPulseChartStudies.indicators.TRIX,out={};for(const [name,v] of Object.entries(d.datasets)){const bars=v.map(close=>({open:close,high:close,low:close,close}));out[name]={};for(const n of d.periods)out[name][n]=t.run(bars,v,n)[0];}console.log(JSON.stringify(out));"
  actual=json.loads(subprocess.run(['node','-e',js,str(a.library.resolve()),str(file)],capture_output=True,text=True,check=True).stdout)
 results=[];total=missing=0;max_all=Decimal(0)
 for name,configs in want.items():
  for n,expected in configs.items():
   got=actual[name][n];assert len(got)==len(expected);bad=[];maximum=Decimal(0)
   for i,(x,y) in enumerate(zip(expected,got)):
    if x is None:
     missing+=1
     if y is not None:bad.append(i)
    else:
     total+=1;error=None if y is None else abs(x-Decimal(str(y)))
     if error is None or error>Decimal('1e-8'):bad.append(i)
     if error is not None:maximum=max(maximum,error);max_all=max(max_all,error)
   results.append({'dataset':name,'period':int(n),'status':'FAIL' if bad else 'PASS','mismatches':len(bad),'samples':bad[:3],'max_error':str(maximum)})
 report={'status':'PASS' if all(r['status']=='PASS' for r in results) else 'FAIL','cases':len(results),'numeric_checks':total,'missing_checks':missing,'max_error':str(max_all),'results':results,'library_sha256':hashlib.sha256(a.library.read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(a.csv_file.read_bytes()).hexdigest(),'scope':'Decimal50 natural-log triple EMA change x10000; first-value EMA seeds. External native TradingView earlier-history seed parity and live broker source parity separate.'}
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='results'}));raise SystemExit(report['status']!='PASS')
