try:from .trend_filter import entry_allowed,entry_proof,current_trend_confirmation
except ImportError:from trend_filter import entry_allowed,entry_proof,current_trend_confirmation
try:from . import sma_only
except ImportError:import sma_only
"""Selected-instrument direct AI Renko signals; no premium series or delta."""
try:
    from .core import positive,SMAExit,chart_candle
    from .indicator import Traditional,AIRenko
    from .hybrid_confirmation import HybridConfirmation,confirm_exit
    from .sizing_policy import scale_reference
except ImportError:
    from core import positive,SMAExit,chart_candle
    from indicator import Traditional,AIRenko
    from hybrid_confirmation import HybridConfirmation,confirm_exit
    from sizing_policy import scale_reference

try:from .sma_band import BandPolicy,observe_band
except ImportError:from sma_band import BandPolicy,observe_band

class DirectStrategy:
    def __init__(self,config):
        sma_only.validate(config)
        self.config=dict(config)
        self.calculation_mode=config.get('calculation_mode','RENKO')
        if self.calculation_mode not in ('CANDLES','RENKO','HYBRID'):raise ValueError('Choose the strategy chart calculation mode')
        self.band=BandPolicy(self.config)
        if config.get('timeframe') not in (1,5,30):raise ValueError('Execution source must be 1/5/30 minutes')
        if not config.get('underlying'):raise ValueError('Selected underlying required')
        sized=scale_reference(config['reference_value'],config['market'],config.get('asset'),explicit_category=config.get('sizing_category'))
        self.parent_hours=sized['parent_hours'];self.allow_short=config.get('product')!='CNC';self.spot_size=sized['base_brick'];self.under_renko=Traditional(self.spot_size)
        self.under_ai=AIRenko(length=config.get('indicator_length',5),factor=config.get('indicator_factor',3.0),manual_brick=self.spot_size,pine_series_precision=True,completed_bricks=config.get('supertrend_basis')=='COMPLETED_RENKO',midline_period=config.get('midline_period',123) if config.get('midline_filter_enabled',False) else None,track_close=config.get('zone_targets_enabled',False) or config.get('grid_trailing_enabled',False) or config.get('swing_targets_enabled',False) or any(config.get(k) is not None for k in ('bull_entry_level','bear_entry_level')))
        self.entry_confirmation=HybridConfirmation(self.spot_size);self.hybrid_sequence=0;self.hybrid_price_at=None;self.hybrid_exchange_at=None;self.hybrid_last_sequence=0
        self.position=self.under_result=None;self.pending_direction=None;self.last_time={};self.sma=SMAExit()
        self.contract=dict(symbol=config['underlying'],underlying=config['underlying'],spot_brick=self.spot_size,execution_route='DIRECT',asset=config.get('asset'),parent_hours=self.parent_hours)
    def reset_contract(self,contract,delta=None):
        if delta is not None:raise ValueError('Direct instruments never use option delta')
        if self.position:raise ValueError('Cannot resize or replace an owned contract')
        if contract.get('symbol')!=self.config['underlying']:raise ValueError('Direct execution must match selected instrument')
        self.contract=dict(contract,spot_brick=self.spot_size,execution_route='DIRECT',asset=self.config.get('asset'),parent_hours=self.parent_hours)
    def update(self,event):
        self.entry_observation_at=event.get('available_at',event.get('closed_at',event['timestamp']))
        if sma_only.enabled(self.config):return sma_only.update(self,event,False)
        kind=event['kind'];at=event['timestamp']
        if kind not in ('underlying','sma'):raise ValueError('Direct strategy has no option premium series')
        if kind in self.last_time and at<=self.last_time[kind]:raise ValueError('Duplicate/out-of-order observation')
        self.last_time[kind]=at;close=positive(event['close'],'Close')
        if kind=='underlying':
            band_actions=observe_band(self,event)
            if band_actions:return band_actions
        if kind=='sma':
            if not self.config.get('sma_exit_enabled',False):return []
            cross=self.sma.update(at,close)
            if self.position and ((self.position['side']=='LONG' and cross=='BELOW') or (self.position['side']=='SHORT' and cross=='ABOVE')):
                self.pending_direction=None
                return self.exit(at,'OPTIONAL_UNDERLYING_1M_SMA30')
            return []
        previous_direction=self.under_result['direction'] if self.under_result else 1
        formed=False
        # Process every full brick, then decide once on this confirmed source observation.
        # Intermediate synthetic levels are not separate executable market observations.
        if self.calculation_mode=='HYBRID':
            try:from .hybrid_basis import seed
            except ImportError:from hybrid_basis import seed
            warm_bricks=seed(self,event,'underlying')
        for bar in (warm_bricks if self.calculation_mode=='HYBRID' and self.config.get('supertrend_basis')=='COMPLETED_RENKO' else [chart_candle(event)] if self.calculation_mode in ('CANDLES','HYBRID') else self.under_renko.update(close)):
            self.under_result=self.under_ai.update(bar);formed=True
            if self.calculation_mode=='HYBRID' and self.config.get('supertrend_basis')=='COMPLETED_RENKO':
                try:from .hybrid_basis import record_signal
                except ImportError:from hybrid_basis import record_signal
                record_signal(self,event,'underlying',bar,self.under_result)
        if self.config.get('sma_band_entry') and formed and self.position is None:
            confirmation=self.band.reentry(event,self.config,self.under_result,not_before=getattr(self,'entry_reset_at',0))
            if confirmation:
                self.pending_direction=(confirmation['direction'],event.get('available_at',event.get('closed_at',at+self.config['timeframe']*60)))
                self.entry_observation_at=self.pending_direction[1]
                action=self.selected_gate_entry()
                if action:action['confirmation']=confirmation;return [action]
        current=current_trend_confirmation(self,dict(bar,kind='brick',closed=True,closed_at=event.get('closed_at',at),available_at=event.get('available_at',event.get('closed_at',at))),self.under_result) if formed and self.calculation_mode=='RENKO' else None
        if not formed or self.under_result['direction']==previous_direction and not current:return []
        direction='LONG' if self.under_result['direction']<0 else 'SHORT';self.pending_direction=(direction,at) if entry_allowed(self,direction) else None
        if self.position:
            return self.exit(at,'AI_RENKO_SUPERTREND_UNDERLYING') if self.position['side']!=direction else []
        action=self.selected_gate_entry();return [action] if action else []
    def update_hybrid(self,event):
        self.entry_observation_at=event.get('available_at',event.get('closed_at',event['timestamp']))
        if sma_only.enabled(self.config):return sma_only.update(self,event,False)
        """Live price forms full bricks; verified candle bodies only confirm current trend."""
        kind=event['kind']
        if kind=='sma':return self.update(event)
        at=event.get('available_at',event['timestamp'])
        positive(at,'Observation availability')
        units=[]
        if kind=='price':
            if self.calculation_mode=='CANDLES':return []
            price=positive(event['close'],'Selected broker price')
            exchange=positive(event['timestamp'],'Provider timestamp')
            if self.hybrid_exchange_at is not None and exchange<self.hybrid_exchange_at:raise ValueError('Out-of-order provider price')
            sequence=event.get('sequence')
            if sequence is not None:
                if isinstance(sequence,bool) or not isinstance(sequence,int) or sequence<=self.hybrid_last_sequence:raise ValueError('Duplicate live price sequence')
                self.hybrid_last_sequence=sequence
            self.hybrid_exchange_at=exchange
            if self.hybrid_price_at is not None and at<self.hybrid_price_at:raise ValueError('Out-of-order live price')
            self.hybrid_price_at=at;self.hybrid_sequence+=1
            if self.calculation_mode=='HYBRID':
                try:from .hybrid_basis import price as price_basis
                except ImportError:from hybrid_basis import price as price_basis
                formed,probe=price_basis(self,event,'underlying')
            else:formed,probe=self.under_renko.update(price),None
            for index,bar in enumerate(formed):
                previous=self.under_result['direction'] if self.under_result else 1
                self.under_result=bar['_signal_result'] if self.calculation_mode=='HYBRID' and self.config.get('supertrend_basis')=='COMPLETED_RENKO' else dict(probe,flip=bool(probe['flip'] and index==0)) if self.calculation_mode=='HYBRID' else self.under_ai.update(bar)
                direction='LONG' if self.under_result['direction']<0 else 'SHORT'
                if self.under_result['direction']!=previous:
                    self.entry_confirmation.clear()
                    if entry_allowed(self,direction):self.entry_confirmation.arm(direction,at,('price',self.hybrid_sequence,len(units)),source_at=exchange)
                units.append(dict(bar,kind='brick',closed=True,closed_at=event['timestamp'],available_at=at,direction=direction,st=self.under_result['st']))
        elif kind=='underlying':
            if self.calculation_mode=='HYBRID' and (event.get('closed') is not True or event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE' or event.get('body_available') is not True):return []
            if at<=self.last_time.get('hybrid_candle',0):raise ValueError('Duplicate hybrid candle')
            self.last_time['hybrid_candle']=at;self.last_time['underlying']=event['timestamp']
            if event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE' or event.get('body_available') is not True:return []
            if self.calculation_mode in ('CANDLES','HYBRID'):
                if self.calculation_mode=='HYBRID':
                    if event.get('closed') is not True:return []
                    try:from .hybrid_basis import confirmed
                    except ImportError:from hybrid_basis import confirmed
                    self.under_result=confirmed(self,event,'underlying')
                    if self.config.get('supertrend_basis')=='COMPLETED_RENKO':
                        try:from .hybrid_basis import store
                        except ImportError:from hybrid_basis import store
                        units.extend(dict(bar,kind='brick',closed=True,closed_at=event['closed_at'],available_at=at,direction='LONG' if bar['_signal_result']['direction']<0 else 'SHORT',st=bar['_signal_result']['st']) for bar in store(self)['underlying'].pop('confirmed_bricks',[]))
                    if self.under_result is None:return observe_band(self,event)
                else:self.under_result=self.under_ai.update(chart_candle(event))
                if self.under_result['flip']:
                    self.entry_confirmation.clear()
                    if entry_allowed(self,'LONG' if self.under_result['direction']<0 else 'SHORT'):self.entry_confirmation.arm('LONG' if self.under_result['direction']<0 else 'SHORT',at,('candle',event['timestamp']),source_at=event.get('closed_at',event['timestamp']+self.config['timeframe']*60))
            if not self.under_result:return observe_band(self,event)
            direction='LONG' if self.under_result['direction']<0 else 'SHORT'
            if self.config.get('supertrend_basis')!='COMPLETED_RENKO' or abs(event['close']-event['open'])<self.spot_size:
                units.append(dict(kind='host_candle' if self.calculation_mode=='CANDLES' else 'candle',open=event['open'],close=event['close'],closed=True,closed_at=event.get('closed_at',event['timestamp']+self.config['timeframe']*60),available_at=at,direction=direction,st=self.under_result['st']))
        else:raise ValueError('Unsupported hybrid observation')
        if self.config.get('exit_confirmation_mode')=='RENKO_BRICKS_ONLY':
            units=[unit for unit in units if unit.get('kind')=='brick']
        if self.calculation_mode=='HYBRID':
            try:from .hybrid_basis import brick_event
            except ImportError:from hybrid_basis import brick_event
            event=brick_event(event,units)
        band_actions=observe_band(self,event)
        if band_actions:self.band.retest=None;return band_actions
        reentry=self.band.reentry(event,self.config,self.under_result,flat=self.position is None,not_before=getattr(self,'entry_reset_at',0)) if event['kind']=='underlying' else None
        if not units:return []
        # Use the final complete unit from this executable observation.
        unit=units[-1];direction=unit['direction'];line=unit['st']
        from strategies.nifty_ai_options.swing_targets import target_exit
        target_actions=target_exit(self,units,at)
        if target_actions:return target_actions
        current=current_trend_confirmation(self,unit,self.under_result)
        entry=current or self.entry_confirmation.confirm(unit,direction,line) or reentry
        if current:self.entry_confirmation.clear()
        if self.position:
            exit_confirmation=confirm_exit(unit,self.position,direction,line,self.spot_size)
            if not exit_confirmation:return []
            self.pending_direction=(direction,at) if entry else None
            actions=self.exit(at,'AI_RENKO_SUPERTREND_UNDERLYING')
            actions[0]['confirmation']=exit_confirmation
            return actions
        if not entry:return []
        self.pending_direction=(direction,at)
        action=self.selected_gate_entry()
        if action:action['confirmation']=entry
        return [action] if action else []

    def manual_entry(self,direction,at):
        self.band.consume_entry()
        if self.position:raise ValueError('An owned position already exists')
        if direction not in ('LONG','SHORT'):raise ValueError('Choose LONG or SHORT for a direct manual entry')
        if direction=='SHORT' and not self.allow_short:raise ValueError('Cash delivery does not permit a short entry')
        positive(at,'Manual entry timestamp');self.entry_reset_at=at;self.pending_direction=None;self.band.retest=None
        self.position=dict(self.contract,side=direction,entry_timestamp=at,manual_override=True)
        from strategies.nifty_ai_options.swing_targets import capture
        capture(self,self.position)
        return dict(action='OPEN_'+direction,timestamp=at,position=dict(self.position),manual_override=True)

    def selected_gate_entry(self):
        if sma_only.enabled(self.config):return sma_only.entry(self,False)
        if self.position or self.pending_direction is None:return None
        direction,at=self.pending_direction;self.pending_direction=None
        if not entry_allowed(self,direction):return None
        if not self.band.entry_ready(direction,self.config,getattr(self,'entry_observation_at',at)):return None
        if direction=='SHORT' and not self.allow_short:return None
        self.band.consume_entry()
        self.position=dict(self.contract,side=direction,entry_timestamp=at,midline_confirmation=entry_proof(self))
        from strategies.nifty_ai_options.swing_targets import capture
        capture(self,self.position)
        return dict(action='OPEN_'+direction,timestamp=at,position=dict(self.position))
    def exit(self,at,reason):
        self.band.consume_entry()
        self.entry_reset_at=at
        self.sma_only_pending=None
        self.band.retest=None
        position=self.position;self.position=None
        return [dict(action='CLOSE_'+position['side'],timestamp=at,reason=reason,position=position)]

def complete_reversal(engine,executor,closed_action,submit):
    """Run the opposite entry only after the exact owned exit has completed."""
    if executor.state.get('pending_reversal'):
        try:from .reversal import advance
        except ImportError:from reversal import advance
        return advance(engine,executor,submit)
    if getattr(engine,'entry_paused',False):return None
    action=closed_action.get('action')
    if action not in ('CLOSE_LONG','CLOSE_SHORT') or closed_action.get('reason')!='AI_RENKO_SUPERTREND_UNDERLYING':return None
    if executor.state.get('position') or executor.state.get('pending'):return None
    direction='LONG' if action=='CLOSE_SHORT' else 'SHORT'
    pending=engine.pending_direction
    if not pending or pending!=(direction,closed_action['timestamp']):return None
    entry=engine.selected_gate_entry()
    if entry is None:return None
    if entry['action']!='OPEN_'+direction or entry['timestamp']!=closed_action['timestamp']:
        engine.position=None;raise ValueError('Reverse entry does not match the confirmed exit signal')
    return submit(entry)
