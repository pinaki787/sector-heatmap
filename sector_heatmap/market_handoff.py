"""Broker-backed index/commodity ATM option plans and bounded AI review."""
from copy import deepcopy
import math
import time
from .exposure_guard import open_exposures,matches_exposure,broker_exposures
from .persistent_jobs import checkpoint

FRAMES={'5 minutes':300,'15 minutes':900,'1 hour':3600}


def native_adapter(base,service):
    class AnalysisBroker(base):
        def underlying(self,symbol):
            if symbol.startswith('MO:'):return self.contract(symbol)
            if symbol.startswith(('NSE_FNO:','BSE_FNO:','MCX_COMM:')):
                segment,security=symbol.split(':',1)
                rows=[r for r in self._rows() if str(r['SEM_SMST_SECURITY_ID'])==security and self._segment(r)==segment]
                if len(rows)!=1:raise ValueError('Option history contract has no unique native master mapping.')
                self.contract(symbol)  # Validate current contract/expiry too.
                return rows[0]
            return super().underlying(symbol)
    return AnalysisBroker(service)


def instrument_kind(meta):
    if not isinstance(meta,dict):return ''
    if meta.get('SEM_SEGMENT')=='I':return 'INDEX'
    return str(meta.get('instrument') or meta.get('kind') or meta.get('SEM_INSTRUMENT_NAME') or '').upper()


def catalog(broker,broker_name,clock=time.time):
    result=[];unavailable=[]
    def rows(segment):
        try:return broker.rows(segment)
        except ValueError as error:
            unavailable.append(dict(segment=segment,reason=str(error)));return []
    if broker_name=='FYERS':
        now=clock()
        for exchange in ('NSE','BSE'):
            option_roots={r[13] for r in rows(exchange+'_FO') if len(r)>16 and r[16] in ('CE','PE') and float(r[8] or 0)>now}
            for row in rows(exchange+'_CM'):
                if len(row)>16 and row[9].endswith('-INDEX') and row[13] in option_roots:
                    result.append(dict(symbol=row[9],name=row[1],market='INDEX'))
        commodity_rows=rows('MCX_COM');roots={r[13] for r in commodity_rows if len(r)>16 and r[16] in ('CE','PE') and float(r[8] or 0)>now}
        nearest={}
        for row in commodity_rows:
            if len(row)<=16 or row[16]!='XX' or row[13] not in roots or float(row[8] or 0)<=now:continue
            if row[13] not in nearest or float(row[8])<float(nearest[row[13]][8]):nearest[row[13]]=row
        result.extend(dict(symbol=r[9],name=r[1],market='COMMODITY') for r in nearest.values())
    else:
        for text in ('NIFTY','BANKNIFTY','SENSEX','FINNIFTY','CRUDEOIL','NATURALGAS','GOLD','SILVER','COPPER'):
            found=broker.search(text,market='ALL')
            for row in found.get('matches',[]) if isinstance(found,dict) else found:
                symbol=row.get('symbol')
                if not symbol:continue
                meta=broker.underlying(symbol)
                kind=instrument_kind(meta)
                if kind in ('INDEX','FUTCOM','FUTIDX','FUTURES','COMMODITY') or symbol.endswith('-INDEX') or symbol.startswith('MCX:'):
                    result.append(dict(symbol=symbol,name=row.get('description',row.get('name',symbol)),market='COMMODITY' if 'MCX' in symbol else 'INDEX'))
    return dict(broker=broker_name,instruments=list({r['symbol']:r for r in result}.values()),unavailable=unavailable,source='Selected broker current symbol master')


