"""Explicit UI-to-standalone bridge. No process is launched by import or preview."""
from pathlib import Path
import hashlib,json,os,secrets,subprocess,threading,time
BASE=Path('/home/trading/sector-heatmap/strategies/nifty_ai_options')
DATA=Path('/home/trading/sector-heatmap/.private/nifty-ai-options')
MODE='AI_RENKO_OPTIONS'
def owner_broker(owner):
    import sqlite3
    if not isinstance(owner,str) or len(owner)!=32 or any(c not in '0123456789abcdef' for c in owner):raise ValueError('Exact registered account id required')
    with sqlite3.connect('file:/home/trading/sector-heatmap/.private/dashboard-login/registry.sqlite3?mode=ro',uri=True) as db:
        row=db.execute('select broker from accounts where id=?',(owner,)).fetchone()
    if not row:raise ValueError('Account registration unavailable')
    return row[0]

def live_capability(owner):
    broker=owner_broker(owner)
    if broker=='FYERS':return bool(os.getenv('AI_RENKO_LIVE_ORDERS',os.getenv('NIFTY_AI_LIVE_ORDERS'))=='I_ACCEPT_REAL_ORDERS' or os.getenv('SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS')=='1')
    if broker=='DELTA_INDIA':
        try:credentials=json.loads((Path('/home/trading/sector-heatmap/.private/dashboard-login/accounts')/owner/'credentials.json').read_text())
        except (OSError,ValueError):return False
        return str(os.getenv('DELTA_INDIA_ENABLE_LIVE_ORDERS',credentials.get('DELTA_INDIA_ENABLE_LIVE_ORDERS','1'))).lower() in ('1','true','yes')
    return False

def configuration(payload,owner):
    if not owner or payload.get('account_id')!=owner or payload.get('broker') not in ('FYERS','DELTA_INDIA'):
        raise ValueError('AI Renko Supertrend requires the exact private broker account')
    if owner_broker(owner)!=payload.get('broker'):raise ValueError('Selected broker differs from the registered owner')
    frames={'1 minute':1,'5 minutes':5,'30 minutes':30}
    if payload.get('timeframe') not in frames:raise ValueError('Choose 1, 5 or 30 minute source')
    if not payload.get('underlying'):raise ValueError('Select an underlying instrument')
    config=dict(account=owner,broker=payload.get('broker'),execution_mode=payload.get('mode','PAPER'),underlying=payload['underlying'],market=payload.get('ai_market') or payload['underlying'].split(':')[0],asset=payload.get('ai_asset'),execution_route=payload.get('ai_execution_route','OPTIONS'),baseline_minutes=30,lots=payload.get('lots'),product=payload.get('ai_product'),expiry_policy='nearest_tradable',
        timeframe=frames[payload['timeframe']],target_premium=payload.get('target_premium',40),
        reference_source='external_native_parent_atr5',reference_session=payload.get('ai_reference_session'),
        reference_value=payload.get('ai_reference_value'),reference_symbol=payload.get('ai_reference_symbol'),reference_evidence=payload.get('ai_reference_evidence'),
        entry_gate='underlying_flip' if payload.get('ai_execution_route')=='DIRECT' else 'underlying_flip_premium_bullish',exit_supertrend='underlying' if payload.get('ai_execution_route')=='DIRECT' else 'premium',indicator_brick_mode='Manual',
        sma_exit_enabled=payload.get('ai_sma_exit_enabled',False),sma_price_basis='underlying',
        accept_close_source_renko_approximation=payload.get('ai_accept_chart_basis',False))
    try:from .native_reference import resolve_reference
    except ImportError:from native_reference import resolve_reference
    reference=resolve_reference(owner,config['underlying'],config['market'],config.get('asset'))
    config.update(reference_source='verified_native_cache',reference_value=reference['native_box'] if reference else None,reference_symbol=config['underlying'],reference_session=reference.get('reference_session') if reference else None,reference_evidence=(reference.get('source','')+' · '+reference.get('url','')) if reference else None,reference_state='VERIFIED' if reference else 'UNAVAILABLE')
    return config

