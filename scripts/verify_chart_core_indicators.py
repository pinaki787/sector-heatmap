"""Compare current chart studies with independent Decimal calculations on an exported OHLC CSV."""
import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def average(values, length):
    return [None if i+1<length else sum(values[i+1-length:i+1])/length for i in range(len(values))]


def exponential(values, length):
    alpha=Decimal(2)/(length+1)
    result=[]
    for value in values:
        result.append(value if not result else result[-1]+alpha*(value-result[-1]))
    return result


def wilder(values, length):
    result=[None]*min(len(values),length-1)
    if len(values)<length:return result
    result.append(sum(values[:length])/length)
    for value in values[length:]:result.append((result[-1]*(length-1)+value)/length)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--provider')
    parser.add_argument('--symbol')
    parser.add_argument('--interval')
    args=parser.parse_args()
    records=list(csv.DictReader(args.csv_file.open()))
    if len(records)<50:raise ValueError('At least50source candles required.')
    root=Path(__file__).resolve().parents[1]
    with localcontext() as context:
        context.prec=50
        closes=[Decimal(row['close']) for row in records]
        bars=[{key:float(row[key]) for key in ('open','high','low','close')} for row in records]
        sma=average(closes,20);ema=exponential(closes,20)
        deltas=[b-a for a,b in zip(closes,closes[1:])]
        gains=wilder([max(Decimal(0),v) for v in deltas],14)
        losses=wilder([max(Decimal(0),-v) for v in deltas],14)
        rsi=[None]+[None if gain is None else Decimal(100) if loss==0 else Decimal(100)-Decimal(100)/(1+gain/loss) for gain,loss in zip(gains,losses)]
        deviation=[None if i<19 else (sum((v-sma[i])**2 for v in closes[i-19:i+1])/20).sqrt()*2 for i in range(len(closes))]
        upper=[None if d is None else m+d for m,d in zip(sma,deviation)];lower=[None if d is None else m-d for m,d in zip(sma,deviation)]
        fast=exponential(closes,12);slow=exponential(closes,26);macd=[f-s for f,s in zip(fast,slow)];signal=exponential(macd,9);histogram=[m-s for m,s in zip(macd,signal)]
        tr=[]
        for i,row in enumerate(records):
            h,l=Decimal(row['high']),Decimal(row['low'])
            tr.append(h-l if i==0 else max(h-l,abs(h-closes[i-1]),abs(l-closes[i-1])))
        reference={'SMA20':sma,'EMA20':ema,'RSI14':rsi,'BBUpper':upper,'BBBasis':sma,'BBLower':lower,'MACD':macd,'MACDSignal':signal,'MACDHistogram':histogram,'ATR14':wilder(tr,14)}
        js='''const fs=require('node:fs');require(process.argv[1]);const b=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),v=b.map(x=>x.close),i=globalThis.SectorPulseChartStudies.indicators;
const bb=i.BB.run(b,v,20,2,{}),m=i.MACD.run(b,v,undefined,undefined,{fast:12,slow:26,signal:9});
process.stdout.write(JSON.stringify({SMA20:i.SMA.run(b,v,20,undefined,{})[0],EMA20:i.EMA.run(b,v,20,undefined,{})[0],RSI14:i.RSI.run(b,v,14,undefined,{})[0],BBUpper:bb[0],BBBasis:bb[1],BBLower:bb[2],MACD:m[0],MACDSignal:m[1],MACDHistogram:m[2],ATR14:i.ATR.run(b,v,14,undefined,{smoothing:'RMA'})[0]}));'''
        with tempfile.TemporaryDirectory(prefix='chart-core-indicators-') as folder:
            data=Path(folder)/'bars.json';data.write_text(json.dumps(bars))
            actual=json.loads(subprocess.run(['node','-e',js,str(root/'chart-workspace-studies.js'),str(data)],check=True,capture_output=True,text=True).stdout)
        report=[]
        for name,expected in reference.items():
            values=actual[name]
            if len(values)!=len(expected):raise ValueError(name+'length mismatch')
            mismatched_warmup=sum((a is None)!=(e is None) for a,e in zip(values,expected))
            errors=[abs(Decimal(str(a))-e) for a,e in zip(values,expected) if a is not None and e is not None]
            maximum=max(errors)
            report.append({'plot':name,'compared_rows':len(errors),'warmup_mismatches':mismatched_warmup,'max_absolute_error':float(maximum),'pass':mismatched_warmup==0 and maximum<Decimal('0.00000001')})
    result={'provider':args.provider,'symbol':args.symbol,'interval':args.interval,'settings':{'SMA':20,'EMA':20,'RSI':14,'BB':[20,2],'MACD':[12,26,9],'ATR':[14,'RMA']},'source_csv_sha256':hashlib.sha256(args.csv_file.read_bytes()).hexdigest(),'study_library_sha256':hashlib.sha256((root/'chart-workspace-studies.js').read_bytes()).hexdigest(),'source_rows':len(records),'independent_reference':'Python Decimal50digits','plots':report,'all_passed':all(x['pass'] for x in report),'scope':'Current built-in library on identical exported candles; not external TradingView parity or all129studies.'}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if not result['all_passed']:raise SystemExit(1)


if __name__=='__main__':main()
