"""Causal rolling research and guarded candidate selection; no trading mutations."""
from bisect import bisect_left,insort
from collections import deque
from copy import deepcopy
from pathlib import Path
import hashlib,json,math,statistics,threading,time,uuid
from .delta_backtest import DeltaBacktest,INTERVALS,MODEL,plan,number,bollinger_features,simulate,BacktestCancelled
from .delta_signals import delta_rsi_series
from . import delta_adx
from .delta_research_ai import ResearchAI


RESEARCH_MODEL=dict(MODEL,split='Chronological rolling training and non-overlapping validation folds. Decisions use only evidence ending before the decision; rank by net-return/drawdown/fee score. The permanently sealed final holdout is excluded.',capital='Historical validation folds start flat with fixed contracts and reset capital; aggregate P&L sums independent folds. Prospective paper windows freeze settings before their future start.',validation='Research only / unvalidated. Similar-regime stability and minimum trades, positive prospective evidence, and one-shot final holdout are required before futures review-ready status. No automatic execution or ATM-options validation.')

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()[:20]


def regimes(rows):
    """Trend/range via past ADX/EMA; ATR-percent percentile versus earlier bars only."""
    adx=delta_adx.series(rows);out=[];fast=slow=None;atr=None;trs=[];history=deque();ordered=[]
    for i,row in enumerate(rows):
        close=row['close'];fast=close if fast is None else fast+2/21*(close-fast);slow=close if slow is None else slow+2/51*(close-slow)
        if i:
            prior=rows[i-1];tr=max(row['high']-row['low'],abs(row['high']-prior['close']),abs(row['low']-prior['close']));trs.append(tr)
            if len(trs)==14:atr=sum(trs)/14
            elif len(trs)>14:atr=(atr*13+tr)/14
        vol=100*atr/close if atr is not None else None
        tier='NORMAL'
        if vol is not None and len(ordered)>=100:
            lower=ordered[int(.25*(len(ordered)-1))];upper=ordered[int(.75*(len(ordered)-1))]
            tier='HIGH' if vol>upper else 'LOW' if vol<lower else 'NORMAL'
        strength=adx.get(row['timestamp']);trend='RANGE' if strength is None or strength<20 else 'TREND_UP' if fast>slow else 'TREND_DOWN'
        out.append(dict(key=trend+' / '+tier,trend=trend,volatility=tier,atr_percent=vol,adx=strength,time=row['timestamp']+row.get('interval',0),ready=len(ordered)>=100))
        if vol is not None:
            history.append(vol);insort(ordered,vol)
            if len(history)>200:ordered.pop(bisect_left(ordered,history.popleft()))
    return out


def score(metrics):
    # Net already deducts fills, fees and funding; added turnover penalty discourages churn.
    capital=metrics['ending_equity']-metrics['net_pnl']
    return metrics['return_percent']-.5*metrics['max_drawdown_percent']-.25*100*metrics['fees']/capital


def evidence(records,at,regime,min_trades):
    usable=[r for r in records if r['end']<=at and r['regime']==regime]
    trades=sum(r['metrics']['trades'] for r in usable);positive=sum(r['metrics']['net_pnl']>0 for r in usable)
    stable=positive/len(usable) if usable else 0
    return dict(windows=len(usable),trades=trades,positive_fraction=stable,mean_score=statistics.mean(r['score'] for r in usable) if usable else None,eligible=trades>=min_trades and len(usable)>=3 and stable>=.6)


def select_candidate(ranking,incumbent,state,at,regime,library,cfg):
    """Only prior validation evidence can authorize a switch; never the upcoming fold."""
    eligible=[]
    for item in ranking:
        ev=evidence(library.get(item['id'],[]),at,regime,cfg['min_validation_trades'])
        if item['metrics']['trades']>=cfg['min_train_trades'] and ev['eligible']:eligible.append((item,ev))
    current=next(r for r in ranking if r['id']==incumbent);challenger=eligible[0] if eligible else None
    result=dict(selected=incumbent,reason='Baseline/incumbent retained: insufficient similar-regime out-of-sample evidence.',evidence=None)
    if not challenger:state['pending']=None;state['streak']=0;return result
    item,ev=challenger;result['evidence']=ev
    if item['id']==incumbent:state['pending']=None;state['streak']=0;result['reason']='Incumbent remains the eligible risk-adjusted leader.';return result
    if item['score']-current['score']<cfg['improvement_margin']:state['pending']=None;state['streak']=0;result['reason']='Improvement below required risk-adjusted percentage-point margin.';return result
    state['streak']=state.get('streak',0)+1 if state.get('pending')==item['id'] else 1;state['pending']=item['id']
    if state['streak']<cfg['persistence']:result['reason']='Challenger waiting for persistent evidence across decisions.';return result
    if at-state.get('last_switch',-1e30)<cfg['cooldown_bars']*INTERVALS[cfg['resolution']]:result['reason']='Research selection cooldown active.';return result
    state.update(last_switch=at,pending=None,streak=0);return dict(selected=item['id'],reason='Research candidate switched after stable similar-regime evidence, improvement and persistence gates.',evidence=ev)


