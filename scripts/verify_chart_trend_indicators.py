"""Independent Decimal50 Supertrend and displaced Ichimoku checks on broker-exported candles."""
import argparse,csv,json,subprocess,tempfile,hashlib
from decimal import Decimal,localcontext,ROUND_HALF_UP
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('csv_file',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--library',type=Path);p.add_argument('--hosted-supertrend',action='store_true');p.add_argument('--hosted-pine-supertrend',action='store_true');args=p.parse_args()
root=Path(__file__).resolve().parents[1]
library=args.library.resolve() if args.library else root/'chart-workspace-studies.js'
with args.csv_file.open() as f:records=[r for r in csv.DictReader(f) if r.get('provisional','0')!='1']
with localcontext() as ctx:
 ctx.prec=50
 highs=[Decimal(r['high']) for r in records];lows=[Decimal(r['low']) for r in records];closes=[Decimal(r['close']) for r in records];n=len(records)
 def midpoint(period):
  return [None if i+1<period else (max(highs[i+1-period:i+1])+min(lows[i+1-period:i+1]))/2 for i in range(n)]
 def ichi(a,b,c,d):
  conv,base,spanb=midpoint(a),midpoint(b),midpoint(c);spana=[None if x is None or y is None else (x+y)/2 for x,y in zip(conv,base)];shift=d-1
  return {'plots':[conv,base,[closes[i+shift] if i+shift<n else None for i in range(n)],[spana[i-shift] if i>=shift else None for i in range(n)],[spanb[i-shift] if i>=shift else None for i in range(n)]],'projected':[spana[max(0,n-shift):],spanb[max(0,n-shift):]],'projectionOffset':max(0,shift-n)}
 tr=[h-l if i==0 else max(h-l,abs(h-closes[i-1]),abs(l-closes[i-1])) for i,(h,l) in enumerate(zip(highs,lows))]
 def rounded(value):return value.quantize(Decimal('0.000000001'),rounding=ROUND_HALF_UP)
 def st(period,factor):
  atr=[None]*n
  if n>=period:
   atr[period-1]=sum(tr[:period])/period
   for i in range(period,n):atr[i]=(atr[i-1]*(period-1)+tr[i])/period
  up=[None]*n;down=[None]*n;upper=[None]*n;lower=[None]*n;line=[None]*n
  for i,v in enumerate(atr):
   if v is None:continue
   highband=(highs[i]+lows[i])/2+factor*v;lowband=(highs[i]+lows[i])/2-factor*v
   previous_upper=upper[i-1] if i else None;previous_lower=lower[i-1] if i else None
   upper[i]=highband if previous_upper is None or rounded(highband)<rounded(previous_upper) or rounded(closes[i-1])>rounded(previous_upper) else previous_upper
   lower[i]=lowband if previous_lower is None or rounded(lowband)>rounded(previous_lower) or rounded(closes[i-1])<rounded(previous_lower) else previous_lower
   if i==0 or atr[i-1] is None:bear=True
   elif rounded(line[i-1])==rounded(previous_upper):bear=not rounded(closes[i])>rounded(upper[i])
   else:bear=rounded(closes[i])<rounded(lower[i])
   line[i]=upper[i] if bear else lower[i]
   (down if bear else up)[i]=line[i]
  return [up,down]
 refs={}
 for period in [1,7,10,14]:
  for factor in [Decimal('1.5'),Decimal('3')]:refs[f'ST-{period}-{factor}']={'plots':st(period,factor)}
 for a,b,c,d in [(9,26,52,26),(2,4,6,1),(9,26,52,250)]:refs[f'ICHI-{a}-{b}-{c}-{d}']=ichi(a,b,c,d)
 bars=[{k:float(r[k]) for k in ['open','high','low','close']} for r in records]
 js="""const fs=require('node:fs');require(process.argv[1]);const b=JSON.parse(fs.readFileSync(process.argv[2])),i=globalThis.SectorPulseChartStudies.indicators,out={};for(const l of [1,7,10,14])for(const f of [1.5,3])out['ST-'+l+'-'+f]={plots:i.Supertrend.run(b,b.map(x=>x.close),l,f)};for(const [a,c,d,e] of [[9,26,52,26],[2,4,6,1],[9,26,52,250]]){const p=i.Ichimoku.run(b,undefined,undefined,undefined,{conversion:a,base:c,spanB:d,displacement:e});out['ICHI-'+[a,c,d,e].join('-')]={plots:p,projected:p.projected,projectionOffset:p.projectionOffset};}process.stdout.write(JSON.stringify(out));"""
 with tempfile.TemporaryDirectory(prefix='trend-indicators-') as tmp:
  file=Path(tmp)/'bars.json';file.write_text(json.dumps(bars));actual=json.loads(subprocess.run(['node','-e',js,str(library),str(file)],text=True,capture_output=True,check=True).stdout)
 checks=0;warmups=0;maximum=Decimal(0)
 def compare(want,got,path):
  global checks,warmups,maximum
  if isinstance(want,list):
   assert isinstance(got,list) and len(want)==len(got),(path,'length')
   for j,(x,y) in enumerate(zip(want,got)):compare(x,y,path+'/'+str(j))
  elif want is None:assert got is None,(path,'warmup',got);warmups+=1
  else:
   assert got is not None,(path,'missing')
   error=abs(Decimal(str(got))-Decimal(want));maximum=max(maximum,error);assert error<Decimal('0.00000001'),(path,str(error));checks+=1
 for key,ref in refs.items():
  for field,value in ref.items():compare(value,actual[key][field],key+'/'+field)
 if args.hosted_supertrend:
  wanted=refs['ST-1-1.5']['plots']
  for index,label in enumerate(['Supertrend up (1)','Supertrend down (1)']):
   exported=[Decimal(row[label]) if row[label] else None for row in records]
   compare(wanted[index],exported,'hosted/'+label)
 if args.hosted_pine_supertrend:
  up,down=refs['ST-1-1.5']['plots']
  want_line=[a if a is not None else b for a,b in zip(up,down)]
  want_direction=[-1 if a is not None else 1 if b is not None else None for a,b in zip(up,down)]
  for name,want in [('Worker Supertrend',want_line),('Worker direction',want_direction)]:
   compare(want,[Decimal(row[name]) if row[name] else None for row in records],'hosted_pine/'+name)
 result={'status':'PASS','source_rows':n,'configurations':len(refs),'hosted_supertrend_export_checked':args.hosted_supertrend,'hosted_pine_supertrend_export_checked':args.hosted_pine_supertrend,'numeric_comparisons':checks,'warmup_null_comparisons':warmups,'max_absolute_error':str(maximum),'source_sha256':hashlib.sha256(args.csv_file.read_bytes()).hexdigest(),'library_sha256':hashlib.sha256(library.read_bytes()).hexdigest(),'reference':'Decimal50 canonical Wilder ATR, Supertrend band recursion, Ichimoku rolling midpoint and displacement-minus-one','scope':'Same broker export calculation and projection-array parity; external TradingView feed/history seeding and browser rendering remain separate.'}
 args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
