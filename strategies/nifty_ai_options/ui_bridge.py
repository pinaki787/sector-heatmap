from strategies.nifty_ai_options.multi_runner import runtime_root,scope,selected_symbol,inventory,assert_start,account_lock,capacity,REVISION as MULTI_RUNNER_REVISION
"""Explicit UI-to-standalone bridge. No process is launched by import or preview."""
from pathlib import Path
import hashlib,json,os,secrets,subprocess,threading,time
from contextlib import nullcontext
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
    if broker in ('DHAN','MOTILAL_OSWAL'):
        if broker=='MOTILAL_OSWAL' and os.getenv('MOTILAL_ENABLE_LIVE_ORDERS')!='1':return False
        import sqlite3
        path=Path('/home/trading/sector-heatmap/.private/dashboard-login/registry.sqlite3')
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            row=db.execute('select live_enabled from accounts where id=? and broker=?',(owner,broker)).fetchone()
        from sector_heatmap.automation import AutomationPolicyService
        return bool(row and row[0] and not (AutomationPolicyService().current().get('profile') or {}).get('kill_switch_engaged',False))
    return False

def configuration(payload,owner):
    if not owner or payload.get('account_id')!=owner or payload.get('broker') not in ('FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'):
        raise ValueError('AI Renko Supertrend requires the exact private broker account')
    if owner_broker(owner)!=payload.get('broker'):raise ValueError('Selected broker differs from the registered owner')
    frames={'1 minute':1,'5 minutes':5,'30 minutes':30}
    if payload.get('timeframe') not in frames:raise ValueError('Choose 1, 5 or 30 minute source')
    if not payload.get('underlying'):raise ValueError('Select an underlying instrument')
    config=dict(account=owner,broker=payload.get('broker'),execution_mode=payload.get('mode','PAPER'),underlying=payload['underlying'],market=payload.get('ai_market') or payload['underlying'].split(':')[0],asset=payload.get('ai_asset'),execution_route=payload.get('ai_execution_route','OPTIONS'),baseline_minutes=30,sizing_policy_revision='selected-native-20261122',lots=payload.get('lots'),product=payload.get('ai_product'),expiry_policy='nearest_tradable',
        timeframe=frames[payload['timeframe']],target_premium=payload.get('target_premium',40),
        reference_source='external_native_parent_atr5',reference_session=payload.get('ai_reference_session'),
        reference_value=payload.get('ai_reference_value'),reference_symbol=payload.get('ai_reference_symbol'),reference_evidence=payload.get('ai_reference_evidence'),
        entry_gate='underlying_flip' if payload.get('ai_execution_route')=='DIRECT' else 'underlying_flip_premium_bullish',exit_supertrend='underlying' if payload.get('ai_execution_route')=='DIRECT' else 'premium',indicator_brick_mode='Manual',
        sma_exit_enabled=payload.get('ai_sma_exit_enabled',False),sma_price_basis='underlying',
        accept_close_source_renko_approximation=payload.get('ai_accept_chart_basis',False))
    if config['broker'] in ('FYERS','DHAN','MOTILAL_OSWAL') and config['execution_route']=='DIRECT' and not config['product']:config['product']='INTRADAY'
    if config['broker'] in ('DHAN','MOTILAL_OSWAL'):
        expected='MARGIN' if config['broker']=='DHAN' else 'NORMAL'
        if config['market'] not in ('NSE','BSE','MCX'):raise ValueError('Selected native market is unsupported')
        if config['broker']=='DHAN' and config['execution_route']=='DIRECT':
            if config['product'] not in ('INTRADAY','MARGIN'):raise ValueError('Select Dhan INTRADAY, or MARGIN for a future; delivery ownership is not certified for this route')
        elif config['broker']=='MOTILAL_OSWAL' and config['execution_route']=='DIRECT':
            if config['product'] not in ('INTRADAY','MARGIN'):raise ValueError('Select Intraday or futures Margin')
        elif config['execution_route']!='OPTIONS' or config['product']!=expected:raise ValueError('Select native bought-options '+expected+' product')
    if config['broker']=='MOTILAL_OSWAL' or payload.get('ai_market_data_broker'):
        if config['broker']!='MOTILAL_OSWAL' or payload.get('ai_market_data_broker','FYERS')!='FYERS':raise ValueError('Alternate FYERS data is available only for Motilal execution')
        try:from .motilal_fyers_data import source_account
        except ImportError:from motilal_fyers_data import source_account
        config['market_data_broker']='FYERS'
        config['market_data_account']=source_account(BASE.parent.parent/'.private/dashboard-login/registry.sqlite3',owner,payload.get('ai_market_data_account'))
    if config['broker']=='DELTA_INDIA':
        config['entry_order_type']='market_order'
        config['entry_execution_policy']='fresh-depth-market-entry-v1'
    if config['broker']=='DHAN' and config['execution_route']=='DIRECT':config.update(entry_order_type='MARKET_WITH_BROKER_MPP',exit_order_type='MARKET_WITH_BROKER_MPP')
    if config['broker']=='MOTILAL_OSWAL' and config['execution_route']=='DIRECT':config.update(entry_order_type='PROTECTED_LIMIT_IOC',exit_order_type='PROTECTED_LIMIT_IOC',protected_limit_ticks=1)
    calculation_mode=payload.get('ai_calculation_mode','CANDLES')
    if calculation_mode not in ('CANDLES','HYBRID'):raise ValueError('Choose candle or hybrid completed-unit calculation; display Renko is separate')
    config['calculation_mode']=calculation_mode
    config['supertrend_basis']='COMPLETED_RENKO' if calculation_mode=='HYBRID' else 'BROKER_CANDLES'
    config['display_mode']=payload.get('ai_display_mode','CANDLES')
    config['exit_confirmation_mode']='RENKO_BRICKS_ONLY' if calculation_mode=='HYBRID' and config['display_mode']=='RENKO' else 'HYBRID_COMPLETED_UNITS' if calculation_mode=='HYBRID' else 'COMPLETED_CANDLES'
    if config['display_mode'] not in ('CANDLES','RENKO'):raise ValueError('Choose Candles or Renko display')
    config['indicator_contract']='ai-renko-chart-v1'
    inputs=(payload.get('ai_indicator_inputs') if payload.get('ai_supertrend_enabled',True) is not False else None) or dict(length=5,factor=3,adx_enabled=False)
    if not isinstance(inputs,dict) or set(inputs)!={'length','factor','adx_enabled'}:raise ValueError('Exact plotted indicator settings required')
    length=inputs['length'];factor=inputs['factor']
    import math
    if isinstance(length,bool) or not isinstance(length,int) or not 1<=length<=1000 or isinstance(factor,bool) or not isinstance(factor,(int,float)) or not math.isfinite(factor) or factor<=0 or inputs['adx_enabled'] is not False:raise ValueError('Unsupported plotted indicator settings; no order source substituted')
    config['indicator_length']=length;config['indicator_factor']=factor;config['indicator_adx_enabled']=False
    signal_source=payload.get('ai_signal_source')
    if signal_source is not None and signal_source not in ('UNDERLYING','PREMIUM'):raise ValueError('Choose underlying or premium signal source')
    source=signal_source or payload.get('ai_entry_source')
    if source is not None and source not in ('UNDERLYING','PREMIUM'):raise ValueError('Choose underlying or premium entry source')
    if source is not None and config['execution_route']=='OPTIONS':
        config['entry_gate']='underlying_flip' if source=='UNDERLYING' else 'underlying_trend_premium_flip'
    if signal_source is not None:
        config['signal_source']='UNDERLYING' if config['execution_route']=='DIRECT' else signal_source
        config['exit_supertrend']='underlying' if config['signal_source']=='UNDERLYING' else 'premium'
        config['band_price_basis']=config['exit_supertrend']
    moneyness=payload.get('ai_option_moneyness','OTM')
    if moneyness not in ('OTM','ATM'):raise ValueError('Select OTM or ATM option classification')
    config['option_moneyness']=moneyness
    if config['broker']=='DELTA_INDIA' and config['execution_route']=='OPTIONS' and moneyness=='ATM':raise ValueError('ATM contract selection currently requires the FYERS option adapter')
    policy=payload.get('ai_expiry_policy','nearest_tradable')
    if policy not in ('nearest_tradable','explicit_listed'):raise ValueError('Unknown expiry policy')
    config['expiry_policy']=policy
    if policy=='explicit_listed':
        expiry=str(payload.get('ai_expiry',''))
        if config['broker'] in ('DHAN','MOTILAL_OSWAL'):
            from datetime import date
            try:day=date.fromisoformat(expiry)
            except ValueError:raise ValueError('Choose an exact listed native expiry date') from None
            from datetime import datetime
            from zoneinfo import ZoneInfo
            if day<datetime.now(ZoneInfo('Asia/Kolkata')).date():raise ValueError('Selected expiry is expired')
        elif not expiry.isdigit() or int(expiry)<=time.time():raise ValueError('Choose an unexpired broker-listed expiry')
        config['expiry']=expiry
    attachment=payload.get('ai_attach_position')
    if attachment is not None:
        if config['broker']!='FYERS' or config['execution_route']!='OPTIONS' or config['execution_mode']!='LIVE':raise ValueError('Existing broker position attachment requires FYERS bought options in Live mode')
        if not isinstance(attachment,dict) or set(attachment)!={'symbol','quantity','product'}:raise ValueError('Invalid attachment selection')
        if not isinstance(attachment['symbol'],str) or not attachment['symbol'].startswith(('NSE:','BSE:','MCX:')) or isinstance(attachment['quantity'],bool) or not isinstance(attachment['quantity'],int) or attachment['quantity']<=0 or attachment['product']!=config['product']:raise ValueError('Attachment contract, quantity or product invalid')
        config['attach_position']=dict(attachment)
    for kind in ('sma','ema'):
        period=payload.get('ai_'+kind+'_band_period',30)
        if isinstance(period,bool) or not isinstance(period,int) or not 1<=period<=500:raise ValueError('Band period must be a whole number from 1 to 500')
        config[kind+'_band_period']=period
        for use in ('entry','exit'):
            flag=payload.get('ai_'+kind+'_band_'+use,False)
            if not isinstance(flag,bool):raise ValueError('Band switches must be boolean')
            config[kind+'_band_'+use]=flag
    config['sma_retest_required']=payload.get('ai_sma_retest_required',False)
    if not isinstance(config['sma_retest_required'],bool):raise ValueError('SMA retest switch must be boolean')
    config['supertrend_enabled']=payload.get('ai_supertrend_enabled',True)
    if not isinstance(config['supertrend_enabled'],bool):raise ValueError('Supertrend switch must be boolean')
    if not config['supertrend_enabled']:
        config.update(sma_band_entry=True,sma_band_exit=True,ema_band_entry=False,ema_band_exit=False,sma_exit_enabled=False)
        config['band_price_basis']='underlying' if config.get('signal_source','UNDERLYING')=='UNDERLYING' else 'premium'
        config['strategy_signal_mode']='SMA_BAND_ONLY'
        config['entry_gate']='sma_band_only';config['exit_supertrend']='disabled'
    else:config['strategy_signal_mode']='SUPERTREND'
    try:from .sizing_policy import instrument_contract
    except ImportError:from sizing_policy import instrument_contract
    config.update(instrument_contract(config['market'],config.get('asset'),is_option=config['execution_route']=='OPTIONS',option_moneyness=config['option_moneyness']))
    sizing_mode=payload.get('ai_sizing_mode','AUTO')
    if sizing_mode not in ('AUTO','MANUAL_PARENT'):raise ValueError('Choose Auto or Manual parent sizing')
    config['sizing_mode']=sizing_mode
    if sizing_mode=='MANUAL_PARENT':
        try:from .native_sizing import manual_parent_reference,session_scope
        except ImportError:from native_sizing import manual_parent_reference,session_scope
        entered_at=payload.get('ai_manual_parent_entered_at',time.time())
        import math
        if isinstance(entered_at,bool) or not isinstance(entered_at,(int,float)) or not math.isfinite(entered_at) or entered_at<=0 or entered_at>time.time()+5:raise ValueError('Valid manual parent entry time required')
        lease=session_scope(config,now=entered_at)
        if lease['id']!=session_scope(config)['id'] or lease['valid_until']<=time.time():raise ValueError('Saved manual parent size belongs to an earlier session; review and re-enter it')
        config.update(manual_parent_value=payload.get('ai_manual_parent_value'),
            manual_parent_scope={k:config.get(k) for k in ('account','broker','underlying','market','asset')},
            manual_parent_entered_at=entered_at,manual_parent_session=lease['id'],
            manual_parent_valid_until=lease['valid_until'])
        return manual_parent_reference(config)
    try:from .native_reference import resolve_reference
    except ImportError:from native_reference import resolve_reference
    reference=resolve_reference(owner,config['underlying'],config['market'],config.get('asset'))
    config.update(reference_source='verified_native_cache',reference_value=reference['native_box'] if reference else None,reference_symbol=config['underlying'],reference_session=reference.get('reference_session') if reference else None,reference_evidence=(reference.get('source','')+' · '+reference.get('url','')) if reference else None,reference_state='VERIFIED' if reference else 'UNAVAILABLE')
    if reference and reference.get('native_provider')=='TRADINGVIEW':
        try:from .native_sizing import apply_reference
        except ImportError:from native_sizing import apply_reference
        config=apply_reference(config,reference)
    if not reference:
        try:from .native_sizing import failed_session_fallback
        except ImportError:from native_sizing import failed_session_fallback
        fallback=failed_session_fallback(config)
        if fallback:config=fallback
    return config