def walk_forward(raw,combinations,settings,units,tick,config,prior_library=None,cancel=None,progress=None):
    interval=INTERVALS[config['resolution']];states=regimes(raw);bytime={r['timestamp']:states[i] for i,r in enumerate(raw)}
    warmup=config['warmup'];train=config['train_bars'];step=config['validation_bars'];first=int(raw[warmup]['timestamp']);end=int(raw[-1]['timestamp'])+interval
    first_boundary=math.ceil((first+train*interval)/(step*interval))*step*interval
    boundaries=list(range(first_boundary,end-step*interval+1,step*interval))[-12:]
    if len(boundaries)<3:raise ValueError('At least three full chronological validation windows are required; increase history bars.')
    series={};features={};adx=delta_adx.series(raw)
    for c in combinations:
        ident=digest(c);series[ident]=delta_rsi_series(raw,c['rsi_length'],c['ma_length'],c['ma_type']);features[ident]=bollinger_features(raw,c)
    base=next(c for c in combinations if c['filter']=='BASELINE' and c['rsi_length']==14 and c['ma_length']==14 and c['ma_type']=='EMA')
    baseline=digest(base);incumbent=baseline;guard={'pending':None,'streak':0};library=deepcopy(prior_library or {});folds=[];adaptive=[];fixed=[]
    for n,start in enumerate(boundaries):
        if cancel and cancel.is_set():raise BacktestCancelled()
        stop=start+step*interval;regime=bytime[start-interval]['key'];ranking=[]
        for c in combinations:
            ident=digest(c);training=simulate(series[ident],features[ident],adx,c,settings,units,tick,start-train*interval,start)
            ranking.append(dict(id=ident,config=c,metrics=training['metrics'],score=score(training['metrics'])))
        ranking.sort(key=lambda r:(-r['score'],r['id']))
        decision=select_candidate(ranking,incumbent,guard,start,regime,library,config);incumbent=decision['selected']
        outcomes={}
        # Selection above cannot see any metric below; fold scores become evidence for later folds only.
        for c in combinations:
            ident=digest(c);validation=simulate(series[ident],features[ident],adx,c,settings,units,tick,start,stop);outcomes[ident]=validation
            record=dict(start=start,end=stop,regime=regime,metrics=validation['metrics'],score=score(validation['metrics']))
            existing=library.setdefault(ident,[]);existing[:]=[r for r in existing if (r['start'],r['end'])!=(start,stop)];existing.append(record);existing[:]=sorted(existing,key=lambda r:r['end'])[-120:]
        adaptive.append(outcomes[incumbent]);fixed.append(outcomes[baseline]);folds.append(dict(start=start,end=stop,regime=regime,selection=decision,config=next(c for c in combinations if digest(c)==incumbent),adaptive=outcomes[incumbent]['metrics'],baseline=outcomes[baseline]['metrics'],training_leader=ranking[0]['config'],decision_basis='Only training and validation windows ending before this decision.'))
        if progress:progress(n+1,len(boundaries))
    # Next decision uses only now-completed training and already-completed validation windows.
    asof=end;regime=states[-1]['key'];ranking=[]
    for c in combinations:
        ident=digest(c);training=simulate(series[ident],features[ident],adx,c,settings,units,tick,end-train*interval,end);ranking.append(dict(id=ident,config=c,metrics=training['metrics'],score=score(training['metrics'])))
    ranking.sort(key=lambda r:(-r['score'],r['id']));latest=select_candidate(ranking,incumbent,guard,asof,regime,library,config)
    def combine(items):
        cash=settings['capital'];peak=cash;dd=0;trades=[];curve=[]
        for segment in items:
            for p in segment['equity']:
                value=cash+p['equity']-settings['capital'];peak=max(peak,value);dd=max(dd,peak-value);curve.append(dict(time=p['time'],equity=value,drawdown=peak-value))
            cash+=segment['metrics']['net_pnl'];trades.extend(segment['trades'])
        return dict(net_pnl=cash-settings['capital'],return_percent=100*(cash/settings['capital']-1),trades=len(trades),max_drawdown=dd,equity=curve[::max(1,math.ceil(len(curve)/1200))],trade_history=trades)
    adaptive_result=combine(adaptive);fixed_result=combine(fixed)
    return dict(folds=folds,library=library,selection=latest,selected_config=next(c for c in combinations if digest(c)==latest['selected']),baseline_config=base,regime=dict(states[-1],time=asof),adaptive=adaptive_result,baseline=fixed_result,asof=asof,guard=guard,leader=ranking[0],ranking=ranking,warmup=warmup)