def option_preview(owner,reference):
    """Bounded broker GETs only; no quantity, product, stream or order required."""
    try:from .live import Reads,Master,choose,sizes,client,IST
    except ImportError:from live import Reads,Master,choose,sizes,client,IST
    from datetime import datetime
    if reference.get('broker')=='DELTA_INDIA':
        try:from .delta_adapter import bound_delta,select_option
        except ImportError:from delta_adapter import bound_delta,select_option
        try:from .sizing_policy import scale_reference
        except ImportError:from sizing_policy import scale_reference
        from strategies.renko_supertrend.delta_contracts import perpetual_contract
        delta=bound_delta(owner,DATA/'preview-delta'/owner)
        try:
            base=scale_reference(reference['reference_value'],'CRYPTO',reference.get('asset'))['base_brick'] if reference.get('reference_value') else None
            if reference.get('execution_route')=='DIRECT':return dict(direct=perpetual_contract(delta.product(reference['underlying'])),contracts={},underlying=reference['underlying'],spot_brick=base,read_only=True,orders_submitted=0)
            contracts={}
            for side in ('CE','PE'):
                contract,d=select_option(delta,reference['underlying'],side,reference.get('target_premium',40))
                contracts[side]=dict(contract,delta=d,spot_brick=base,option_brick=base*abs(d) if base is not None else None,expiry_date=datetime.fromtimestamp(float(contract['expiry']),IST).date().isoformat())
            if contracts['CE']['expiry']!=contracts['PE']['expiry']:raise ValueError('Expiry changed during preview; repeat read-only preview')
            return dict(contracts=contracts,underlying=reference['underlying'],resolved_expiry=contracts['CE']['expiry'],checked_at=datetime.now(IST).isoformat(),read_only=True,orders_submitted=0,reference_value=reference['reference_value'],reference_session=reference['reference_session'],quote_note='Delta chain snapshot in native quote currency; executable quotes are checked at actual entry.')
        finally:delta.requester.close()
    if reference.get('broker')!='FYERS':raise ValueError('No selected broker preview adapter')
    if reference.get('execution_route')=='DIRECT':
        try:from .markets import FyersInstrumentMaster
        except ImportError:from markets import FyersInstrumentMaster
        try:from .direct import DirectStrategy
        except ImportError:from direct import DirectStrategy
        meta=FyersInstrumentMaster(DATA/'preview-master'/owner)(reference['underlying'])
        return dict(direct=meta,underlying=reference['underlying'],contracts={},spot_brick=DirectStrategy(reference).spot_size if reference.get('reference_value') else None,read_only=True,orders_submitted=0)
    raw=client(owner)
    try:
        api=Reads(raw);master=Master(DATA/'preview-master'/owner)
        contracts={}
        for side in ('CE','PE'):
            contract,delta=choose(api,master,reference,side,require_reference=False)
            spot,brick=sizes(reference['reference_value'],delta,reference.get('market','NSE'),reference.get('asset')) if reference.get('reference_value') else (None,None)
            contracts[side]=dict(contract,delta=delta,spot_brick=spot,option_brick=brick,
                expiry_date=datetime.fromtimestamp(float(contract['expiry']),IST).date().isoformat())
        if contracts['CE']['expiry']!=contracts['PE']['expiry']:raise ValueError('Expiry changed during preview; repeat read-only preview')
        return dict(contracts=contracts,resolved_expiry=contracts['CE']['expiry'],checked_at=datetime.now(IST).isoformat(),read_only=True,orders_submitted=0,
            reference_session=reference['reference_session'],reference_value=reference['reference_value'],reference_evidence=reference['reference_evidence'],
            underlying=reference['underlying'],quote_note='Provider chain snapshot; executable fresh quotes are rechecked only at a later explicit Start/trade')
    finally:raw._sector_pulse_ipv4_session.close()

