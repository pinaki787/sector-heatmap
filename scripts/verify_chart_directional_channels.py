"""Independent Decimal50 DMI/ADX, Keltner and Donchian formulas."""
import argparse,csv,json,hashlib,subprocess,tempfile
from pathlib import Path
from decimal import Decimal,getcontext,ROUND_HALF_UP
getcontext().prec=50
parser=argparse.ArgumentParser();parser.add_argument('csv_file',type=Path);parser.add_argument('--library',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];library=(args.library or root/'chart-workspace-studies.js').resolve()
records=[r for r in csv.DictReader(args.csv_file.open()) if r.get('provisional','0')!='1']
broker=[{k:Decimal(r[k]) for k in ['open','high','low','close']} for r in records]
def bar(h,l,c=Decimal(100)):return {'open':c,'high':h,'low':l,'close':c}
tie=[bar(Decimal('100.1')+Decimal('.1')*i,Decimal('99.8')-Decimal('.1')*i) for i in range(100)]
flat=[bar(Decimal(100),Decimal(100)) for _ in range(80)]
gap=[bar(Decimal(101)+i,Decimal(99)+i,Decimal(100)+i) for i in range(80)]
data={'broker':broker,'equal_moves':tie,'flat':flat,'trend':gap,'empty':[],'one':tie[:1],'short':tie[:5]}
def sma(v,n):return [None if i+1<n else sum(v[i+1-n:i+1])/n for i in range(len(v))]
def ema(v,n):
 result=[];alpha=Decimal(2)/(n+1)
 for value in v:result.append(value if not result else result[-1]+alpha*(value-result[-1]))
 return result
def rma(v,n):
 out=[None]*min(len(v),n-1)
 if len(v)<n:return out
 value=sum(v[:n])/n;out.append(value)
 for current in v[n:]:value=(value*(n-1)+current)/n;out.append(value)
 return out
def ranges(b):return [x['high']-x['low'] if i==0 else max(x['high']-x['low'],abs(x['high']-b[i-1]['close']),abs(x['low']-b[i-1]['close'])) for i,x in enumerate(b)]
def rounded(v):return v.quantize(Decimal('0.000000001'),rounding=ROUND_HALF_UP)
def dmi(b,n,smoothing):
 if len(b)<2:return [[None]*len(b) for _ in range(3)]
 plus=[];minus=[]
 for previous,current in zip(b,b[1:]):
  up=current['high']-previous['high'];down=previous['low']-current['low']
  plus.append(up if rounded(up)>rounded(down) and rounded(up)>0 else Decimal(0))
  minus.append(down if rounded(down)>rounded(up) and rounded(down)>0 else Decimal(0))
 tr=rma(ranges(b)[1:],n);directions=[]
 for values in [plus,minus]:directions.append([None]+[None if v is None else 100*v/r if r else Decimal(0) for v,r in zip(rma(values,n),tr)])
 dx=[100*abs(a-c)/(a+c) if a+c else Decimal(0) for a,c in zip(directions[0][n:],directions[1][n:])]
 return [*directions,[None]*min(n,len(b))+rma(dx,smoothing)]
specs=[]
for n,s in [(1,1),(2,3),(7,14),(14,14),(20,7)]:
 for kind in ['DMI','ADX']:specs.append({'key':kind+str((n,s)),'kind':kind,'length':n,'multiplier':s,'inputs':{}})
for n in [1,7,14,20]:specs.append({'key':'DC'+str(n),'kind':'Donchian','length':n,'multiplier':2,'inputs':{}})
for n in [1,7,20]:
 for style,atrn in [('Average True Range',1),('Average True Range',10),('Average True Range',14),('True Range',10),('Range',10)]:
  for exponential in [True,False]:
   for mult in ['1.5','2']:
    specs.append({'key':'KC'+str((n,style,atrn,exponential,mult)),'kind':'Keltner','length':n,'multiplier':float(mult),'inputs':{'bandsStyle':style,'atrLength':atrn,'exponential':exponential}})
