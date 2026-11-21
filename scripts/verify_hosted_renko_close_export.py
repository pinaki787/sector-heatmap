"""Independent Decimal reference for fixed-size, close-driven, two-brick-reversal Renko."""
import csv,json,argparse
from decimal import Decimal,ROUND_FLOOR,getcontext
from pathlib import Path
getcontext().prec=50
p=argparse.ArgumentParser();p.add_argument('candles');p.add_argument('bricks');p.add_argument('--size',required=True);p.add_argument('--source',choices=['close','ohlc'],default='close');p.add_argument('--body-only',action='store_true',help='Compare open/close only when exported wick settings differ');p.add_argument('--output',required=True);args=p.parse_args()
def read(path):
 with open(path) as f:return list(csv.DictReader(f))
source=[r for r in read(args.candles) if r['provisional']=='0']
actual=read(args.bricks);size=Decimal(args.size)
assert source and size>0
level=(Decimal(source[0]['open' if args.source=='ohlc' else 'close'])/size).to_integral_value(rounding=ROUND_FLOOR)*size
direction=0;expected=[]
for candle in source:
 values={k:Decimal(candle[k]) for k in ['open','high','low','close']}
 if args.source=='close':observations=[values['close']]
 elif values['close']>=values['open']:observations=[values['open'],values['low'],values['high'],values['close']]
 else:observations=[values['open'],values['high'],values['low'],values['close']]
 for price in observations:
   while True:
    if direction==1 and price<=level-2*size:
     opening=level-size;closing=level-2*size;side=-1
    elif direction==-1 and price>=level+2*size:
     opening=level+size;closing=level+2*size;side=1
    elif direction!=-1 and price>=level+size:
     opening=level;closing=level+size;side=1
    elif direction!=1 and price<=level-size:
     opening=level;closing=level-size;side=-1
    else:break
    expected.append({'source_time_utc':candle['source_time_utc'],'open':opening,'high':max(opening,closing),'low':min(opening,closing),'close':closing})
    level=closing;direction=side
assert len(actual)==len(expected),(len(actual),len(expected))
errors=[]
for i,(want,got) in enumerate(zip(expected,actual)):
 assert got['provisional']=='0'
 assert got['source_time_utc']==want['source_time_utc'],('time',i,got['source_time_utc'],want['source_time_utc'])
 assert int(got['brick_index'])==i+1
 for key in (['open','close'] if args.body_only else ['open','high','low','close']):
  error=abs(Decimal(got[key])-want[key]);errors.append(error);assert error<Decimal('0.00000001'),(i,key,str(error))
result={'status':'PASS','source_candles':len(source),'confirmed_bricks':len(actual),'size':args.size,'body_only':args.body_only,'construction_source':args.source,'numeric_comparisons':len(errors),'source_time_comparisons':len(actual),'max_absolute_error':str(max(errors,default=Decimal(0))),'source_range':[source[0]['source_time_utc'],source[-1]['source_time_utc']],'scope':('Hosted PAXGUSD Delta30m fixed selected box '+args.source+'; Decimal50 floor-grid anchor and two-brick reversal reference. '+('Open/close body only; exported wicks excluded.' if args.body_only else 'All OHLC with projections/wicks OFF.')+(' OHLC path assumption: rising O-L-H-C, falling O-H-L-C; actual intrabar tick path is not recovered.' if args.source=='ohlc' else '')+' No external TradingView seed/feed parity established.')}
Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
