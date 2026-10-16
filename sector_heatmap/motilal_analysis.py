"""Native captured-candle providers for existing Sector Rotation and Handoff."""
from datetime import datetime,timedelta
import math,threading,time
from .motilal_strategy_broker import Broker,BROKER,IST
from .sector_service import CandleHistoryProvider,SectorAnalysisService
from .handoff import build_long_option_proposals,build_defined_risk_spreads
from .sectors import BENCHMARK_SYMBOL

def native_liquidity(quote,now):
    """Depth freshness cannot freshen volume/OI from an older LTP packet."""
    fresh=all(isinstance(quote.get(key),(int,float)) and not isinstance(quote.get(key),bool)
              and math.isfinite(quote[key]) and 0<=now-quote[key]<=15
              for key in ('ltp_exchange_at','ltp_received_at'))
    def value(key):
        result=quote.get(key)
        return result if fresh and isinstance(result,int) and not isinstance(result,bool) and result>=0 else None
    return dict(oi=value('open_interest'),volume=value('cumulative_volume'))

class Provider(CandleHistoryProvider):
    broker=BROKER
    def __init__(self,execution):
        super().__init__(None);self.execution=execution;self.adapter=Broker(execution)
    def prepare(self):self.execution.ready()
    def resolve(self,symbol):return self.adapter.underlying(symbol)
    def get(self,symbol,timeframe):
        self.prepare();host=self.resolve(symbol);self.adapter.subscribe(symbol);self.adapter.start()
        minutes={'15m':15,'1h':60,'daily':375,'weekly':375}[timeframe]
        rows=(self.execution.history.session_candles(host['symbol'],session_open='09:15',minutes=375,limit=3000)
              if timeframe in {'daily','weekly'} else
              self.execution.history.candles(host['symbol'],minutes,limit=3000,session_open='09:15'))
        # Volume-dependent candidate analysis cannot treat absent volume as zero.
        rows=[r for r in rows if r['volume_available']]
        if timeframe=='weekly':
            from .indicators import resample_weekly
            rows=resample_weekly(rows)
        return rows

class Sectors(SectorAnalysisService):
    def __init__(self,execution):
        self.execution=execution
        super().__init__('',state_file=execution.folder/'motilal-sector-history.json',provider=Provider(execution))
    def refresh(self):
        self.provider.prepare();super().refresh()
        from .sectors import SECTOR_DEFINITIONS,equity_symbol
        moves={}
        for sector in SECTOR_DEFINITIONS:
            for item in sector.constituents:
                if item.ticker in moves:continue
                try:
                    symbol=equity_symbol(item.ticker);bars=self.provider.get(symbol,'daily')
                    price,stamp=self.provider.adapter.live_price(dict(underlying=symbol),time.time())
                    if not bars:continue
                    previous=bars[-1]['close']
                    moves[item.ticker]=dict(change=(price/previous-1)*100,stamp=stamp)
                except (ValueError,KeyError):continue
        with self.lock:
            for value in self.snapshots.values():
                value.update(broker=BROKER,provider=BROKER,account_id=self.execution.account['id'],source='Motilal native captured candles; warming up until completed history is sufficient')
                value['refresh_state']['message']='Motilal captured history; insufficient periods remain unavailable'
                for sector in value['sectors']:
                    drivers=[]
                    for item in sector['constituents']:
                        quote=moves.get(item['ticker']);change=quote['change'] if quote else None
                        drivers.append(dict(item,change=change,provider=BROKER,provider_tick_timestamp_iso=datetime.fromtimestamp(quote['stamp'],IST).isoformat() if quote else None,contribution=item['weight']*change/100 if change is not None else None))
                    drivers.sort(key=lambda r:abs(r['contribution']) if r['contribution'] is not None else -1,reverse=True)
                    sector['constituent_movers']=drivers;sector['top_contributors']=[r for r in drivers if r['contribution'] is not None][:3]
    def snapshot(self,mode='intraday',sector_id=None):
        self.execution.ready();value=super().snapshot(mode,sector_id)
        value.update(broker=BROKER,provider=BROKER,account_id=self.execution.account['id'],source='Motilal native captured candles only',history_policy='No FYERS/Dhan history; missing periods stay unavailable until capture warmup completes.')
        return value

