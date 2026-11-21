"""Explicit UI-to-standalone bridge. No process is launched by import or preview."""
from pathlib import Path
import hashlib,json,os,secrets,subprocess,threading,time
BASE=Path('/home/trading/sector-heatmap/strategies/nifty_ai_options')
DATA=Path('/home/trading/sector-heatmap/.private/nifty-ai-options')
MODE='AI_RENKO_OPTIONS'
def configuration(payload,owner):
    if not owner or payload.get('account_id')!=owner or payload.get('broker')!='FYERS':
        raise ValueError('AI Renko Supertrend requires the exact private FYERS account')
    frames={'1 minute':1,'5 minutes':5,'30 minutes':30}
    if payload.get('timeframe') not in frames:raise ValueError('Choose 1, 5 or 30 minute source')
    if payload.get('underlying')!='NSE:NIFTY50-INDEX':raise ValueError('AI options strategy requires Nifty50 underlying')
    return dict(account=owner,lots=payload.get('lots'),product=payload.get('ai_product'),expiry=payload.get('ai_expiry'),
        timeframe=frames[payload['timeframe']],target_premium=payload.get('target_premium',40),
        reference_source='external_native_renko_6h_atr5',reference_session=payload.get('ai_reference_session'),
        reference_value=payload.get('ai_reference_value'),reference_evidence=payload.get('ai_reference_evidence'),
        entry_gate='underlying_flip_premium_bullish',exit_supertrend='premium',indicator_brick_mode='Manual',
        sma_exit_enabled=payload.get('ai_sma_exit_enabled',False),sma_price_basis='underlying',
        accept_close_source_renko_approximation=payload.get('ai_accept_chart_basis',False))
class Service:
    def __init__(self,owner,legacy):
        self.owner,self.legacy=owner,legacy
        self.lock=threading.RLock();self.process=None;self.run=None;self.launching=False;self.error=None;self.cancelled=False
    def snapshot(self):
        with self.lock:
            result=dict(live_capability=bool(os.getenv('NIFTY_AI_LIVE_ORDERS')=='I_ACCEPT_REAL_ORDERS' or os.getenv('SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS')=='1'),phase='PREFLIGHT' if self.launching else 'FAILED' if self.error or (self.process and self.process.poll() not in (None,0)) else 'STREAM' if self.process and self.process.poll() is None else 'STOPPED',error=self.error,revision='ai-renko-options-v1',running=bool(self.process and self.process.poll() is None),run_id=self.run['id'] if self.run else None)
            # Public measured reference/expiry metadata; no broker call or trading setting mutation.
            try:
                references=sorted((BASE/'evidence').glob('native-reference-*.json'))
                if references:
                    reference=json.loads(references[-1].read_text())
                    if reference.get('parent_hours')==6 and reference.get('atr_length')==5 and reference.get('native_box',0)>0:
                        result['native_reference']=reference
                metadata=BASE/'evidence/verified-20261119/probe.json'
                if metadata.exists():result['available_expiries']=json.loads(metadata.read_text()).get('expiry_data',[])
                from sector_heatmap.market_calendar import market_session
                result['expected_reference_session']=market_session()['last_completed_session']
            except (OSError,ValueError,KeyError):pass
            if self.run:
                result.update(directory=str(self.run['directory']),mode=self.run['mode'],exit_code=self.process.poll() if self.process else None)
                heartbeat=self.run['directory']/'heartbeat.json'
                if heartbeat.exists():
                    result['heartbeat']=json.loads(heartbeat.read_text())
                    result['heartbeat_age']=time.time()-heartbeat.stat().st_mtime
            return result
    def prepare(self,payload):
        config=configuration(payload,self.owner)
        # This is a reviewable configuration, not a claim of broker readiness.
        return dict(config=config,revision='ai-renko-options-v1',activation_required=True,
                    limitations=['Dated native six-hour Renko ATR5 reference required','Hosted marker/seed agreement must be accepted before live activation'])
    def start(self,payload):
        with self.lock:
            if self.launching or self.snapshot()['running']:raise ValueError('AI runner already running')
            legacy=self.legacy.snapshot()
            if legacy.get('running') or legacy.get('position') or legacy.get('pending'):raise ValueError('Selected legacy runner is active or recovering; it remains untouched')
            config=configuration(payload,self.owner)
            live=payload.get('mode')=='LIVE'
            if payload.get('mode') not in ('PAPER','LIVE'):raise ValueError('Paper or Live required')
            if live and (not (os.getenv('NIFTY_AI_LIVE_ORDERS')=='I_ACCEPT_REAL_ORDERS' or os.getenv('SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS')=='1') or payload.get('confirmation')!='START AI RENKO LIVE'):
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
                    if live:child_environment['NIFTY_AI_LIVE_ORDERS']='I_ACCEPT_REAL_ORDERS' # user-selected LIVE + typed confirmation + account gate validated above
                    self.process=subprocess.Popen(args,cwd=BASE,env=child_environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
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