def expiry_options(owner,config):
    """Read-only selection metadata from the already connected exact account."""
    from datetime import datetime
    try:from .run import IST
    except ImportError:from run import IST
    if config.get('execution_route')!='OPTIONS':return dict(underlying=config['underlying'],expiries=[],read_only=True)
    if config['broker'] in ('DHAN','MOTILAL_OSWAL'):
        try:from .native_indian import bound_native
        except ImportError:from native_indian import bound_native
        adapter=bound_native(config);rows=adapter.option_rows();pairs={}
        for row in rows:pairs.setdefault((row['expiry'],row['strike']),set()).add(row['option_type'])
        expiries=sorted({e for (e,k),sides in pairs.items() if sides=={'CE','PE'}})
        listed=[];unavailable=[]
        for expiry in expiries:
            date=datetime.fromisoformat(expiry).replace(tzinfo=IST)
            try:deadline=date.timestamp()+adapter.session(date.replace(hour=12).timestamp())['closing_minutes']*60
            except ValueError:unavailable.append(expiry);continue
            if deadline>time.time():listed.append(dict(value=expiry,date=expiry,expires_at=deadline))
        if not listed:raise ValueError('No current paired native expiry with a verified venue calendar for selected underlying')
        return dict(account_id=owner,broker=config['broker'],underlying=config['underlying'],expiries=listed,nearest=listed[0]['value'],calendar_unavailable_dates=unavailable,checked_at=time.time(),read_only=True,orders_submitted=0)
    if config['broker']=='FYERS':
        try:from .live import client,Reads,ok,listed_expiries
        except ImportError:from live import client,Reads,ok,listed_expiries
        raw=client(owner)
        try:
            reply=ok(Reads(raw).optionchain(data=dict(symbol=config['underlying'],strikecount=1,timestamp='',greeks='1')))
            epochs=listed_expiries(reply.get('data') or {})
        finally:raw._sector_pulse_ipv4_session.close()
    else:
        try:from .delta_adapter import bound_delta
        except ImportError:from delta_adapter import bound_delta
        delta=bound_delta(owner,DATA/'preview-delta'/owner)
        try:
            from strategies.renko_supertrend.delta_contracts import perpetual_contract,option_contract
            parent=delta.product(config['underlying']);perpetual_contract(parent);now=delta.clock();epochs=set()
            for row in delta.catalog()['instruments']:
                if row.get('underlying')!=parent.get('underlying') or row.get('quoting_currency')!=parent.get('quoting_currency') or row.get('contract_type') not in ('call_options','put_options') or row.get('state')!='live' or row.get('trading_status')!='operational':continue
                epoch=datetime.fromisoformat(str(row['settlement_time']).replace('Z','+00:00')).timestamp()
                if epoch>now:epochs.add(int(option_contract(row,now)['expiry_epoch']))
            epochs=[str(x) for x in sorted(epochs)]
            if not epochs:raise ValueError('No listed tradable selected-underlying option expiry')
        finally:delta.requester.close()
    return dict(account_id=owner,broker=config['broker'],underlying=config['underlying'],
        expiries=[dict(value=e,date=datetime.fromtimestamp(float(e),IST).date().isoformat()) for e in epochs],
        nearest=epochs[0],checked_at=time.time(),read_only=True,orders_submitted=0)