class Service:
    def __init__(self,owner,legacy):
        self.owner,self.legacy=owner,legacy
        self.lock=threading.RLock();self.process=None;self.run=None;self.launching=False;self.error=None;self.cancelled=False
        try:
            try:from .process_state import recover
            except ImportError:from process_state import recover
            self.run,self.process=recover(self.owner,DATA)
        except (OSError,ValueError,KeyError) as error:self.error='AI job recovery requires review: '+str(error)
    def snapshot(self):
        with self.lock:
            result=dict(live_capability=live_capability(self.owner),phase='PREFLIGHT' if self.launching else 'FAILED' if self.error or (self.process and self.process.poll() not in (None,0)) else 'STREAM' if self.process and self.process.poll() is None else 'STOPPED',error=self.error,revision='ai-renko-options-v1',running=bool(self.process and self.process.poll() is None),run_id=self.run['id'] if self.run else None)
            # Public measured reference/expiry metadata; no broker call or trading setting mutation.
            try:
                references=sorted((BASE/'evidence').glob('native-reference-*.json'))
                measured=[]
                for path in references:
                    reference=json.loads(path.read_text())
                    if reference.get('status','').startswith('VERIFIED_') and reference.get('atr_length')==5 and reference.get('native_box',0)>0:measured.append(reference)
                result['native_references']=measured
                if measured:result['native_reference']=measured[-1]
                metadata=BASE/'evidence/verified-20261119/probe.json'
                result['expiry_policy']='nearest_tradable'
                from sector_heatmap.market_calendar import market_session
                result['expected_reference_session']=market_session()['last_completed_session']
            except (OSError,ValueError,KeyError):pass
            if self.run:
                result.update(directory=str(self.run['directory']),mode=self.run['mode'],exit_code=self.process.poll() if self.process else None)
                preflight=self.run['directory']/'preflight/preflight.json'
                if preflight.exists():result['resolved_expiry']=json.loads(preflight.read_text()).get('resolved_expiry')
                markers=self.run['directory']/'markers.json'
                if markers.exists():result['markers']=json.loads(markers.read_text())
                # Read the exact run's durable ledger even after SIGTERM/crash.
                # Account key comes from authenticated preflight, never a browser path.
                config=json.loads((self.run['directory']/'config.json').read_text())
                result.update(source_timeframe=config.get('timeframe'),execution_route=config.get('execution_route'),underlying=config.get('underlying'),chart_source_ready=(self.run['directory']/'chart-source').is_dir())
                result['chart_source_series']=[json.loads(path.read_text()) for path in (self.run['directory']/'chart-source').glob('*-meta.json')]

                proof=self.run['directory']/'preflight/preflight.json'
                if not proof.exists():proof=self.run['directory']/'preflight.json'
                details=json.loads(proof.read_text()) if proof.exists() else {}
                key=self.owner if config.get('broker')=='DELTA_INDIA' else details.get('account_sha256')
                suffix='live' if self.run['mode']=='LIVE' else 'paper'
                ledger_name=('delta-'+suffix if config.get('broker')=='DELTA_INDIA' else 'direct-'+suffix if config.get('execution_route')=='DIRECT' else suffix)+'.json'
                if isinstance(key,str) and len(key) in (32,64) and all(c in '0123456789abcdef' for c in key):
                    ledger=DATA/'runtime'/key/ledger_name
                    if ledger.exists():
                        owned=json.loads(ledger.read_text())
                        result['ownership']=dict(position=owned.get('position'),pending=owned.get('pending'),checked_at=time.time())
                heartbeat=self.run['directory']/'heartbeat.json'
                if heartbeat.exists():
                    result['heartbeat']=json.loads(heartbeat.read_text())
                    result['heartbeat_age']=time.time()-heartbeat.stat().st_mtime
                if result.get('ownership'):
                    result['heartbeat']=dict(result.get('heartbeat') or {},position=result['ownership']['position'],pending=result['ownership']['pending'])
                result['heartbeat']=dict(result.get('heartbeat') or {},timeframe=config.get('timeframe'))
            return result
    def chart_source(self,query):
        try:from .chart_source import read_source
        except ImportError:from chart_source import read_source
        return read_source(DATA,self.owner,query.get('run_id'),query.get('symbol'),int(query.get('frame','0')),after=query.get('after'))

    def search(self,query,market,route='OPTIONS'):
        broker=owner_broker(self.owner)
        if broker=='FYERS':
            try:from .instrument_search import search_fyers
            except ImportError:from instrument_search import search_fyers
            return search_fyers(DATA/'instrument-master'/self.owner,query,market,route)
        if broker=='DELTA_INDIA':
            try:from .delta_adapter import bound_delta
            except ImportError:from delta_adapter import bound_delta
            delta=bound_delta(self.owner,DATA/'preview-delta'/self.owner)
            try:
                matches=[dict(symbol=r['symbol'],underlying=r['underlying'],description=r.get('description',r['symbol']),market='CRYPTO',product_type='PERPETUAL') for r in delta.catalog()['instruments'] if r['contract_type']=='perpetual_futures' and str(query or '').upper() in (r['symbol']+' '+r['underlying']).upper()]
                return dict(matches=matches[:80],message='Current Delta catalog · exact selected perpetual source')
            finally:delta.requester.close()
        raise ValueError('Selected broker has no deployed AI strategy adapter')

    def prepare(self,payload):
        config=configuration(payload,self.owner)
        # This is a reviewable configuration, not a claim of broker readiness.
        preview=option_preview(self.owner,config) if payload.get('preview_options') else None
        return dict(config=config,preview=preview,revision='ai-renko-options-v1',activation_required=True,
                    limitations=['Verified native market-parent ATR5 reference required','Hosted marker/seed agreement must be accepted before live activation'])
    def start(self,payload):
        with self.lock:
            if self.launching or self.snapshot()['running']:raise ValueError('AI runner already running')
            legacy=self.legacy.snapshot()
            if legacy.get('running') or legacy.get('position') or legacy.get('pending'):raise ValueError('Selected legacy runner is active or recovering; it remains untouched')
            config=configuration(payload,self.owner)
            if config['execution_route'] not in ('OPTIONS','DIRECT') or config['broker']=='FYERS' and (config['market'] not in ('NSE','BSE','MCX') or config['execution_route']=='OPTIONS' and config['market']=='MCX') or config['broker']=='DELTA_INDIA' and config['market']!='CRYPTO':raise ValueError('Selected broker/product has no runtime adapter; no fallback')
            if config['reference_state']!='VERIFIED':raise ValueError('Verified native parent ATR5 reference is unavailable for '+config['underlying'])
            live=payload.get('mode')=='LIVE'
            if payload.get('mode') not in ('PAPER','LIVE'):raise ValueError('Paper or Live required')
            if live and (not live_capability(self.owner) or payload.get('confirmation')!='START AI RENKO LIVE'):
                raise ValueError('Live requires this account live capability and explicit START AI RENKO LIVE confirmation')
            if not config['accept_close_source_renko_approximation']:raise ValueError('Review chart basis before starting')
            from datetime import datetime
            from zoneinfo import ZoneInfo
            identifier=datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(4)
            directory=DATA/'runs'/self.owner/identifier
            directory.mkdir(parents=True,mode=0o700)
            try:from .run import atomic
            except ImportError:from run import atomic
            atomic(directory/'config.json',config)
            self.run=dict(id=identifier,directory=directory,mode='LIVE' if live else 'PAPER')
            self.launching=True;self.error=None;self.cancelled=False
            threading.Thread(target=self._launch,args=(directory,live),daemon=True).start()
            return self.snapshot()
    def _launch(self,directory,live):
        try:
            preflight=subprocess.run([str(BASE/'.venv/bin/python'),str(BASE/'run.py'),'preflight','--config',str(directory/'config.json'),'--output',str(directory/'preflight')],cwd=BASE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90)
            (directory/'preflight.log').write_text(preflight.stdout)
            if preflight.returncode:raise ValueError('Preflight failed; retained '+str(directory/'preflight.log'))
            args=[str(BASE/'.venv/bin/python'),'-u',str(BASE/'run.py')]
            if live:args+=['--live']
            args+=['stream','--config',str(directory/'config.json'),'--output',str(directory)]
            with self.lock:
                if self.cancelled:return
                with (directory/'runtime.log').open('a') as log:
                    child_environment=dict(os.environ)
                    if live:child_environment['AI_RENKO_LIVE_ORDERS']=child_environment['NIFTY_AI_LIVE_ORDERS']='I_ACCEPT_REAL_ORDERS' # user-selected LIVE + typed confirmation + account gate validated above
                    self.process=subprocess.Popen(args,cwd=BASE,env=child_environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:from .process_state import identity
                    except ImportError:from process_state import identity
                    record=identity(self.process.pid,directory)
                    if record:
                        try:from .run import atomic
                        except ImportError:from run import atomic
                        atomic(directory/'process.json',record)
        except Exception as error:
            with self.lock:self.error=str(error)
        finally:
            with self.lock:self.launching=False
    def stop(self,payload):
        with self.lock:
            if not self.run:return self.snapshot()
            if payload.get('run_id')!=self.run['id']:raise ValueError('Stop requires exact AI run id')
            if self.launching:self.cancelled=True;return dict(self.snapshot(),notice='Preflight cancellation requested; no stream will start')
            if not self.process or self.process.poll() is not None:return self.snapshot()
            if payload.get('run_id')!=self.run['id']:raise ValueError('Stop requires exact AI run id')
            # This only terminates the subprocess created by this Service. It does NOT close a trade.
            self.process.terminate()
            return dict(self.snapshot(),notice='Stop requested; broker exposure and pending orders remain untouched. Reconcile owned position before restart.')