def indicators(rows,seconds,now):
    bars=[dict(r) for r in rows if not r.get('is_forming') and r['timestamp']+seconds<=now]
    bars.sort(key=lambda r:r['timestamp'])
    if len(bars)<35:raise ValueError('At least 35 completed broker candles are required.')
    if len({r['timestamp'] for r in bars})!=len(bars):raise ValueError('Duplicate broker candle timestamps.')
    for r in bars:
        values=[r.get(k) for k in ('open','high','low','close')]
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values) or not r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']:
            raise ValueError('Broker OHLC is invalid; no synthetic candles were substituted.')
    if now-(bars[-1]['timestamp']+seconds)>seconds*2:raise ValueError('Latest completed broker candle is stale for this timeframe.')
    fast=slow=bars[0]['close'];gain=loss=atr=None;previous=bars[0]['close'];changes=[];ranges=[]
    for r in bars[1:]:
        close=r['close'];fast+=2/11*(close-fast);slow+=2/31*(close-slow)
        move=close-previous;changes.append(move);ranges.append(max(r['high']-r['low'],abs(r['high']-previous),abs(r['low']-previous)))
        if len(changes)==14:
            gain=sum(max(v,0) for v in changes)/14;loss=sum(max(-v,0) for v in changes)/14;atr=sum(ranges)/14
        elif len(changes)>14:
            gain=(gain*13+max(move,0))/14;loss=(loss*13+max(-move,0))/14;atr=(atr*13+ranges[-1])/14
        previous=close
    rsi=100 if loss==0 and gain else 50 if loss==gain==0 else 100-100/(1+gain/loss)
    trend='BULLISH' if bars[-1]['close']>fast>slow else 'BEARISH' if bars[-1]['close']<fast<slow else 'MIXED'
    return dict(timestamp=bars[-1]['timestamp'],close=bars[-1]['close'],ema10=round(fast,4),ema30=round(slow,4),rsi14=round(rsi,2),atr14=round(atr,6),
                recent_low=min(r['low'] for r in bars[-5:]),recent_high=max(r['high'] for r in bars[-5:]),trend=trend,completed_bars=len(bars))


def _wait(read,seconds=8,clock=time.monotonic):
    deadline=clock()+seconds;error=None
    while clock()<deadline:
        checkpoint()
        try:return read()
        except (ValueError,RuntimeError) as exc:error=exc
        time.sleep(.25)
    raise ValueError(str(error or 'Broker data unavailable.'))


def premium_plan(broker,config,direction,clock=time.time):
    contract=broker.resolve(config,direction)
    quote=_wait(lambda:broker.quote(contract['symbol']))
    now=clock();bid,ask=quote.get('bid'),quote.get('ask')
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in (bid,ask)) or not 0<bid<=ask:raise ValueError('Executable option bid/ask unavailable.')
    for key in ('exchange_at','received_at'):
        if not isinstance(quote.get(key),(int,float)) or not 0<=now-quote[key]<=15:raise ValueError('Option quote timestamp is missing or stale.')
    spread=(ask-bid)/((ask+bid)/2)*100
    if spread>5:raise ValueError('Option spread exceeds 5%; no recommended premium entry.')
    option_rows=broker.candles({**config,'underlying':contract['symbol'],'timeframe':'5 minutes'})
    option=indicators(option_rows,300,now)
    tick=float(contract['tick_size']);entry=round(math.ceil(ask/tick-1e-9)*tick,8)
    stop=max(tick,min(option['recent_low']-tick,entry-option['atr14']))
    stop=round(math.floor(stop/tick)*tick,8)
    if not 0<stop<entry or entry-stop>entry*.5:raise ValueError('Completed option history does not support a bounded premium stop.')
    target=round(math.ceil((entry+2*(entry-stop))/tick)*tick,8)
    return dict(symbol=contract['symbol'],direction=direction,action='BUY',option_type='CE' if direction=='BULLISH' else 'PE',
                entry=entry,target=target,stop_loss=stop,lot_size=contract['lot_size'],tick_size=tick,expiry=contract.get('expiry_epoch',contract.get('expiry')),
                bid=bid,ask=ask,spread_pct=round(spread,3),quote_at=quote['exchange_at'],price_unit='option premium points',
                risk_per_unit=round(entry-stop,8),reward_to_risk=2,method='Completed option five-bar swing low and ATR14 stop; target two times premium risk.',
                premium_history_at=option['timestamp'],contract_source='Selected broker current symbol master and native ATM resolver')