def option_preview(owner,reference):
    """Bounded broker GETs only; no quantity, product, stream or order required."""
    try:from .live import Reads,Master,choose,sizes,client,IST
    except ImportError:from live import Reads,Master,choose,sizes,client,IST
    from datetime import datetime
    if reference.get('broker') in ('DHAN','MOTILAL_OSWAL'):
        try:from .native_indian import bound_native
        except ImportError:from native_indian import bound_native
        try:from .sizing_policy import scale_reference
        except ImportError:from sizing_policy import scale_reference
        adapter=bound_native(reference);contracts={}
        if reference.get('execution_route')=='DIRECT':
            meta=adapter.metadata(reference['underlying'])
            return dict(market_data_underlying=adapter.market_data.symbol(reference['underlying']) if adapter.market_data else None,market_data_account=adapter.market_data.account if adapter.market_data else None,account_id=owner,broker=reference['broker'],underlying=reference['underlying'],direct=meta,contracts={},spot_brick=scale_reference(reference['reference_value'],reference['market'],reference.get('asset'))['base_brick'] if reference.get('reference_value') else None,read_only=True,orders_submitted=0)
        for side in ('CE','PE'):
            c=adapter.select(side);q=adapter.signal_quote(c['symbol'])
            if adapter.market_data:c=dict(c,market_data_symbol=adapter.market_data.symbol(c['symbol']),market_data_broker='FYERS',market_data_account=adapter.market_data.account)
            geometry=scale_reference(reference['reference_value'],reference['market'],reference.get('asset'),is_option=True,option_moneyness=reference.get('option_moneyness','OTM')) if reference.get('reference_value') else {}
            contracts[side]=dict(c,ltp=q.get('last_price'),bid=q['bid'],ask=q['ask'],quote_at=q['exchange_at'],spot_brick=geometry.get('base_brick'),option_brick=geometry.get('premium_brick'),expiry_date=c['expiry'])
        if contracts['CE']['expiry']!=contracts['PE']['expiry']:raise ValueError('Native expiry changed during preview')
        return dict(market_data_underlying=adapter.market_data.symbol(reference['underlying']) if adapter.market_data else None,market_data_account=adapter.market_data.account if adapter.market_data else None,account_id=owner,broker=reference['broker'],contracts=contracts,underlying=reference['underlying'],resolved_expiry=contracts['CE']['expiry'],checked_at=time.time(),read_only=True,orders_submitted=0)
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
                contract,d=select_option(delta,reference['underlying'],side,reference.get('target_premium',40),expiry=reference.get('expiry') if reference.get('expiry_policy')=='explicit_listed' else None)
                contracts[side]=dict(contract,delta=d,spot_brick=base,option_brick=base*(0.5 if reference.get('option_moneyness','OTM')=='ATM' else 0.25) if base is not None else None,expiry_date=datetime.fromtimestamp(float(contract['expiry']),IST).date().isoformat())
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
            spot,brick=sizes(reference['reference_value'],delta,reference.get('market','NSE'),reference.get('asset'),reference.get('option_moneyness','OTM')) if reference.get('reference_value') else (None,None)
            contracts[side]=dict(contract,delta=delta,spot_brick=spot,option_brick=brick,
                expiry_date=datetime.fromtimestamp(float(contract['expiry']),IST).date().isoformat())
        if contracts['CE']['expiry']!=contracts['PE']['expiry']:raise ValueError('Expiry changed during preview; repeat read-only preview')
        return dict(contracts=contracts,resolved_expiry=contracts['CE']['expiry'],checked_at=datetime.now(IST).isoformat(),read_only=True,orders_submitted=0,
            reference_session=reference['reference_session'],reference_value=reference['reference_value'],reference_evidence=reference['reference_evidence'],
            underlying=reference['underlying'],quote_note='Provider chain snapshot; executable fresh quotes are rechecked only at a later explicit Start/trade')
    finally:raw._sector_pulse_ipv4_session.close()

def fail_position_request(directory,message,request_id=None):
    path=Path(directory)/'position-controls/latest.json'
    if not path.exists():return
    receipt=json.loads(path.read_text())
    if request_id is not None and receipt.get('request_id')!=request_id:return
    if receipt.get('phase') not in ('QUEUED','CLAIMED','WAITING_FOR_SOURCE','VERIFYING_FLAT'):return
    try:from .run import atomic
    except ImportError:from run import atomic
    receipt.update(phase='RECOVERY_REQUIRED',error=message,updated_at=time.time(),broker_flat_confirmed=False)
    atomic(path,receipt);atomic(path.parent/'receipts'/(receipt['request_id']+'.json'),receipt)

class NativeLegacyView:
    def __init__(self,owner):self.owner=owner
    def snapshot(self):
        try:from .ownership import legacy_ownership
        except ImportError:from ownership import legacy_ownership
        return legacy_ownership(self.owner)


