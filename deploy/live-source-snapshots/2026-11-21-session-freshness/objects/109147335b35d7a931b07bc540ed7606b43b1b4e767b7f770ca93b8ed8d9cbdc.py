#!/usr/bin/env python3
"""Standalone FYERS Nifty AI Renko research runner. Never activates dashboard runners."""
import argparse,csv,fcntl,hashlib,json,os,sys,time
from pathlib import Path
from datetime import datetime,date,timedelta
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
try:from .core import Strategy,select_contract
except ImportError:from core import Strategy,select_contract
IST=ZoneInfo('Asia/Kolkata')

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out:
        json.dump(value,out,indent=2);out.flush();os.fsync(out.fileno())
    os.replace(temp,path)
    directory_fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory_fd)
    finally:os.close(directory_fd)

def client(account):
    # Explicit owner, verified registry binding. Read only, never refresh/login/change HOME.
    import sqlite3
    if not isinstance(account,str) or len(account)!=32 or any(c not in '0123456789abcdef' for c in account):raise ValueError('Invalid explicit account id')
    folder=ROOT/'.private/dashboard-login/accounts'/account
    with sqlite3.connect((ROOT/'.private/dashboard-login/registry.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        binding=db.execute('select broker,credential_identity from accounts where id=?',(account,)).fetchone()
    credentials=json.loads((folder/'credentials.json').read_text())
    saved=json.loads((folder/'home/.fyers/token.json').read_text())
    app=credentials.get('FYERS_APP_ID')
    if not app or not binding or binding[0]!='FYERS' or hashlib.sha256(('FYERS|'+app).encode()).hexdigest()!=binding[1] or saved.get('app_id')!=app:raise ValueError('Account/token owner mismatch')
    from sector_heatmap.fyers_transport import client as factory
    return factory(client_id=app,token=saved['access_token'])

def ok(reply):
    if not isinstance(reply,dict) or reply.get('s')!='ok':
        code=reply.get('code') if isinstance(reply,dict) else None
        raise ValueError('FYERS read failed, code='+str(code)+'; no retry or credential mutation')
    return reply

def normalize(rows,price_only=False):
    unique={};duplicates=0
    for row in rows:
        if row[0] in unique:
            if unique[row[0]]!=row:
                if not price_only or unique[row[0]][:5]!=row[:5]:raise ValueError('Conflicting duplicate history OHLC timestamp')
                unique[row[0]]=list(row[:5])+[None] # volume unavailable; unused by this strategy
            duplicates+=1
            continue
        unique[row[0]]=row
    return sorted(unique.values()),duplicates

def six_hour(rows):
    """Session-aligned 09:15-15:15 and 15:15-15:30, start labels, excludes 15:30.
    Diagnostic aggregation only: NOT a native Renko OHLC ATR calculation.
    """
    groups={}
    for r in rows:
        dt=datetime.fromtimestamp(r[0],IST);minute=dt.hour*60+dt.minute
        if not 555<=minute<930:continue
        bucket=(dt.date().isoformat(),(minute-555)//360)
        groups.setdefault(bucket,[]).append(r)
    return [dict(session=k[0],bucket=k[1],timestamp=v[0][0],open=v[0][1],high=max(r[2] for r in v),low=min(r[3] for r in v),close=v[-1][4],count=len(v)) for k,v in sorted(groups.items())]

def probe(args):
    api=client(args.account)
    try:
        profile=ok(api.get_profile())
        identity=(profile.get('data') or {}).get('fy_id')
        if not identity:raise ValueError('Missing FYERS account identity')
        chain=ok(api.optionchain(data=dict(symbol='NSE:NIFTY50-INDEX',strikecount=50,timestamp=args.expiry or '',greeks='1')))
        data=chain.get('data',{})
        rows=data.get('optionsChain',[])
        summary=dict(read_only=True,account_sha256=hashlib.sha256(str(identity).encode()).hexdigest(),checked_at=datetime.now(IST).isoformat(),
                     expiry_data=data.get('expiryData'),contract_count=len(rows),greeks_rows=sum(isinstance(r.get('greeks'),dict) for r in rows),orders_submitted=0)
        summary['nearest_by_side']={}
        for side in ('CE','PE'):
            candidates=[r for r in rows if r.get('option_type')==side and isinstance(r.get('ltp'),(int,float)) and r['ltp']>0]
            if candidates:
                r=min(candidates,key=lambda r:(abs(r['ltp']-args.target),r['symbol']))
                summary['nearest_by_side'][side]={k:r.get(k) for k in ('symbol','ltp','option_type','greeks')}
        from sector_heatmap.fyers_history import history
        raw=ok(history(api,dict(symbol='NSE:NIFTY50-INDEX',resolution='15',date_format=1,range_from=args.start,range_to=args.end,cont_flag=0)))
        atomic(Path(args.output)/'history-15m-raw.json',raw)
        atomic(Path(args.output)/'chain-raw.json',chain)
        candles,dupes=normalize(raw.get('candles',[]),price_only=True)
        aggregates=six_hour(candles)
        summary.update(history_rows=len(raw.get('candles',[])),unique_rows=len(candles),duplicate_timestamp_rows=dupes,volume_conflict_timestamps=[r[0] for r in candles if r[5] is None],aggregates=aggregates,
                       timestamp_label_assumption='start; session excludes 15:30; no parity certification')
        from live import Master
        master=Master(Path(args.output)/'master')
        for side,contract in summary['nearest_by_side'].items():
            contract['master']=master(contract['symbol'])
        positions=ok(api.positions()).get('netPositions')
        orders=ok(api.orderbook()).get('orderBook')
        if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Unknown reconciliation response')
        summary['existing_nifty_positions']=sum(int(p.get('netQty',0))!=0 for p in positions if str(p.get('symbol','')).startswith('NSE:NIFTY'))
        summary['existing_nifty_pending_orders']=sum(p.get('status') in (1,4,6) for p in orders if str(p.get('symbol','')).startswith('NSE:NIFTY'))
        summary['market_status']=ok(api.market_status())
        out=Path(args.output)
        atomic(out/'probe.json',summary);atomic(out/'history-15m.json',raw);atomic(out/'chain.json',chain)
        print(json.dumps({k:v for k,v in summary.items() if k not in ('aggregates','expiry_data','market_status')},indent=2))
    finally:api._sector_pulse_ipv4_session.close()

def replay(args):
    config=json.loads(Path(args.config).read_text())
    if args.live:raise ValueError('Replay cannot send orders')
    engine=Strategy(config)
    if config.get('contract'):engine.reset_contract(config['contract'],config['selection_delta'])
    events=[json.loads(line) for line in Path(args.events).read_text().splitlines() if line.strip()]
    # Equal-time order is explicit in the input; never silently reorder observations.
    if any(events[i]['timestamp']>events[i+1]['timestamp'] for i in range(len(events)-1)):raise ValueError('Events must be chronological')
    actions=[]
    for event in events:
        for action in engine.update(event):
            actions.append(action);print(json.dumps(action))
    atomic(args.output,dict(dry_run=True,events=len(events),actions=actions,position=engine.position,
                           pnl=None,pnl_reason='Signal replay does not establish executable option fills'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Real orders: stream only; requires additional user-set environment opt-in')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('probe',help='Read-only exact-owner auth, chain/Greeks and history audit')
    p.add_argument('--account',required=True);p.add_argument('--expiry');p.add_argument('--target',type=float,default=40)
    p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('replay',help='Offline dry-run signals, no broker dependency')
    p.add_argument('--config',required=True);p.add_argument('--events',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('preflight',help='Read-only account, dated baseline, expiry, lot and Greeks checks')
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('stream',help='Start standalone WebSocket runtime, PAPER by default')
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.live and args.command!='stream':parser.error('--live is only valid for stream')
    if args.command in ('stream','preflight'):
        from live import stream,preflight
        {'stream':stream,'preflight':preflight}[args.command](args)
    else:{'probe':probe,'replay':replay}[args.command](args)
if __name__=='__main__':
    sys.modules['run']=sys.modules[__name__]
    try:main()
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as error:
        print('ERROR: '+str(error),file=sys.stderr);sys.exit(2)
