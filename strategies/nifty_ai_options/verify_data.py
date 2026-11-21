"""Read-only 1/5/30m source audit and signal replay; never an executable-fill backtest."""
import argparse,json,time
from pathlib import Path
from run import client,ok,atomic,normalize,IST
from live import Reads,history
from indicator import Traditional,AIRenko
parser=argparse.ArgumentParser();parser.add_argument('--account',required=True);parser.add_argument('--session',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args();out=Path(args.output);raw=client(args.account);api=Reads(raw)
try:
    chain=ok(api.optionchain(data=dict(symbol='NSE:NIFTY50-INDEX',strikecount=50,timestamp='',greeks='1')))
    rows=chain['data']['optionsChain'];contracts=[]
    for side in ('CE','PE'):
        eligible=[r for r in rows if r.get('option_type')==side and isinstance(r.get('ltp'),(int,float)) and r['ltp']>0]
        contracts.append(min(eligible,key=lambda r:(abs(r['ltp']-40),r['symbol']))['symbol'])
    result=dict(session=args.session,read_only=True,orders_submitted=0,source_results={},strategy_pnl=None,
        limitation='Current chain selection/delta cannot establish historical target-premium selection. Signal replay only, not a P&L backtest.')
    for symbol in ['NSE:NIFTY50-INDEX']+contracts:
        result['source_results'][symbol]={}
        for frame in (1,5,30):
            from sector_heatmap.fyers_history import history as fetch
            raw_reply=ok(fetch(api,dict(symbol=symbol,resolution=str(frame),date_format=1,range_from=args.session,range_to=args.session,cont_flag=0)))
            atomic(out/(symbol.replace(':','_')+'-'+str(frame)+'m-raw.json'),raw_reply)
            try:
                data,duplicates=normalize(raw_reply.get('candles',[]),price_only=True)
            except ValueError as error:
                result['source_results'][symbol][str(frame)]=dict(status='FAILED',reason=str(error))
                continue
            raw_normalized_count=len(data)
            data=[r for r in data if 555<=__import__('datetime').datetime.fromtimestamp(r[0],IST).hour*60+__import__('datetime').datetime.fromtimestamp(r[0],IST).minute<930]
            atomic(out/(symbol.replace(':','_')+'-'+str(frame)+'m.json'),data)
            if not data:
                result['source_results'][symbol][str(frame)]=dict(status='UNAVAILABLE',reason='No history')
                continue
            renko=Traditional(400/12);indicator=AIRenko();flips=[]
            for row in data:
                for brick in renko.update(row[4]):
                    event=indicator.update(brick)
                    if event['flip']:flips.append(dict(timestamp=row[0],direction=event['direction']))
            result['source_results'][symbol][str(frame)]=dict(status='PASS',rows=len(data),excluded_outside_regular_session=raw_normalized_count-len(data),duplicate_rows=duplicates,first=data[0][0],last=data[-1][0],close=data[-1][4],signal_flips=len(flips),test_brick=400/12,
                    sizing='400 is fixture only; option brick here is deliberately NOT a strategy performance simulation')
    result['status']='PARTIAL' if any(r.get('status')!='PASS' for frames in result['source_results'].values() for r in frames.values()) else 'PASS'
    atomic(out/'data-audit.json',result);print(json.dumps(result,indent=2))
finally:raw._sector_pulse_ipv4_session.close()
