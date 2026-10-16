"""Compatibility reads for existing strategy forms, bound to one private Dhan account."""
from datetime import datetime
from .dhan_execution import IST
from .dhan_indicator_runners import configuration,KAMA_KEYS
from .kama_strategy import kama_series,kama_v6_signal
from strategies.ema_crossover.runner import TIMEFRAMES
from strategies.ema_crossover.history import position_history

def config(service,payload):
    p=dict(payload,broker='DHAN',account_id=service.execution.account['id'],execution_route='OPTIONS')
    if service.strategy=='rsi':return p
    p['strategy']='EMA_BAND_V1' if service.strategy=='band' else 'KAMA_V6'
    if service.strategy=='kama':
        if p.get('execution_mode','OPTIONS')!='OPTIONS':raise ValueError('Dhan KAMA supports bought options only.')
        p['lots']=p.get('quantity') or p.get('lots') or 1
    else:
        requested=p.get('entry_session')
        if requested not in (None,'','0915-1510'):
            raise ValueError('Dhan EMA Band requires the 09:15–15:10 entry session.')
    return p

def snapshot(service):
    s=service.runner.snapshot();s.update(broker='DHAN',account_id=service.execution.account['id'])
    if service.strategy=='kama' and s.get('config'):s['config']['execution_mode']='OPTIONS'
    if s.get('config') and service.strategy in ('band','kama'):
        s['last_event']=dict(message=s.get('message') or s.get('error') or '',signal=s.get('last_signal') or {})
    return s

def chart(service,query):
    p={k:v[0] for k,v in query.items() if v}
    saved=service.runner.state.get('config') or {}
    symbol=p.get('symbol') or p.get('underlying') or saved.get('underlying')
    if not symbol:raise ValueError('Select an underlying for this broker account.')
    timeframe=p.get('timeframe',saved.get('timeframe','5 minutes'))
    if timeframe not in TIMEFRAMES:raise ValueError('Unsupported timeframe.')
    rows=service.chart_broker.candles(dict(underlying=symbol,timeframe=timeframe,broker='DHAN',execution_route='OPTIONS'))
    count=int(p.get('bars',500))
    if not 20<=count<=500:raise ValueError('Use between 20 and 500 chart bars.')
    if service.strategy=='kama':
        settings=configuration(dict(p,broker='DHAN',strategy='KAMA_V6',execution_route='OPTIONS',underlying=symbol,timeframe=timeframe,mode='PAPER',lots='1',
            allow_reclaims=str(p.get('allow_reclaims','true')).lower() in ('1','true')))
        completed=[r for r in rows if not r.get('is_forming')]
        line=kama_series(completed,settings['kama_length'],settings['fast_length'],settings['slow_length'])
        candles=[dict(r,kama=v) for r,v in zip(completed,line)]
        sig=kama_v6_signal(completed,**{k:settings[k] for k in KAMA_KEYS})
        return dict(symbol=symbol,timeframe=timeframe,broker='DHAN',source='Dhan Data API; completed candles',candles=candles[-count:],signal=sig,squareoff_at='15:15 IST')
    from .web import ema_rsi_series
    length=int(p.get('ema_length',21))
    if not 1<=length<=500:raise ValueError('Invalid EMA length.')
    alpha=2/(length+1);high=low=None;candles=[]
    rsis=ema_rsi_series([r['close'] for r in rows])
    for i,r in enumerate(rows):
        high=r['high'] if high is None else alpha*r['high']+(1-alpha)*high
        low=r['low'] if low is None else alpha*r['low']+(1-alpha)*low
        candles.append(dict(r,ema_high=high,ema_low=low,rsi_14=rsis[i],marker=None))
    return dict(symbol=symbol,timeframe=timeframe,broker='DHAN',source='Dhan account Data API OHLCV',ema_length=length,rsi_length=14,levels=[],candles=candles[-count:])

def read(service,action,query):
    if action=='runner':return snapshot(service)
    if action in ('master-status','master-refresh'):
        rows=service.execution.master.load(datetime.fromtimestamp(service.chart_broker.clock(),IST))
        return dict(usable=True,fresh=True,source='Dhan security master',rows=len(rows),message='Dhan current master · bought NSE/BSE options only')
    if action in ('underlying-search','master-search'):
        matches=service.chart_broker.search((query.get('q') or [''])[0])
        matches=[dict(r,underlying=r['description'],underlying_kind='INDEX' if r['symbol'].split(':')[-1] in ('NIFTY','BANKNIFTY','FINNIFTY','MIDCPNIFTY','SENSEX','BANKEX','NIFTYNXT50') else 'EQUITY') for r in matches]
        return dict(matches=matches,status=dict(usable=True,fresh=True,source='Dhan security master'))
    if action in ('mode-capability','live-capability'):
        service.chart_broker.authenticated_client()
        return dict(live_submission_enabled=service.broker.live_enabled(),
            message='Dhan account authenticated · bullish buys Call; bearish buys Put · LIMIT IOC')
    if action=='chart':return chart(service,query)
    s=snapshot(service)
    if action=='tracked-positions':
        positions=[s['position']] if s.get('position') else []
        return dict(positions=positions,tracked_positions=positions,source='Dhan runner-confirmed positions only')
    if action=='execution-log':
        history=position_history(s.get('order_history',[]))
        trades=[dict(symbol=r.get('contract'),mode=r.get('mode'),status=r.get('status'),quantity=r.get('entry_filled'),entry_price=r.get('entry_price'),
                     exit_price=r.get('exit_price'),realized_pnl_rupees=r.get('realized_pnl'),opened_at=r.get('entry_time'),closed_at=r.get('exit_time'),
                     description=r.get('strategy'),exit_reason=', '.join(r.get('exit_reasons') or [])) for r in history]
        return dict(entries=s.get('events',[]),trades=trades,summary=dict(total_trades=len(trades),open_trades=sum(r['status']=='OPEN' for r in trades),
                    realized_pnl_rupees=(s.get('pnl') or {}).get('realized'),unrealized_pnl_rupees=(s.get('pnl') or {}).get('unrealized')))
    if action=='atm-option':raise ValueError('Dhan resolves the exact ATM option at entry using a fresh executable quote; no stale contract preview is substituted.')
    raise ValueError('This operation is unavailable for the selected Dhan strategy.')

def write(service,action,payload):
    if action=='runner-stop' or action=='stop':return service.runner.request_stop(payload)
    if action=='preview':return service.runner.preview(config(service,payload))
    if action=='start':return service.runner.start(payload)
    if action=='runner-start':
        p=service.runner.preview(config(service,payload))
        return service.runner.start(dict(preview_id=p['id'],confirmation=p['confirmation']))
    if action=='master-refresh':return read(service,action,{})
    raise ValueError('Unsupported Dhan form action.')