def reference(b,spec):
 n=spec['length'];kind=spec['kind'];c=[r['close'] for r in b]
 if kind in ['DMI','ADX']:
  plots=dmi(b,n,spec['multiplier']);return [plots[2]] if kind=='ADX' else plots
 if kind=='Donchian':
  hi=[max(r['high'] for r in b[max(0,i+1-n):i+1]) for i in range(len(b))]
  lo=[min(r['low'] for r in b[max(0,i+1-n):i+1]) for i in range(len(b))]
  return [hi,[(a+z)/2 for a,z in zip(hi,lo)],lo]
 settings=spec['inputs'];basis=(ema if settings['exponential'] else sma)(c,n);style=settings['bandsStyle']
 width=ranges(b) if style=='True Range' else rma([r['high']-r['low'] for r in b],n) if style=='Range' else rma(ranges(b),settings['atrLength'])
 mult=Decimal(str(spec['multiplier']))
 return [[None if a is None or w is None else a+mult*w for a,w in zip(basis,width)],basis,[None if a is None or w is None else a-mult*w for a,w in zip(basis,width)]]
payload={'data':{key:[{k:float(v) for k,v in row.items()} for row in rows] for key,rows in data.items()},'specs':specs}
js="const fs=require('node:fs');require(process.argv[1]);const p=JSON.parse(fs.readFileSync(process.argv[2])),i=globalThis.SectorPulseChartStudies.indicators,out={};for(const [name,b]of Object.entries(p.data)){out[name]={};for(const s of p.specs)out[name][s.key]=i[s.kind].run(b,b.map(x=>x.close),s.length,s.multiplier,s.inputs);}process.stdout.write(JSON.stringify(out));"
with tempfile.TemporaryDirectory(prefix='directional-reference-') as tmp:
 file=Path(tmp)/'input.json';file.write_text(json.dumps(payload));actual=json.loads(subprocess.run(['node','-e',js,str(library),str(file)],capture_output=True,text=True,check=True).stdout)
cases=[];numeric=missing=0;maxerror=Decimal(0)
for name,b in data.items():
 for spec in specs:
  want=reference(b,spec);got=actual[name][spec['key']];bad=[];count=0
  assert len(want)==len(got)
  for plot,(expected,values) in enumerate(zip(want,got)):
   assert len(expected)==len(values),(name,spec['key'],'length')
   for index,(x,y) in enumerate(zip(expected,values)):
    if x is None:
     missing+=1;different=y is not None;error=None
    else:
     numeric+=1;error=abs(x-Decimal(str(y))) if y is not None else None;different=error is None or error>Decimal('0.00000001')
     if error is not None:maxerror=max(maxerror,error)
    if different:
     count+=1
     if len(bad)<3:bad.append({'plot':plot,'index':index,'expected':None if x is None else str(x),'actual':y})
  cases.append({'dataset':name,'study':spec['key'],'status':'FAIL' if count else 'PASS','mismatch_count':count,'samples':bad})
failed=[c for c in cases if c['status']=='FAIL']
report={'status':'FAIL' if failed else 'PASS','library_sha256':hashlib.sha256(library.read_bytes()).hexdigest(),'csv_sha256':hashlib.sha256(args.csv_file.read_bytes()).hexdigest(),'datasets':{k:len(v) for k,v in data.items()},'cases':len(cases),'failed_cases':len(failed),'numeric_checks':numeric,'missing_checks':missing,'max_error':str(maxerror),'failures':failed,'scope':'Decimal50 formulas, Pine9decimal direction comparisons. EMAfirst-value seed; Donchianavailable-history windows; zeroTRuseszeroDI/ADX bydeclaredconvention. ExternalTradingViewfeed/flat-seed/visualparity not established.'}
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='failures'}));print(json.dumps({'first_failures':failed[:2]}))
raise SystemExit(bool(failed))
