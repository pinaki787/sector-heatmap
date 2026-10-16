"""Owner-bound routes reused by Renko, Screener, Handoff and Sector Rotation."""
from .persistent_jobs import checkpoint
import hashlib,json,re,secrets,threading,time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from .motilal_service import Service
from .motilal_strategy_service import Registry
from .motilal_strategy_broker import Broker,BROKER,IST
from .motilal_analysis import Sectors,Handoff
from .handoff import validate_risk_policy,evidence_conviction,build_equity_opportunity
from .analysis import calculate_timeframe_state,mtf_alignment
from .analysis_config import TIMEFRAMES
from .screener_paging import page_request,MAX_SYMBOLS

class Routes:
    def __init__(self,root,allowed=lambda:True):
        self.root=Path(root);self.allowed=allowed;self.lock=threading.RLock();self.services={};self.sectors={};self.strategies={}
    def execution(self,store,user,aid):
        account=store.account(user,aid)
        if account['broker']!=BROKER:raise PermissionError('Select this user’s Motilal account.')
        with self.lock:
            service=self.services.get(aid)
            if service is None:
                owner={'id':user['id']}
                def permitted():
                    try:return self.allowed() and bool(store.account(owner,aid)['live_enabled'])
                    except PermissionError:return False
                service=Service(store.folder(account),account,execution_allowed=permitted)
                from .motilal_history_seed import Seed
                service.history_seed=Seed(store,user,account)
                self.services[aid]=service
            service.account=dict(account)
            service.ready();service.client.live_enabled=bool(account['live_enabled']) and self.allowed()
            return service
    def sector(self,execution):
        aid=execution.account['id']
        with self.lock:
            if aid not in self.sectors:
                service=Sectors(execution);self.sectors[aid]=service;service.start()
            return self.sectors[aid]
    def handoff(self,execution):return Handoff(execution,self.sector(execution))
    def renko(self,execution,handler,action,query,payload):
        aid=execution.account['id']
        with self.lock:
            if aid not in self.strategies:self.strategies[aid]=Registry(execution,self.root)
        return self.strategies[aid].dispatch(handler,action,query,payload)
    def screener(self,execution,payload):
        symbols,offset,limit,page,prices,key=page_request(payload)
        sectors=self.sector(execution);adapter=sectors.provider.adapter
        benchmark=sectors._timeframe_candles('NSE:NIFTY50-INDEX');result=[]
        for ticker in page:
            checkpoint("Analyzing "+ticker+" with Motilal evidence.")
            symbol='NSE:'+ticker+'-EQ'
            try:
                candles=sectors._timeframe_candles(symbol)
                states={tf:calculate_timeframe_state(tf,candles.get(tf,[]),benchmark.get(tf,[]),sectors._quality(tf,candles.get(tf,[]))) for tf in TIMEFRAMES}
                stripped={tf:{k:v for k,v in state.items() if k!='series'} for tf,state in states.items()}
                alignment=mtf_alignment(states)
                if any(s.get('data_quality') in {'UNAVAILABLE','STALE','INSUFFICIENT DATA'} for s in states.values()):
                    result.append(dict(symbol=ticker,decision='REJECT',reason='Motilal-only history is warming up; completed 15m, 1h, daily and weekly evidence is insufficient.',alignment=alignment,timeframe_states=stripped));continue
                if alignment not in {'FULL BULLISH ALIGNMENT','FULL BEARISH ALIGNMENT'}:
                    result.append(dict(symbol=ticker,decision='WATCHLIST',reason='Completed native timeframes do not fully agree.',alignment=alignment,timeframe_states=stripped));continue
                direction='BULLISH' if 'BULLISH' in alignment else 'BEARISH';price,_=adapter.live_price(dict(underlying=symbol),time.time())
                candidate=dict(key='screener:'+ticker,kind='stock',ticker=ticker,name=ticker,symbol=symbol,direction=direction,mtf_alignment=alignment,data_quality='READY',price=price,timeframe_states=stripped)
                plan=build_equity_opportunity(candidate,dict(minimum_reward_to_risk=2.0))
                stop=(plan.get('recommended_invalidation') or {}).get('price');entry=plan.get('entry')
                if not stop or not entry:raise ValueError(plan.get('reason') or 'Native completed structure is unavailable.')
                target=entry+2*(entry-stop) if direction=='BULLISH' else entry-2*(stop-entry)
                result.append(dict(symbol=ticker,decision='PASS',reason=plan.get('thesis'),alignment=alignment,direction=direction,entry=entry,stop=stop,target=target,reward_to_risk=2,conviction=evidence_conviction(candidate,plan),timeframe_states=stripped))
            except Exception as error:result.append(dict(symbol=ticker,decision='REJECT',reason=str(error),alignment='UNAVAILABLE',timeframe_states={}))
        result.sort(key=lambda r:({'PASS':0,'WATCHLIST':1,'REJECT':2}[r['decision']],-(r.get('conviction') or {}).get('score',0),r['symbol']))
        return dict(status='READY',broker=BROKER,account_id=execution.account['id'],source='Motilal native captured candles only',offset=offset,limit=limit,total=len(symbols),analyzed=len(page),has_more=offset+len(page)<len(symbols),results=result)
    def screener_options(self,execution,payload):
        items=payload.get('candidates')
        if not isinstance(items,list) or not 1<=len(items)<=12:raise ValueError('Select one to twelve analyzed stocks.')
        provider=self.handoff(execution);plans=[];classifications=[];excluded=[]
        policy=validate_risk_policy(payload.get('risk_policy'))
        risk=dict(planning_capital=policy['planning_capital'],max_loss_value=policy['idea_risk_limit'],max_loss_unit='rupees',enforce_risk_controls=policy['enforce_risk_controls'],minimum_reward_to_risk=policy['minimum_reward_to_risk'])
        for item in items:
            ticker=str(item.get('symbol','')).strip().upper()
            if not re.fullmatch('[A-Z0-9&-]{1,35}',ticker):raise ValueError('Invalid native stock ticker.')
            symbol='NSE:'+ticker+'-EQ';rows=provider.adapter.option_rows(symbol);available=bool(rows)
            classification=dict(symbol=ticker,classification='Stock Options' if available else 'Equity',options_available=available,routes={});classifications.append(classification)
            for route in ('LONG_OPTION','OPTION_SPREAD'):
                try:
                    if route=='OPTION_SPREAD':raise ValueError('Motilal spreads are excluded; use bought ATM Call/Put only.')
                    if not available:raise ValueError('No current native listed option contracts.')
                    if item.get('direction') not in {'BULLISH','BEARISH'} or not item.get('stop'):raise ValueError('Analyze a direction and structural invalidation first.')
                    chain,expiry,masters=provider.chain(symbol,item['direction'])
                    from .handoff import build_long_option_proposals,build_defined_risk_spreads
                    options=build_long_option_proposals(chain,expiry,masters,item['direction'],dict(risk,invalidation=item['stop']),require_greeks=False)
                    ready=[p for p in options.get('proposals',[]) if p.get('sizing',{}).get('lots') and (route!='OPTION_SPREAD' or p['structure']=='DEBIT')]
                    if not ready:raise ValueError(options.get('reason') or 'Native liquidity/risk evidence does not meet the bought ATM option gates.')
                    proposal=ready[0];grade=evidence_conviction(dict(direction=item['direction'],data_quality='READY',timeframe_states=item.get('timeframe_states',{})),item,proposal)
                    if grade['rating']!='High':raise ValueError('High conviction gate not passed.')
                    plans.append(dict(symbol=ticker,underlying=symbol,route=route,direction=item['direction'],classification='Stock Options',proposal=dict(proposal,kind=route,broker=BROKER,account_id=execution.account['id']),conviction=grade,decision_support_only=True))
                    classification['routes'][route]=dict(eligible=True)
                except Exception as error:
                    reason=str(error);classification['routes'][route]=dict(eligible=False,reason=reason);excluded.append(dict(symbol=ticker,route=route,reason=reason))
        plans.sort(key=lambda r:(-r['conviction']['score'],r['symbol'],r['route']))
        return dict(status='READY',broker=BROKER,plans=plans,classifications=classifications,excluded=excluded,message='Motilal native eligibility and evidence only; unavailable option fields never inherit FYERS values.')