class Handoff:
    broker=BROKER
    def __init__(self,execution,sectors):self.execution=execution;self.sectors=sectors;self.adapter=sectors.provider.adapter
    def candidates(self,mode):
        snap=self.sectors.snapshot(mode)
        result=self.sectors.alignment_candidates([dict(r,drivers=r.get('constituent_movers',[])) for r in snap.get('sectors',[])],mode)
        result.update(broker=BROKER,account_id=self.execution.account['id'],source='Motilal captured candles only');return result
    def positions(self):
        result=[]
        for row in self.adapter.positions():
            meta=self.adapter.contract(row['symbol']);exchange=meta['exchange'].removesuffix('FO')
            # Conservative underlying exposure excludes all of its cash/options.
            result.append(dict(symbol=exchange+':'+meta['underlying']+'-EQ',netQty=row['netQty']))
        return result
    def orders(self):
        # Include external/manual orders too; runner reconciliation filters those out.
        from .motilal_strategy_broker import STATES
        result=[]
        for row in self.adapter.service.book('orders')['data']:
            state=STATES.get(str(row.get('orderstatus') or '').strip().upper())
            if state is None:raise ValueError('Native order status unavailable; duplicate exposure cannot be excluded.')
            if state not in (3,4,6):continue
            meta=self.adapter.contract('MO:'+str(row['exchange'])+':'+str(row['symboltoken']))
            result.append(dict(symbol=meta['exchange'].removesuffix('FO')+':'+meta['underlying']+'-EQ',status=state))
        return result
    def funds(self):return dict(connected=True,available_funds=self.adapter.funds('NSE'))
    def quote(self,symbol):return self.adapter.live_price(dict(underlying=symbol),time.time())
    def tick(self,symbol):return self.adapter.host_tick_size(symbol)
    def chain(self,symbol,direction):
        rows=self.adapter.option_rows(symbol);spot,_=self.quote(symbol)
        if not rows:raise ValueError('No native listed option contracts.')
        expiry=min(r['expiry'] for r in rows);rows=[r for r in rows if r['expiry']==expiry]
        strike=min({r['strike'] for r in rows},key=lambda x:(abs(x-spot),x))
        # Only the native ATM pair: an unavailable ATM quote must never fall
        # through to a nearby quoted strike now that spreads are excluded.
        rows=[r for r in rows if r['strike']==strike]
        self.adapter.start()
        for r in rows:self.adapter.subscribe(r['symbol'])
        chain=[dict(option_type='',ltp=spot)];masters={}
        epoch=str(int(datetime.fromisoformat(expiry).replace(hour=15,minute=30,tzinfo=IST).timestamp()))
        for r in rows:
            try:q=self.adapter.quote(r['symbol'])
            except ValueError:continue
            chain.append(dict(symbol=r['symbol'],option_type=r['option_type'],strike_price=r['strike'],ltp=q.get('ltp'),bid=q['bid'],ask=q['ask'],**native_liquidity(q,self.adapter.clock()),greeks={}))
            masters[r['symbol']]=dict(exchange_token=str(r['token']),lot_size=r['lot_size'],tick_size=r['tick_size'],expiry_epoch=epoch)
        if len(chain)==1:raise ValueError('Native option quotes are warming up; refresh after subscription. Missing native liquidity stays unavailable.')
        return {'data':{'optionsChain':chain}},dict(date=datetime.fromisoformat(expiry).strftime('%d-%m-%Y'),expiry=epoch),masters
    def options(self,symbol,direction,risk):
        chain,expiry,masters=self.chain(symbol,direction)
        result=build_long_option_proposals(chain,expiry,masters,direction,risk,require_greeks=False)
        result['broker']=BROKER
        for proposal in result.get('proposals',[]):
            proposal['broker']=BROKER;proposal['account_id']=self.execution.account['id']
            for leg in proposal.get('legs',[]):leg['broker']=BROKER
        return result