DEFAULTS=dict(symbol='BTCUSD',resolution='5m',rsi_lengths=[10,14,21],ma_lengths=[14],ma_types=['EMA'],filters=['BASELINE','EXPANDING','SQUEEZE_RELEASE'],history_bars=3600,train_bars=600,validation_bars=200,holdout_bars=300,min_train_trades=15,min_validation_trades=20,improvement_margin=.05,persistence=2,cooldown_bars=400,cadence_minutes=60,capital=10000,contracts=10,fee_bps=6,slippage_bps=2,half_spread_bps=1,funding_bps_day=0,adx_enabled=True,adx_thresholds=[25],momentum_enabled=True,bb_lengths=[20],bb_deviation=2,squeeze_lookback=100,squeeze_percentile=20,release_bars=3,entry_rule='CURRENT',direction='BOTH',ai_enabled=False,ai_calls_per_day=2,ai_tokens_per_day=12000,ai_max_output_tokens=400,ai_model='gpt-4.1-mini')


class AdaptiveResearch:
    def __init__(self,root,read,metadata,workspace,clock=time.time,ai=None,can_run=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.read=read;self.metadata=metadata;self.clock=clock;self.lock=threading.RLock();self.cancel_event=threading.Event();self.shutdown=threading.Event()
        self.can_run=can_run or (lambda:True)
        self.path=self.root/'agent-state.json';self.state=dict(schema=1,config=deepcopy(DEFAULTS),loop_running=False,job={'state':'IDLE','message':'Research loop stopped. Run a cycle explicitly.'},cycles=[],library={},holdout=None,extras=[],prospective=[],pending_forward=None,next_due=None)
        if self.path.exists():self.state=json.loads(self.path.read_text())
        if self.state['job']['state'] in ('FETCHING','RUNNING','REVIEWING'):self.state['job'].update(state='INTERRUPTED',message='Research worker restarted during a cycle; no trading runner changed.')
        self.ai=ai or ResearchAI(self.root/'ai-usage.json',workspace,clock)
        threading.Thread(target=self._schedule,daemon=True,name='delta-adaptive-scheduler').start()
    def save(self):
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.state,allow_nan=False));temp.chmod(0o600);temp.replace(self.path)
    def limits(self):
        c=self.state['config'];return dict(enabled=c['ai_enabled'],model=c['ai_model'],calls_per_day=c['ai_calls_per_day'],tokens_per_day=c['ai_tokens_per_day'],max_output_tokens=c['ai_max_output_tokens'])
    def status(self):
        with self.lock:
            data=deepcopy(self.state);data['ai']=self.ai.status(self.limits());data['library']=[dict(id=key,**{k:v for k,v in entry.items() if k!='records'}) for key,entry in data['library'].items()];return data
    def configure(self,payload):
        with self.lock:
            if self.state['job']['state'] in ('FETCHING','RUNNING','REVIEWING'):raise ValueError('Wait for or cancel the research cycle before changing settings.')
            c=dict(self.state['config'],**{k:v for k,v in payload.items() if k in DEFAULTS})
            if c['resolution'] not in INTERVALS:raise ValueError('Unsupported adaptive research timeframe.')
            for k,lo,hi in [('history_bars',1500,16000),('train_bars',200,4000),('validation_bars',100,1000),('holdout_bars',100,2000),('min_train_trades',5,200),('min_validation_trades',10,500),('persistence',1,5),('cooldown_bars',100,4000),('cadence_minutes',15,1440),('ai_calls_per_day',0,10),('ai_tokens_per_day',0,100000),('ai_max_output_tokens',100,800)]:c[k]=number(c[k],k,lo,hi,True)
            c['improvement_margin']=number(c['improvement_margin'],'Improvement margin',.01,5)
            if not isinstance(c['ai_enabled'],bool):raise ValueError('AI enabled must be true or false.')
            if c['ai_model'] not in ('gpt-4.1-mini','gpt-4.1-nano'):raise ValueError('Choose a supported bounded review model.')
            if self.state['holdout'] and any(c[k]!=self.state['config'][k] for k in ('symbol','resolution','holdout_bars')):raise ValueError('The sealed holdout fixes the underlying, timeframe and holdout size for this campaign.')
            validated=self._plan(c)
            if len(validated['combinations'])+len(self.state['extras'])>24:raise ValueError('Adaptive grid is capped at 24 combinations, including proposed experiments.')
            if c['history_bars']<validated['warmup']+c['train_bars']+3*c['validation_bars']+c['holdout_bars']:raise ValueError('History must cover warmup, training, at least 3 validation windows and reserved holdout.')
            self.state['config']=c;self.save();return self.status()
    def _plan(self,c):
        # Use the standard strict grid/cost validation; adaptive data ends at latest completed candle instead of yesterday.
        p=dict(c,resolutions=[c['resolution']],start_date='2026-08-01',end_date='2026-08-02',holdout_percent=30)
        if c['resolution'] in ('1h','6h','1d'):p['start_date']='2026-04-01'
        if c['resolution']=='1d':p['end_date']='2026-06-01'
        result=plan(p,self.clock())
        baseline=dict(result['combinations'][0],rsi_length=14,ma_length=14,ma_type='EMA',filter='BASELINE')
        if baseline not in result['combinations']:result['combinations'].append(baseline)
        return result
    def run(self,_=None):
        with self.lock:
            if not self.can_run():raise ValueError('Wait for the current grid backtest.')
            if self.state['job']['state'] in ('FETCHING','RUNNING','REVIEWING'):raise ValueError('An adaptive research cycle is already running.')
            self.cancel_event=threading.Event();self.state['job']=dict(id=uuid.uuid4().hex,state='FETCHING',progress=0,message='Updating and auditing completed public candles.',started_at=self.clock());self.save()
            threading.Thread(target=self._cycle,args=(deepcopy(self.state['config']),self.cancel_event),daemon=True,name='delta-adaptive-research').start();return self.status()
    def start_loop(self,_=None):
        with self.lock:self.state.update(loop_running=True,next_due=self.clock());self.save()
        return self.status()
    def stop_loop(self,_=None):
        with self.lock:self.state.update(loop_running=False,next_due=None);self.cancel_event.set();self.save()
        return self.status()
    def cancel(self,_=None):self.cancel_event.set();return self.status()
    def _schedule(self):
        while not self.shutdown.wait(5):
            with self.lock:
                due=self.can_run() and self.state['loop_running'] and self.clock()>=(self.state.get('next_due') or 0) and self.state['job']['state'] not in ('FETCHING','RUNNING','REVIEWING')
                if due:
                    self.state['next_due']=self.clock()+self.state['config']['cadence_minutes']*60;self.save();self.run()
    def update(self,**values):
        with self.lock:
            self.state['job'].update(values)
            if values.get('state') in ('ERROR','CANCELLED') and self.state['job'].get('id'):
                self.state['cycles'].append(deepcopy(self.state['job']));self.state['cycles']=self.state['cycles'][-50:]
            self.save()
    def _data(self,c,cancel):
        p=self._plan(c);interval=INTERVALS[c['resolution']];end=int(self.clock()//interval)*interval;start=end-c['history_bars']*interval;warm=p['warmup'];fetch_start=((start-warm*interval)//(1500*interval))*(1500*interval)
        bounds=dict(start=start,end=end,fetch_start=fetch_start,expected=c['history_bars'],interval=interval)
        cache=DeltaBacktest(self.root/'candles',self.read,self.metadata,self.clock);cache.job=dict(plan={'estimated_requests':math.ceil((end-fetch_start)/(1500*interval))},coverage={},downloaded_windows=0,cached_windows=0)
        rows=cache._fetch(c['symbol'],c['resolution'],bounds,cancel)
        return rows,p,cache.job,bounds
    def _cycle(self,c,cancel):
        try:
            rows,p,fetch,bounds=self._data(c,cancel);interval=INTERVALS[c['resolution']];product=self.metadata(c['symbol'])
            if product.get('contract_type')!='perpetual_futures' or product.get('notional_type')!='vanilla' or product.get('is_quanto') is not False or product.get('quoting_currency')!='USD' or product.get('settlement_currency')!='USD' or product.get('contract_unit_currency')!=product.get('underlying'):raise ValueError('Verified vanilla futures contract identity unavailable.')
            units=number(float(product['contract_value']),'Contract units',1e-8,10000);tick=number(float(product['tick_size']),'Tick',1e-8,10000)
            with self.lock:
                if not self.state['holdout']:
                    self.state['holdout']=dict(start=bounds['end']-c['holdout_bars']*interval,end=bounds['end'],status='SEALED_UNTOUCHED',result=None);self.save()
                sealed=deepcopy(self.state['holdout'])
            # Sealed final holdout is permanently excluded from all optimization and regime features.
            before=[r for r in rows if r['timestamp']<sealed['start']];after=[r for r in rows if r['timestamp']>=sealed['end']]
            required=p['warmup']+c['train_bars']+3*c['validation_bars']
            usable=after if len(after)>=required else before
            if len(usable)<required:raise ValueError('Insufficient unsealed contiguous history. Reserved holdout is never reused for optimization.')
            self.update(state='RUNNING',progress=30,message='Causal regime matching and rolling train/validation comparisons.',coverage=fetch['coverage'],data_end=bounds['end'],sealed_holdout=sealed)
            combinations=p['combinations']+[dict(p['combinations'][0],**{k:e[k] for k in ('rsi_length','ma_length','ma_type','filter')}) for e in self.state['extras']]
            combinations=list({digest(x):x for x in combinations}.values())
            context=digest({'costs':p['settings'],'train':c['train_bars'],'validation':c['validation_bars'],'product':product})
            prior={key:value['records'] for key,value in self.state['library'].items() if value['context']==context}
            cfg=dict(c,warmup=p['warmup'])
            result=walk_forward(usable,combinations,p['settings'],units,tick,cfg,prior,cancel,lambda n,total:self.update(progress=30+55*n/total,message=f'Validated chronological fold {n}/{total}; selection cannot see its future outcome.'))
            # Persist the real-time selection guard separately from historical replay.
            with self.lock:
                live=self.state.setdefault('selection_guard',{})
                base_id=digest(result['baseline_config']);ids={r['id'] for r in result['ranking']}
                incumbent=live.get('incumbent',base_id)
                if live.get('context')!=context or incumbent not in ids:live.clear();live.update(context=context,incumbent=base_id);incumbent=base_id
                if result['asof']>live.get('asof',0):
                    decision=select_candidate(result['ranking'],incumbent,live,result['asof'],result['regime']['key'],result['library'],cfg)
                    live.update(incumbent=decision['selected'],asof=result['asof'],decision=decision)
                result['selection']=deepcopy(live['decision']);result['selected_config']=next(r['config'] for r in result['ranking'] if r['id']==live['incumbent'])
                self.save()
            library=[]
            for candidate in combinations:
                ident=digest(candidate);records=result['library'].get(ident,[]);ev=evidence(records,result['asof'],result['regime']['key'],c['min_validation_trades']);entry=dict(config=candidate,settings=p['settings'],product=product,context=context,records=records,evidence=ev,last_seen=result['asof'],status='RESEARCH_ELIGIBLE' if ev['eligible'] else 'INSUFFICIENT_SIMILAR_REGIME_EVIDENCE')
                with self.lock:self.state['library'][ident]=entry
                library.append(dict(id=ident,config=candidate,evidence=ev,status=entry['status']))
            self._forward(rows,product,c,p['settings'],sealed,result,units,tick)
            summary=dict(id=self.state['job']['id'],at=self.clock(),asof=result['asof'],data_end=bounds['end'],regime=result['regime'],selected_config=result['selected_config'],selection=result['selection'],adaptive=result['adaptive'],baseline=result['baseline'],folds=result['folds'],coverage=fetch['coverage'],model=RESEARCH_MODEL,product=product,context=context,library=library,unvalidated=True,optimization='Deterministic parameter search and causal similar-regime evidence; no ML model is fitted.')
            summary['adaptive'].pop('trade_history');summary['baseline'].pop('trade_history')
            compact=dict(regime=result['regime']['key'],asof=result['asof'],selected=result['selected_config'],reason=result['selection']['reason'],adaptive_net=round(result['adaptive']['net_pnl'],4),baseline_net=round(result['baseline']['net_pnl'],4),validation=[{'filter':x['config']['filter'],'rsi':x['config']['rsi_length'],'ma':x['config']['ma_length'],'status':x['status'],'evidence':x['evidence']} for x in library[:4]],prospective_windows=len(self.state['prospective']),holdout='SEALED_UNTOUCHED',live_promotion=False)
            meaningful=digest({'regime':compact['regime'],'selected':compact['selected'],'reason':compact['reason'],'validation':compact['validation']})
            with self.lock:unchanged=meaningful==self.state.get('last_ai_signature')
            self.update(state='REVIEWING',progress=90,message='One bounded AI evidence review; no per-candle or per-combination calls.')
            ai_result=dict(state='UNCHANGED',review='No meaningful evidence change; no AI call.',experiments=[]) if unchanged else self.ai.review(compact,self.limits())
            summary['ai_review']=ai_result
            if cancel.is_set():raise BacktestCancelled()
            with self.lock:
                if ai_result['state'] in ('COMPLETE','CACHED'):self.state['last_ai_signature']=meaningful
                self.state['latest']=summary;self.state['cycles'].append({k:v for k,v in summary.items() if k not in ('adaptive','baseline','folds','library','model')});self.state['cycles']=self.state['cycles'][-50:]
                self.state['job'].update(state='COMPLETE',progress=100,message='Adaptive research cycle complete; no trading settings changed.',finished_at=self.clock());self.save()
        except BacktestCancelled:self.update(state='CANCELLED',message='Research cancelled; trading runner untouched.',finished_at=self.clock())
        except Exception as error:self.update(state='ERROR',message=str(error),error=str(error),finished_at=self.clock())
    def _forward(self,rows,product,c,settings,sealed,result,units,tick):
        interval=INTERVALS[c['resolution']];step=c['validation_bars']*interval;after=[r for r in rows if r['timestamp']>=sealed['end']];pending=self.state.get('pending_forward')
        if pending and after and after[-1]['timestamp']+interval>=pending['end']:
            # Real-time decision was durably captured before this future window, not reconstructed later.
            if pending['created_at']>pending['start'] or len([r for r in after if r['timestamp']<pending['start']])<pending['warmup']:self.state['pending_forward']=None
            else:
                outcomes={}
                for label,cfg in [('adaptive',pending['config']),('baseline',pending['baseline'])]:
                    series=delta_rsi_series(after,cfg['rsi_length'],cfg['ma_length'],cfg['ma_type']);outcomes[label]=simulate(series,bollinger_features(after,cfg),delta_adx.series(after),cfg,pending['settings'],pending['units'],pending['tick'],pending['start'],pending['end'])['metrics']
                self.state['prospective'].append(dict(start=pending['start'],end=pending['end'],decision_at=pending['created_at'],context=pending['context'],config=pending['config'],**outcomes));self.state['prospective']=self.state['prospective'][-100:];self.state['pending_forward']=None
        if not self.state.get('pending_forward'):
            warmup=result['warmup'];start=math.ceil(max(self.clock(),sealed['end']+warmup*interval)/step)*step
            self.state['pending_forward']=dict(created_at=self.clock(),start=start,end=start+step,config=result['selected_config'],baseline=result['baseline_config'],settings=settings,warmup=warmup,units=units,tick=tick,context=digest({'costs':settings,'train':c['train_bars'],'validation':c['validation_bars'],'product':product}))
    def proposal(self,ident):
        with self.lock:
            entry=self.state['library'].get(ident)
            if not entry:raise ValueError('Choose a saved research candidate.')
            forward=[r for r in self.state['prospective'] if digest(r['config'])==ident and r.get('context')==entry['context']];count=sum(r['adaptive']['trades'] for r in forward);net=sum(r['adaptive']['net_pnl'] for r in forward)
            sealed=self.state['holdout'];final=(sealed or {}).get('result');ready=entry['evidence']['eligible'] and count>=20 and net>0 and final and final['candidate_id']==ident and final.get('context')==entry['context'] and final['metrics']['trades']>=10 and final['metrics']['net_pnl']>0
            return dict(candidate_id=ident,settings=entry['config'],simulation_settings={k:v for k,v in entry['settings'].items() if k not in ('start_date','end_date','holdout_percent')},validation_records=entry.get('records',[]),product=entry['product'],context=entry['context'],evidence=entry['evidence'],prospective_windows=len(forward),prospective_trades=count,prospective_net_pnl=net,holdout=sealed,status='FUTURES_REVIEW_READY' if ready else 'INSUFFICIENT_EVIDENCE',automatic_promotion=False,execution_compatibility='Underlying futures only. ATM option chain/premium/spread evidence is missing; cannot promote to the current ATM-options runner.',model=RESEARCH_MODEL)
    def add_proposals(self,_=None):
        with self.lock:
            if self.state['job']['state'] in ('FETCHING','RUNNING','REVIEWING'):raise ValueError('Wait for the current cycle.')
            proposals=(self.state.get('latest',{}).get('ai_review') or {}).get('experiments',[])
            for p in proposals:
                if p not in self.state['extras'] and len(self._plan(self.state['config'])['combinations'])+len(self.state['extras'])<24:self.state['extras'].append(p)
            self.save();return self.status()

    def holdout_once(self,payload):
        ident=payload.get('candidate_id')
        with self.lock:
            if self.state['job']['state'] in ('FETCHING','RUNNING','REVIEWING'):raise ValueError('Wait for or cancel the research cycle.')
            sealed=self.state['holdout'];entry=self.state['library'].get(ident)
            if not sealed or not entry:raise ValueError('Choose a saved candidate after the first cycle seals a holdout.')
            if sealed.get('result'):raise ValueError('Final holdout already scored once; it cannot be reranked or reused.')
            if sealed.get('candidate_id') and sealed['candidate_id']!=ident:raise ValueError('Holdout candidate was already frozen; only that candidate can complete its evaluation.')
            if not sealed.get('frozen_entry'):sealed['frozen_entry']=deepcopy({k:v for k,v in entry.items() if k!='records'})
            entry=sealed['frozen_entry'];self.cancel_event=threading.Event()
            sealed.update(status='SCORING_ONCE',candidate_id=ident);self.state['job']=dict(state='FETCHING',progress=0,message='One-shot final holdout: candidate frozen before evaluation.');self.save()
            threading.Thread(target=self._score_holdout,args=(deepcopy(sealed),ident,deepcopy(entry)),daemon=True,name='delta-final-holdout').start()
            return self.status()
    def _score_holdout(self,sealed,ident,entry):
        try:
            cfg=entry['config'];interval=INTERVALS[cfg['resolution']];warm=max(600,cfg['bb_length']+cfg['squeeze_lookback']+cfg['release_bars']+2)
            bounds=dict(start=sealed['start'],end=sealed['end'],fetch_start=sealed['start']-warm*interval,interval=interval,expected=(sealed['end']-sealed['start'])//interval)
            cache=DeltaBacktest(self.root/'candles',self.read,self.metadata,self.clock);cache.job=dict(plan={'estimated_requests':math.ceil((bounds['end']-bounds['fetch_start'])/(1500*interval))},coverage={},downloaded_windows=0,cached_windows=0)
            rows=cache._fetch(cfg['symbol'],cfg['resolution'],bounds,self.cancel_event);product=self.metadata(cfg['symbol'])
            if any(product.get(k)!=entry['product'].get(k) for k in ('id','contract_value','tick_size','notional_type','is_quanto')):raise ValueError('Contract specifications changed; final holdout evaluation blocked.')
            series=delta_rsi_series(rows,cfg['rsi_length'],cfg['ma_length'],cfg['ma_type']);out=simulate(series,bollinger_features(rows,cfg),delta_adx.series(rows),cfg,entry['settings'],float(product['contract_value']),float(product['tick_size']),sealed['start'],sealed['end'])
            with self.lock:self.state['holdout'].update(status='SCORED_ONCE',result=dict(candidate_id=ident,context=entry['context'],settings=cfg,simulation_settings=entry['settings'],metrics=out['metrics'],at=self.clock()));self.save()
            self.update(state='COMPLETE',progress=100,message='Final holdout scored once. Research-only; no trading promotion performed.')
        except Exception as error:
            with self.lock:self.state['holdout']['status']='SCORE_ERROR';self.save()
            self.update(state='ERROR',message=str(error))