class Service:
    def __init__(self,owner,legacy,instrument=None):
        self.owner,self.legacy,self.instrument=owner,legacy,instrument
        self.lock=threading.RLock();self.process=None;self.run=None;self.launching=False;self.error=None;self.cancelled=False;self.control_process=None
        try:
            try:from .process_state import recover
            except ImportError:from process_state import recover
            self.run,self.process=recover(self.owner,DATA,instrument=getattr(self,'instrument',None))
            if self.run:
                change=self.run['directory']/'reconfigure.json'
                if change.exists():
                    command=json.loads(change.read_text())
                    if command.get('phase')=='PREPARING_TARGET':
                        try:from .run import atomic
                        except ImportError:from run import atomic
                        atomic(change,dict(command,phase='REJECTED',error='Dashboard restarted during target preparation; previous instrument retained'))
                    elif command.get('target_config') and command.get('phase') in ('QUEUED','READY_TO_HANDOVER'):
                        if self.process is None and command['phase']=='READY_TO_HANDOVER':
                            try:from .process_state import RecoveredProcess
                            except ImportError:from process_state import RecoveredProcess
                            self.process=RecoveredProcess(json.loads((self.run['directory']/'process.json').read_text()),self.run['directory'])
                        if self.process is not None:
                            threading.Thread(target=self._handover,args=(self.process,self.run['directory'],self.run['mode']=='LIVE',command['request_id']),daemon=True).start()

        except (OSError,ValueError,KeyError) as error:self.error='AI job recovery requires review: '+str(error)
    def snapshot(self):
        try:from .sma_band import ENTRY_POLICY_REVISION
        except ImportError:from sma_band import ENTRY_POLICY_REVISION
        with self.lock:
            # Follow only a durable, explicit attachment handover to its verified child.
            if self.run and (self.process is None or self.process.poll() is not None):
                receipt=self.run['directory']/'position-controls/latest.json'
                if receipt.exists():
                    handover=json.loads(receipt.read_text())
                    if handover.get('phase')=='HANDED_OVER' and handover.get('account_id')==self.owner:
                        from .process_state import recover
                        recovered,child=recover(self.owner,DATA,instrument=getattr(self,'instrument',None))
                        if recovered and child and child.poll() is None and recovered['id']==handover.get('replacement_run'):
                            self.run,self.process=recovered,child
                            self.error=None;self.launching=False
            # An explicitly restarted exact child may replace the previous PID.
            # Reattach monitoring only; never launches a child or submits an order.
            if self.run and (self.run['directory']/'process.json').exists():
                try:
                    from .process_state import RecoveredProcess,identity
                except ImportError:
                    from process_state import RecoveredProcess,identity
                record=json.loads((self.run['directory']/'process.json').read_text())
                if identity(record.get('pid'),self.run['directory'])==record and getattr(self.process,'pid',None)!=record.get('pid'):
                    self.process=RecoveredProcess(record,self.run['directory']);self.error=None
            try:from .release_state import snapshot as release_snapshot
            except ImportError:from release_state import snapshot as release_snapshot
            release=release_snapshot()
            result=dict(dhan_direct_ready=True,motilal_direct_ready=True,motilal_fyers_data_ready=True,hybrid_completed_units_ready=True,sma_retest_optional_ready=True,manual_parent_override_ready=True,sma_entry_policy_revision=ENTRY_POLICY_REVISION,sma_only_capable=True,native_broker_integration_ready=True,entry_exit_source_ready=True,live_capability=live_capability(self.owner),phase='PREFLIGHT' if self.launching else 'FAILED' if self.error or (self.process and self.process.poll() not in (None,0)) else 'STREAM' if self.process and self.process.poll() is None else 'STOPPED',error=self.error,revision='ai-renko-options-v1',sizing_policy_revision='selected-native-20261122',parent_contract_revision='parent-candles-20261124',native_acquisition_ready=False,running=bool(self.process and self.process.poll() is None),run_id=self.run['id'] if self.run else None)
            result.update(multi_runner_ready=True,multi_runner_revision=MULTI_RUNNER_REVISION,multi_runner_capacity=capacity(),runner_instrument=getattr(self,'instrument',None),runner_inventory=inventory(self.owner,DATA))
            if self.run and not result['running']:
                claims=[r for r in result['runner_inventory'] if r['run_id']==self.run['id'] and r['state']=='Preparing']
                if claims:result['phase']='PREFLIGHT'
            result.update(release_ready=release['ready'],execution_lifecycle_revision=release['revision'],release_notice=release.get('message'))
            try:
                try:from .native_sizing import authorize,jobs,REVISION
                except ImportError:from native_sizing import authorize,jobs,REVISION
                authorize(self.owner,owner_broker(self.owner))
                result.update(native_acquisition_ready=True,native_provider='TRADINGVIEW',native_provider_revision=REVISION,native_jobs=jobs(self.owner))
            except (ValueError,OSError):result['native_acquisition_ready']=False
            try:
                import sqlite3
                with sqlite3.connect('file:/home/trading/sector-heatmap/.private/dashboard-login/registry.sqlite3?mode=ro',uri=True) as db:
                    row=db.execute('SELECT u.username FROM users u JOIN accounts a ON a.user_id=u.id WHERE a.id=?',(self.owner,)).fetchone()
                result['settings_owner_username']=row[0] if row else None
            except (OSError,ValueError,sqlite3.Error):pass
            if owner_broker(self.owner)=='DELTA_INDIA':result['next_entry_order_type']='market_order'
            # Public measured reference/expiry metadata; no broker call or trading setting mutation.
            try:
                references=sorted((DATA/'references'/self.owner).glob('*.json'))
                measured=[]
                for path in references:
                    reference=json.loads(path.read_text())
                    if reference.get('account')==self.owner and reference.get('broker')==owner_broker(self.owner) and reference.get('verified_native_size') is True and reference.get('completed_parent') is True and reference.get('status','').startswith('VERIFIED_') and reference.get('native_box',0)>0 and reference.get('native_provider')=='TRADINGVIEW' and result['native_acquisition_ready'] and reference.get('valid_until',0)>time.time():measured.append(reference)
                result['native_references']=measured
                fallbacks=[]
                for manual_path in (DATA/'manual-session-fallback'/self.owner).glob('*.json'):
                    fields=json.loads(manual_path.read_text())
                    scope=fields.get('manual_parent_identity') or {}
                    if scope.get('account')!=self.owner or scope.get('broker')!=owner_broker(self.owner):continue
                    try:
                        try:from .native_sizing import failed_session_fallback
                        except ImportError:from native_sizing import failed_session_fallback
                        fallback=failed_session_fallback(scope)
                        if fallback:fallbacks.append(fallback['reference_context'])
                    except (ValueError,KeyError):pass
                result['manual_fallback_references']=fallbacks
                if measured:result['native_reference']=measured[-1]
                metadata=BASE/'evidence/verified-20261119/probe.json'
                result['expiry_policy']='nearest_tradable'
                from sector_heatmap.market_calendar import market_session
                result['expected_reference_session']=market_session()['last_completed_session']
            except (OSError,ValueError,KeyError):pass
            readiness=DATA/'capabilities'/self.owner/'native-readiness.json'
            if owner_broker(self.owner) in ('DHAN','MOTILAL_OSWAL'):
                ready=json.loads(readiness.read_text()) if readiness.exists() else {}
                result['native_broker_readiness']=ready
            if self.run:
                result.update(directory=str(self.run['directory']),mode=self.run['mode'],exit_code=self.process.poll() if self.process else None)
                exit_report=self.run['directory']/'runtime-exit.json'
                if not result['running'] and exit_report.exists():
                    exited=json.loads(exit_report.read_text())
                    if exited.get('cancelled'):result.update(phase='STOPPED',error=None)
                    if exited.get('exit_code') and not exited.get('cancelled'):
                        result.update(phase='FAILED',error=exited.get('error') or 'Strategy worker failed; inspect runtime diagnostics.',exit_code=exited['exit_code'])

                preflight=self.run['directory']/'preflight/preflight.json'
                if preflight.exists():result['run_expiry']=json.loads(preflight.read_text()).get('resolved_expiry')
                markers=self.run['directory']/'markers.json'
                if markers.exists():result['markers']=json.loads(markers.read_text())
                # Read the exact run's durable ledger even after SIGTERM/crash.
                # Account key comes from authenticated preflight, never a browser path.
                config=json.loads((self.run['directory']/'config.json').read_text())
                result.update(supertrend_basis=config.get('supertrend_basis','BROKER_CANDLES'),sma_retest_required=config.get('sma_retest_required',True),sizing_mode=config.get('sizing_mode','AUTO'),manual_parent_value=config.get('manual_parent_value'),supertrend_enabled=config.get('supertrend_enabled',True),display_mode=config.get('display_mode','CANDLES'),indicator_length=config.get('indicator_length',5),indicator_factor=config.get('indicator_factor',3.0),source_timeframe=config.get('timeframe'),execution_route=config.get('execution_route'),underlying=config.get('underlying'),calculation_mode=config.get('calculation_mode','RENKO'),option_moneyness=config.get('option_moneyness','OTM'),entry_gate=config.get('entry_gate'),signal_source=config.get('signal_source'),exit_supertrend=config.get('exit_supertrend'),chart_source_ready=(self.run['directory']/'chart-source').is_dir())
                result['chart_source_series']=[json.loads(path.read_text()) for path in (self.run['directory']/'chart-source').glob('*-meta.json')]

                proof=self.run['directory']/'preflight/preflight.json'
                if not proof.exists():proof=self.run['directory']/'preflight.json'
                details=json.loads(proof.read_text()) if proof.exists() else {}
                if result['running'] and (details.get('contracts') or config.get('execution_route')=='DIRECT'):result['contracts_preview']=dict(account_id=self.owner,underlying=config.get('underlying'),contracts=details.get('contracts',{}),market_data_underlying=details.get('market_data_underlying'),market_data_account=details.get('market_data_account'))
                key=self.owner if config.get('broker') in ('DELTA_INDIA','DHAN','MOTILAL_OSWAL') else details.get('account_sha256')
                suffix='live' if self.run['mode']=='LIVE' else 'paper'
                ledger_name=('direct-'+suffix if config.get('broker') in ('DHAN','MOTILAL_OSWAL') and config.get('execution_route')=='DIRECT' else 'native-indian-'+suffix if config.get('broker') in ('DHAN','MOTILAL_OSWAL') else 'delta-'+suffix if config.get('broker')=='DELTA_INDIA' else 'direct-'+suffix if config.get('execution_route')=='DIRECT' else suffix)+'.json'
                if isinstance(key,str) and len(key) in (32,64) and all(c in '0123456789abcdef' for c in key):
                    ledger=runtime_root(config,DATA)/key/ledger_name
                    if ledger.exists():
                        owned=json.loads(ledger.read_text())
                        try:from .exit_alerts import notices
                        except ImportError:from exit_alerts import notices
                        result['exit_notices']=[dict(row,account_id=self.owner,run_id=result['run_id']) for row in notices(owned)]

                        result['ownership']=dict(positions=owned.get('positions',[]),closing_legs=owned.get('closing_legs',{}),position=owned.get('position'),pending=owned.get('pending'),detached_position=owned.get('detached_position'),management_mode=owned.get('management_mode'),stop_verification_position=owned.get('stop_verification_position'),checked_at=time.time())
                heartbeat=self.run['directory']/'heartbeat.json'
                if heartbeat.exists():
                    result['heartbeat']=json.loads(heartbeat.read_text())
                    result['heartbeat_age']=time.time()-heartbeat.stat().st_mtime
                if result.get('ownership'):
                    result['heartbeat']=dict(result.get('heartbeat') or {},position=result['ownership']['position'],pending=result['ownership']['pending'])
                result['heartbeat']=dict(result.get('heartbeat') or {},timeframe=config.get('timeframe'))
                recovered=self.run['directory']/'reconciliation.json'
                if recovered.exists() and not result['running']:
                    receipt=json.loads(recovered.read_text());owned=result.get('ownership') or {}
                    if receipt.get('phase')=='RECOVERED_CLOSED' and receipt.get('account_id')==self.owner and receipt.get('run_id')==self.run['id'] and receipt.get('runtime_session')==config.get('runtime_session') and not any(owned.get(k) for k in ('position','pending','detached_position','positions','closing_legs','stop_verification_position')):
                        result.update(reconciliation={k:receipt.get(k) for k in ('phase','key','completed_at','entry_order','exit_order','broker_flat','external_position')},phase='STOPPED',error=None,notice='Historical fill and external broker close reconciled; automation is stopped.')
                        external=receipt.get('external_position')
                        if external:result['notice']='Historical trade reconciled. Separate broker holding last verified: '+str(external['quantity'])+' contracts; not attached to automation. Fresh broker preflight remains required.'


                change=self.run['directory']/'reconfigure.json'
                if change.exists():result['reconfiguration']=json.loads(change.read_text())
                latest=self.run['directory']/'manual-entry/latest.json'
                if latest.exists():result['manual_entry']=json.loads(latest.read_text())
                heartbeat=result.get('heartbeat') or {}
                result['manual_entry_ready']=bool(result['running'] and result.get('heartbeat_age',999)<=10 and heartbeat.get('manual_entry_capable') is True and heartbeat.get('runtime_session')==config.get('runtime_session') and config.get('runtime_session'))
                try:
                    from .manual_entry import runtime_identity
                    from .position_control import REVISION
                except ImportError:
                    from manual_entry import runtime_identity
                    from position_control import REVISION
                if config.get('runtime_session'):
                    result['position_control_context']=runtime_identity(config,self.run['directory'],self.run['mode'])
                    capable=not result['running'] or (heartbeat.get('position_control') or {}).get('revision')==REVISION
                    result['position_control_capable']=bool(capable and config.get('broker') in ('FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'))
                latest=self.run['directory']/'position-controls/latest.json'
                if latest.exists():result['position_control_receipt']=json.loads(latest.read_text())
                receipt=result.get('position_control_receipt') or {}
                if not result['running'] and receipt.get('phase')=='STOPPED' and all(receipt.get(k)==v for k,v in dict(account_id=self.owner,run_id=self.run['id'],runtime_session=config.get('runtime_session')).items()) and (receipt.get('no_owned_position') or receipt.get('broker_flat_confirmed') or receipt.get('simulated_flat_confirmed')):
                    result.update(phase='STOPPED',error=None,exit_code=0)
                result['position_control']=heartbeat.get('position_control') or dict(mode=(result.get('ownership') or {}).get('management_mode','MANAGED'))
                if (result.get('ownership') or {}).get('detached_position'):result['position_control']['mode']='DETACHED'
                result['active_lots']=config.get('lots');result['active_product']=config.get('product')
                if result['manual_entry_ready']:
                    try:from .manual_entry import runtime_identity
                    except ImportError:from manual_entry import runtime_identity
                    result['manual_entry_context']=runtime_identity(config,self.run['directory'],self.run['mode'])
            try:
                try:from .trade_journal import snapshot as journal_snapshot
                except ImportError:from trade_journal import snapshot as journal_snapshot
                result['trade_journal']=journal_snapshot(self.owner,result.get('run_id'),instrument=getattr(self,'instrument',None))
            except (ValueError,OSError) as error:result['trade_journal']=dict(rows=[],sync=dict(state='ERROR',error=str(error)))
            return result
    def chart_source(self,query):
        try:from .chart_source import read_source
        except ImportError:from chart_source import read_source
        return read_source(DATA,self.owner,query.get('run_id'),query.get('symbol'),int(query.get('frame','0')),after=query.get('after'))

    def search(self,query,market,route='OPTIONS'):
        broker=owner_broker(self.owner)
        if broker in ('DHAN','MOTILAL_OSWAL'):
            if route!='OPTIONS' and not (broker in ('DHAN','MOTILAL_OSWAL') and route=='DIRECT'):raise ValueError('Selected native direct route is unavailable')
            try:from .native_indian import bound_native
            except ImportError:from native_indian import bound_native
            adapter=bound_native(dict(broker=broker,account=self.owner,underlying='NSE:NIFTY50-INDEX',market='NSE',execution_route='OPTIONS',product='MARGIN' if broker=='DHAN' else 'NORMAL'))
            if route=='DIRECT':
                try:from .dhan_direct import search_direct
                except ImportError:from dhan_direct import search_direct
                if broker=='MOTILAL_OSWAL':
                    try:from .motilal_direct import search_direct
                    except ImportError:from motilal_direct import search_direct
                return dict(matches=search_direct(adapter.native,query,market),message='Exact selected-broker equity/futures master')
            return dict(matches=adapter.native.search(query,market),message='Selected native broker current master; no source fallback')
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
        if config.get('sizing_mode')=='MANUAL_PARENT' and not config.get('sizing_fallback'):
            try:from .native_sizing import remember_manual
            except ImportError:from native_sizing import remember_manual
            config=remember_manual(config)
        if payload.get('list_positions') is True:
            if self.run:
                saved=json.loads((self.run['directory']/'config.json').read_text())
                if saved.get('underlying')==config['underlying'] and saved.get('broker')==config['broker']:config=saved
            if config.get('execution_mode')!='LIVE':raise ValueError('External position attachment requires Live mode')
            return dict(positions=self._position_candidates(config),account_id=self.owner,underlying=config['underlying'],read_only=True,orders_submitted=0)
        if config['broker'] in ('DHAN','MOTILAL_OSWAL') and payload.get('preview_options'):
            try:
                try:from .native_indian import bound_native
                except ImportError:from native_indian import bound_native
                adapter=bound_native(config);proof=adapter.validate();rows=adapter.candles()
                readiness=dict(execution_route=config['execution_route'],market_data_broker=config.get('market_data_broker'),market_data_account=config.get('market_data_account'),account_id=self.owner,broker=config['broker'],underlying=config['underlying'],timeframe=config['timeframe'],checked_at=time.time(),valid_until=time.time()+60,ready=True,account_identity=proof['account_identity'],history_rows=len(rows),product=config['product'],signal_source=config.get('signal_source','UNDERLYING'),orders_submitted=0)
                if config.get('sma_exit_enabled'):adapter.candles(frame=1)
            except Exception as error:
                readiness=dict(account_id=self.owner,broker=config['broker'],underlying=config['underlying'],timeframe=config['timeframe'],checked_at=time.time(),valid_until=time.time()+30,ready=False,error=str(error),orders_submitted=0)
                try:from .run import atomic
                except ImportError:from run import atomic
                atomic(DATA/'capabilities'/self.owner/'native-readiness.json',readiness)
                raise
            try:from .run import atomic
            except ImportError:from run import atomic
        if payload.get('expiry_options') is True:return dict(config=config,expiry_options=expiry_options(self.owner,config),activation_required=True)
        native_job=None
        if config['reference_state'] not in ('VERIFIED','MANUAL'):
            try:
                try:from .native_sizing import request
                except ImportError:from native_sizing import request
                native_job=request(config)
                if native_job.get('state')=='FAILED':
                    try:from .native_sizing import failed_session_fallback
                    except ImportError:from native_sizing import failed_session_fallback
                    fallback=failed_session_fallback(config)
                    if fallback:config=fallback
            except (ValueError,OSError) as error:native_job=dict(state='FAILED',symbol=config['underlying'],error=str(error))
        # This is a reviewable configuration, not a claim of broker readiness.
        try:
            preview=option_preview(self.owner,config) if payload.get('preview_options') else None
            if config['broker'] in ('DHAN','MOTILAL_OSWAL') and payload.get('preview_options'):
                if config.get('signal_source')=='PREMIUM':
                    for contract in preview['contracts'].values():adapter.candles(contract['symbol'])
                atomic(DATA/'capabilities'/self.owner/'native-readiness.json',readiness)
        except Exception as error:
            if config['broker'] in ('DHAN','MOTILAL_OSWAL'):
                atomic(DATA/'capabilities'/self.owner/'native-readiness.json',dict(account_id=self.owner,broker=config['broker'],ready=False,error=str(error),checked_at=time.time(),valid_until=time.time()+30,orders_submitted=0))
            raise
        return dict(config=config,preview=preview,native_job=native_job,revision='ai-renko-options-v1',activation_required=True,
                    limitations=['Sizing uses the authorized official TradingView native calculation; execution uses the selected broker','Unavailable or stale native sizing blocks new entries'])
    def start(self,payload):
        with self.lock,account_lock(self.owner,DATA) if getattr(self,'instrument',None) else nullcontext():
            try:from .release_state import require_ready
            except ImportError:from release_state import require_ready
            config=configuration(payload,self.owner)
            if getattr(self,'instrument',None):
                if config['underlying']!=self.instrument:raise ValueError('Start instrument differs from selected runner')
                config['runner_scope']=scope(self.instrument)
                assert_start(config,DATA)
            require_ready(config)
            if self.launching or self.snapshot()['running']:raise ValueError('AI runner already running')
            legacy=self.legacy.snapshot()
            if legacy.get('running') or legacy.get('position') or legacy.get('pending'):raise ValueError('Selected legacy runner is active or recovering; it remains untouched')
            if (self.snapshot().get('ownership') or {}).get('closing_legs'):raise ValueError('Previous option exits remain retained; use Stop recovery before starting a new run')
            if config['execution_route'] not in ('OPTIONS','DIRECT') or config['broker']=='FYERS' and (config['market'] not in ('NSE','BSE','MCX')) or config['broker']=='DELTA_INDIA' and config['market']!='CRYPTO':raise ValueError('Selected broker/product has no runtime adapter; no fallback')
            if (self.snapshot().get('ownership') or {}).get('detached_position'):raise ValueError('Detached broker holding retained; use Attach or Stop before starting new entries')
            if config['reference_state'] not in ('VERIFIED','MANUAL'):
                try:from .native_sizing import authorize,context
                except ImportError:from native_sizing import authorize,context
                authorize(self.owner,config['broker']);context(config)
            live=payload.get('mode')=='LIVE'
            if payload.get('mode') not in ('PAPER','LIVE'):raise ValueError('Paper or Live required')
            if payload.get('start_requested') is not True:raise ValueError('Start the strategy using its Start button')
            if live and not live_capability(self.owner):raise ValueError('Live execution is not enabled for this account')
            if not config['accept_close_source_renko_approximation']:raise ValueError('Review chart basis before starting')
            from datetime import datetime
            from zoneinfo import ZoneInfo
            identifier=datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(4)
            directory=DATA/'runs'/self.owner/identifier
            directory.mkdir(parents=True,mode=0o700)
            try:from .run import atomic
            except ImportError:from run import atomic
            atomic(directory/'config.json',config)
            if config.get('runner_scope'):
                from .process_state import fingerprint
                atomic(directory/'launching.json',dict(at=time.time(),pid=os.getpid(),start_ticks=fingerprint(os.getpid())))
            self.run=dict(id=identifier,directory=directory,mode='LIVE' if live else 'PAPER')
            self.launching=True;self.error=None;self.cancelled=False
            threading.Thread(target=self._launch,args=(directory,live),daemon=True).start()
            return self.snapshot()
    def _launch(self,directory,live):
        try:
            config={}
            config_path=directory/'config.json'
            if config_path.exists():
                config=json.loads(config_path.read_text())
                if config.get('broker')=='FYERS':
                    environment=subprocess.run([str(BASE/'.venv/bin/python'),'-c','from fyers_apiv3.FyersWebsocket import data_ws; import requests,certifi,websocket'],cwd=BASE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
                    (directory/'environment.log').write_text(environment.stdout)
                    if environment.returncode:raise ValueError('FYERS worker streaming SDK unavailable; saved broker session is unchanged. See launch environment diagnostics.')
                try:from .native_sizing import ensure
                except ImportError:from native_sizing import ensure
                if not config.get('_managed_resume'):config=ensure(config)
                try:from .run import atomic
                except ImportError:from run import atomic
                atomic(config_path,config)
            if not config.get('_managed_resume'):
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
                    if live:child_environment['AI_RENKO_LIVE_ORDERS']=child_environment['NIFTY_AI_LIVE_ORDERS']='I_ACCEPT_REAL_ORDERS' # user clicked Start with LIVE selected; account capability validated above
                    self.process=subprocess.Popen(args,cwd=BASE,env=child_environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:from .process_state import identity
                    except ImportError:from process_state import identity
                    record=identity(self.process.pid,directory)
                    if config.get('runner_scope'):
                        deadline=time.monotonic()+2
                        while not record and self.process.poll() is None and time.monotonic()<deadline:
                            time.sleep(.02);record=identity(self.process.pid,directory)
                        if not record:raise ValueError('Instrument worker launch identity unavailable; initialization remains blocked')
                    if record:
                        try:from .run import atomic
                        except ImportError:from run import atomic
                        atomic(directory/'process.json',record)
                    if isinstance(self.process.pid,int):threading.Thread(target=self._watch,args=(self.process,directory),daemon=True).start()
        except Exception as error:
            with self.lock:self.error=str(error)
            fail_position_request(directory,'Position management did not launch; broker exposure is preserved. '+str(error))
        finally:
            (directory/'launching.json').unlink(missing_ok=True)
            with self.lock:self.launching=False
    def _watch(self,process,directory):
        code=process.wait()
        fail_position_request(directory,'Position-management worker ended before confirming its request; retained exposure requires reconciliation')
        try:from .run import atomic
        except ImportError:from run import atomic
        message='Strategy worker stopped with an error; inspect runtime diagnostics. Broker session and retained exposure are preserved.' if code and not self.cancelled else None
        atomic(directory/'runtime-exit.json',dict(exit_code=code,completed_at=time.time(),error=message,cancelled=self.cancelled))
        with self.lock:
            if self.process is process and message:self.error=message

    def reconfigure(self,payload):
        with self.lock:
            snapshot=self.snapshot();heartbeat=snapshot.get('heartbeat') or {}
            if (snapshot.get('position_control') or {}).get('mode') not in (None,'MANAGED'):raise ValueError('Resolve position controls before changing the runtime')
            if not snapshot.get('running') or snapshot.get('heartbeat_age',999)>10 or not heartbeat.get('reconfigure_capable'):raise ValueError('Runtime changes require the active runner and a fresh capable heartbeat')
            if payload.get('confirmed') is not True:raise ValueError('Confirm the active-runner change warning first')
            if (snapshot.get('manual_entry') or {}).get('phase') in ('QUEUED','CLAIMED','PREPARING','SUBMITTING'):raise ValueError('Wait for the existing manual entry request before changing runner selection')
            config=json.loads((self.run['directory']/'config.json').read_text())
            if heartbeat.get('runtime_session')!=config.get('runtime_session'):raise ValueError('Runtime session changed')
            try:from .runtime_control import enqueue
            except ImportError:from runtime_control import enqueue
            directory=self.run['directory'];child=self.process;live=self.run['mode']=='LIVE'
            if payload.get('underlying')==config['underlying'] and payload.get('calculation_mode',config.get('calculation_mode','RENKO'))==config.get('calculation_mode','RENKO') and not (config.get('calculation_mode') in ('CANDLES','HYBRID') and payload.get('timeframe')!=config['timeframe']):
                command=enqueue(directory,config,payload)
                return dict(self.snapshot(),reconfiguration=command)
            symbol=payload.get('underlying')
            if config.get('runner_scope') and symbol!=config['underlying']:raise ValueError('Select another instrument runner instead of moving this worker')
            if not isinstance(symbol,str) or not symbol:raise ValueError('Exact target instrument required')
            target=dict(config,underlying=symbol,reference_symbol=symbol,timeframe=payload.get('timeframe'),calculation_mode=payload.get('calculation_mode',config.get('calculation_mode','RENKO')),expiry_policy='nearest_tradable');target.pop('expiry',None)
            target['market']=symbol.split(':')[0].split('_')[0] if config['broker'] in ('FYERS','DHAN','MOTILAL_OSWAL') else 'CRYPTO'
            if target['market'] not in ('NSE','BSE','MCX','CRYPTO'):raise ValueError('Target instrument has no supported execution adapter')
            command=enqueue(directory,config,payload,target_config=target,preparing=True)
        # Slow read-only acquisition never holds the Stop/status lock. The old
        # child sees PREPARING_TARGET immediately and keeps owned exits active.
        path=directory/'reconfigure.json'
        try:
            try:from .native_sizing import ensure
            except ImportError:from native_sizing import ensure
            target=ensure(target);preview=option_preview(self.owner,target)
            product_type=(preview.get('direct') or {}).get('product_type')
            if product_type=='STOCK' and target.get('product') not in ('CNC','INTRADAY') or product_type=='FUTURE' and target.get('product') not in ('MARGIN','INTRADAY'):raise ValueError('The target requires a different product; stop and configure that product explicitly')
            with self.lock:
                latest=json.loads(path.read_text())
                if self.cancelled or self.process is not child or child.poll() is not None or latest.get('request_id')!=command['request_id'] or latest.get('phase')!='PREPARING_TARGET':raise ValueError('Target preparation was cancelled or superseded')
                try:from .run import atomic
                except ImportError:from run import atomic
                command=dict(command,target_config=target,phase='QUEUED',prepared_at=time.time());atomic(path,command)
                threading.Thread(target=self._handover,args=(child,directory,live,command['request_id']),daemon=True).start()
                return dict(self.snapshot(),reconfiguration=command)
        except Exception as error:
            with self.lock:
                latest=json.loads(path.read_text())
                if latest.get('request_id')==command['request_id'] and latest.get('phase')=='PREPARING_TARGET':
                    try:from .run import atomic
                    except ImportError:from run import atomic
                    atomic(path,dict(latest,phase='REJECTED',error=str(error) if isinstance(error,ValueError) else 'Target instrument preparation failed'))
            raise

    def _handover(self,child,directory,live,request_id):
        path=directory/'reconfigure.json'
        try:
            while True:
                with self.lock:
                    if self.cancelled or self.process is not child or not self.run or self.run['directory']!=directory:return
                    command=json.loads(path.read_text())
                    if command.get('request_id')!=request_id:return
                    phase=command.get('phase')
                    if phase not in ('PREPARING_TARGET','QUEUED','READY_TO_HANDOVER'):return
                    ended=child.poll() is not None
                    if ended:
                        if phase!='READY_TO_HANDOVER':raise ValueError('Runner ended before instrument handover was ready')
                        heartbeat=json.loads((directory/'heartbeat.json').read_text())
                        if not heartbeat.get('terminal') or heartbeat.get('position') or heartbeat.get('pending'):raise ValueError('Instrument handover requires confirmed flat terminal ownership')
                        if live and not live_capability(self.owner):raise ValueError('Live capability changed before instrument handover')
                        target=command['target_config']
                        try:from .run import atomic
                        except ImportError:from run import atomic
                        atomic(directory/'config.json',target)
                        self.launching=True;self.error=None
                        break
                time.sleep(.25)
            self._launch(directory,live)
            while True:
                with self.lock:
                    if self.cancelled:return
                    if self.error or self.process is child or not self.process or self.process.poll() is not None:raise ValueError(self.error or 'Target runner did not launch')
                    command=json.loads(path.read_text())
                    if command.get('request_id')!=request_id:return
                    heartbeat=json.loads((directory/'heartbeat.json').read_text())
                    active_config=json.loads((directory/'config.json').read_text())
                    if heartbeat.get('runtime_session')==active_config.get('runtime_session') and heartbeat.get('runtime_session')!=command.get('runtime_session') and not heartbeat.get('terminal'):
                        atomic(path,dict(command,phase='APPLIED',applied_at=time.time()));return
                time.sleep(.25)
        except Exception as error:
            with self.lock:
                self.error=str(error) if isinstance(error,ValueError) else 'Instrument handover requires review'
                if path.exists():
                    command=json.loads(path.read_text())
                    if command.get('request_id')==request_id:
                        try:from .run import atomic
                        except ImportError:from run import atomic
                        atomic(path,dict(command,phase='REJECTED',error=self.error))

    def manual_entry(self,payload):
        with self.lock:
            snapshot=self.snapshot()
            if not self.run or not self.process or self.process.poll() is not None or not snapshot.get('manual_entry_ready'):raise ValueError('Manual entry requires the current active AI runner and a fresh heartbeat')
            if (snapshot.get('reconfiguration') or {}).get('phase') in ('PREPARING_TARGET','QUEUED','READY_TO_HANDOVER'):raise ValueError('Wait for the confirmed runtime change before manual entry')
            config=json.loads((self.run['directory']/'config.json').read_text())
            if config.get('_verification_only'):raise ValueError('Verification-only artifacts cannot accept a manual entry')
            if config.get('account')!=self.owner or payload.get('account_id')!=self.owner or config.get('broker')!=owner_broker(self.owner):raise ValueError('Manual entry requires the exact active broker account')
            if self.run['mode']=='LIVE' and not live_capability(self.owner):raise ValueError('Live capability is unavailable for this account')
            heartbeat=snapshot.get('heartbeat') or {}
            if heartbeat.get('position') or heartbeat.get('pending'):raise ValueError('Manual entry requires no owned position or pending order')
            if not snapshot.get('native_acquisition_ready') or (heartbeat.get('native_sizing') or {}).get('state')!='READY':raise ValueError('Fresh verified automatic sizing is required for manual entry')
            try:from .manual_entry import runtime_identity,enqueue
            except ImportError:from manual_entry import runtime_identity,enqueue
            command=enqueue(self.run['directory'],runtime_identity(config,self.run['directory'],self.run['mode']),payload)
            return dict(self.snapshot(),manual_entry=command,notice='Manual entry requested; the active runner will manage its confirmed position and strategy exits')

    def _position_candidates(self,config):
        try:
            from .position_brokers import FyersPositions,DeltaPositions
            from .run import client
        except ImportError:
            from position_brokers import FyersPositions,DeltaPositions
            from run import client
        if config['broker'] in ('DHAN','MOTILAL_OSWAL'):
            try:from .native_indian import bound_native
            except ImportError:from native_indian import bound_native
            rows=bound_native(config).candidates()
        elif config['broker']=='FYERS':
            try:
                from .live import Master
                from .markets import FyersInstrumentMaster
            except ImportError:
                from live import Master
                from markets import FyersInstrumentMaster
            raw=client(self.owner)
            try:
                from hashlib import sha256
                identity=(raw.get_profile().get('data') or {}).get('fy_id')
                if not identity:raise ValueError('Broker account identity unavailable')
                master=(Master if config['execution_route']=='OPTIONS' else FyersInstrumentMaster)(DATA/'attachment-master'/self.owner)
                rows=FyersPositions(raw,config,master,sha256(str(identity).encode()).hexdigest()).candidates()
            finally:raw._sector_pulse_ipv4_session.close()
        else:
            try:from .delta_adapter import bound_delta
            except ImportError:from delta_adapter import bound_delta
            from strategies.renko_supertrend.delta_execution import Execution
            delta=bound_delta(self.owner,DATA/'preview-delta'/self.owner)
            try:rows=DeltaPositions(delta,config,Execution(delta)).candidates()
            finally:delta.requester.close()
        return [{k:v for k,v in row.items() if k!='meta'} for row in rows]

    def position_action(self,payload):
        with self.lock:
            if not self.run:raise ValueError('Select the exact saved strategy run')
            config=json.loads((self.run['directory']/'config.json').read_text())
            try:
                from .manual_entry import runtime_identity
                from .position_control import enqueue,TERMINAL
            except ImportError:
                from manual_entry import runtime_identity
                from position_control import enqueue,TERMINAL
            expected=runtime_identity(config,self.run['directory'],self.run['mode'])
            if any(payload.get(k)!=v for k,v in expected.items()):raise ValueError('Position control is not bound to this account and runtime')
            if config['account']!=self.owner or owner_broker(self.owner)!=config['broker']:raise ValueError('Position-control owner mismatch')
            if config['execution_mode']=='LIVE' and not live_capability(self.owner):raise ValueError('Live position control is not enabled for this account')
            snapshot=self.snapshot();operation=payload.get('operation')
            if snapshot.get('running') and (snapshot.get('heartbeat_age',999)>10 or not snapshot.get('position_control_capable')):raise ValueError('The active worker has not loaded position controls; it remains untouched')
            if (snapshot.get('reconfiguration') or {}).get('phase') in ('QUEUED','PREPARING_TARGET','READY_TO_HANDOVER'):raise ValueError('An instrument/timeframe change is pending; position action was not sent')
            if operation=='ATTACH':
                try:from .ownership import assert_attach_available
                except ImportError:from ownership import assert_attach_available
                assert_attach_available(config)
            if operation=='ATTACH' and not snapshot.get('running'):
                if config['execution_mode']!='LIVE':raise ValueError('Select an actual open Live broker holding')
                holding=payload.get('holding') or {}
                if len([r for r in self._position_candidates(config) if all(r.get(k)==holding.get(k) for k in ('symbol','quantity','product'))])!=1:raise ValueError('Selected broker holding changed; refresh open positions')
            request=enqueue(self.run['directory'],config,payload)
            if request['phase'] in TERMINAL:return self.snapshot()
            if snapshot.get('running'):return dict(self.snapshot(),notice='Position request queued; broker outcome is not yet confirmed')
            if operation=='ATTACH':
                holding=payload['holding']
                from datetime import datetime
                from zoneinfo import ZoneInfo
                identifier=datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(4)
                directory=DATA/'runs'/self.owner/identifier;directory.mkdir(parents=True,mode=0o700)
                resume=dict(config,_managed_resume=True,runtime_session=secrets.token_hex(16));resume.pop('attach_position',None)
                proof=self.run['directory']/'preflight/preflight.json'
                if not proof.exists():proof=self.run['directory']/'preflight.json'
                details=json.loads(proof.read_text())
                resume['_resume_account_sha256']=details.get('account_sha256');resume['_resume_account_identity']=details.get('account_identity')
                try:from .run import atomic
                except ImportError:from run import atomic
                atomic(directory/'config.json',resume);atomic(directory/'preflight/preflight.json',details)
                replacement=dict(runtime_identity(resume,directory,self.run['mode']),operation='ATTACH',request_id=payload['request_id'],holding=holding)
                enqueue(directory,resume,replacement)
                old=self.run['directory']/'position-controls'
                completed=dict(request,phase='HANDED_OVER',replacement_run=identifier)
                atomic(old/'latest.json',completed);atomic(old/'receipts'/(request['request_id']+'.json'),completed)
                self.run=dict(id=identifier,directory=directory,mode=resume['execution_mode']);self.process=None
                self.launching=True;self.cancelled=False;self.error=None
                threading.Thread(target=self._launch,args=(directory,resume['execution_mode']=='LIVE'),daemon=True).start()
                return dict(self.snapshot(),notice='Attaching the exact existing holding; no entry order is requested')
            if getattr(self,'control_process',None) is not None and self.control_process.poll() is None:raise ValueError('A stopped-job position request is already running')
            args=[str(BASE/'.venv/bin/python'),'-u',str(BASE/'run.py')]
            if config['execution_mode']=='LIVE':args+=['--live']
            args+=['position-control','--config',str(self.run['directory']/'config.json'),'--output',str(self.run['directory'])]
            environment=dict(os.environ)
            if config['execution_mode']=='LIVE':environment['AI_RENKO_LIVE_ORDERS']='I_ACCEPT_REAL_ORDERS'
            try:
                with (self.run['directory']/'position-control.log').open('a') as output:
                    self.control_process=subprocess.Popen(args,cwd=BASE,env=environment,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            except Exception:
                fail_position_request(self.run['directory'],'Position-control process did not launch; broker exposure is preserved')
                raise
            threading.Thread(target=self._watch_position_control,args=(self.control_process,self.run['directory'],request['request_id']),daemon=True).start()
            return dict(self.snapshot(),notice='Position request accepted; square-off or detach is not confirmed until broker reconciliation completes')

    def _watch_position_control(self,process,directory,request_id):
        process.wait()
        fail_position_request(directory,'Position-control worker ended before confirmation; broker exposure and order intents are preserved',request_id)
    def stop(self,payload):
        with self.lock:
            if not self.run:raise ValueError('No AI run selected')
            if self.launching:
                if payload.get('run_id')!=self.run['id'] or payload.get('account_id')!=self.owner:raise ValueError('Preflight cancellation requires the exact run and account')
                self.cancelled=True
                return dict(self.snapshot(),notice='Preflight cancellation requested; no position close is claimed')
            path=self.run['directory']/'config.json'
            if not path.exists():raise ValueError('Saved run configuration unavailable; no process interrupted')
            config=json.loads(path.read_text())
            try:from .manual_entry import runtime_identity
            except ImportError:from manual_entry import runtime_identity
            expected=runtime_identity(config,self.run['directory'],self.run['mode'])
            if any(payload.get(k)!=v for k,v in expected.items()):raise ValueError('Position control requires the exact account/run/session')
            change=self.run['directory']/'reconfigure.json'
            if change.exists():
                command=json.loads(change.read_text())
                if command.get('phase') in ('PREPARING_TARGET','QUEUED','READY_TO_HANDOVER'):
                    try:from .run import atomic
                    except ImportError:from run import atomic
                    self.cancelled=True
                    atomic(change,dict(command,phase='CANCELLED',cancelled_at=time.time()))
        return self.position_action(dict(payload,operation='STOP'))