def analyze(payload,broker,ai,broker_name,account_id,clock=time.time):
    symbols=list(dict.fromkeys(str(s).strip().upper() for s in payload.get('symbols',[]) if str(s).strip()))
    if not 1<=len(symbols)<=6:raise ValueError('Choose one to six exact index/commodity symbols from the selected broker.')
    exposures=broker_exposures(broker)
    result=dict(kind='MARKET_HANDOFF',ai_provider=getattr(ai,'provider',None),broker=broker_name,account_id=account_id,created_at=clock(),instruments=[],exclusions=[],order_authority='NONE')
    broker.start()
    try:
        for symbol in symbols:
            checkpoint('Collecting '+symbol,result)
            if matches_exposure(symbol,exposures):
                result['exclusions'].append(dict(symbol=symbol,reason='Open position or pending entry already exists for this underlying.'));continue
            try:
                meta=broker.underlying(symbol)
                if isinstance(meta,list):valid=symbol.endswith('-INDEX') or symbol.startswith('MCX:') and meta[16]=='XX'
                else:valid=instrument_kind(meta) in ('INDEX','FUTCOM','FUTIDX','FUTURE','FUTURES','COMMODITY') or symbol.endswith('-INDEX')
                if not valid:raise ValueError('Select an index or commodity future from this broker master.')
                config=dict(underlying=symbol,timeframe='5 minutes',execution_route='OPTIONS',lots=1,commodity_holding='INTRADAY')
                price,stamp=_wait(lambda:broker.live_price(config,clock()))
                if not math.isfinite(price) or price<=0 or not 0<=clock()-stamp<=15:raise ValueError('Fresh underlying tick required.')
                frames={frame:indicators(broker.candles({**config,'timeframe':frame}),seconds,clock()) for frame,seconds in FRAMES.items()}
                plans=[];unavailable=[]
                for direction in ('BULLISH','BEARISH'):
                    checkpoint('Checking native ATM '+direction.lower()+' premium for '+symbol,result)
                    try:plans.append(premium_plan(broker,config,direction,clock))
                    except (ValueError,RuntimeError) as error:unavailable.append(dict(direction=direction,reason=str(error)))
                result['instruments'].append(dict(symbol=symbol,spot=price,underlying_quote_at=stamp,timeframes=frames,plans=plans,unavailable=unavailable))
            except (ValueError,RuntimeError) as error:result['exclusions'].append(dict(symbol=symbol,reason=str(error)))
        checkpoint('Broker evidence collected.',result)
        if result['instruments']:
            # Send public market evidence only, never account/position/funds data.
            review=ai.review({'instruments':deepcopy(result['instruments'])})
            recommendations={r['symbol']:r for r in review['recommendations']}
            for instrument in result['instruments']:
                recommendation=recommendations[instrument['symbol']]
                selected=next((p for p in instrument['plans'] if p['direction']==recommendation['decision']),None)
                if recommendation['decision']!='WAIT' and not selected:
                    recommendation={**recommendation,'decision':'WAIT','rationale':'Executable premium plan unavailable. '+recommendation['rationale']}
                if selected:
                    try:
                        selected=premium_plan(broker,dict(underlying=instrument['symbol'],timeframe='5 minutes',execution_route='OPTIONS',lots=1,commodity_holding='INTRADAY'),recommendation['decision'],clock)
                    except (ValueError,RuntimeError) as error:
                        selected=None
                        recommendation={**recommendation,'decision':'WAIT','rationale':'Premium evidence could not be refreshed after AI analysis: '+str(error)}
                instrument['recommendation']=recommendation
                instrument['recommended_plan']=selected
            result['ai_review']={k:v for k,v in review.items() if k!='recommendations'}
        else:result['ai_review']=dict(provider=getattr(ai,'provider',None),state='NO_ELIGIBLE_EVIDENCE',summary='No selected-broker instrument has complete entry evidence; no AI request made.')
        # Exposure may have changed while history or AI analysis was in flight.
        fresh=broker_exposures(broker)
        eligible=[]
        for instrument in result['instruments']:
            if matches_exposure(instrument['symbol'],fresh):result['exclusions'].append(dict(symbol=instrument['symbol'],reason='Exposure appeared during analysis; recommendation excluded.'))
            else:eligible.append(instrument)
        result['instruments']=eligible;result['completed_at']=clock()
        checkpoint('Recommendations saved.',result)
        return result
    finally:
        broker.stop()  # Only this analysis adapter; never the runner's adapter.
