"""Selected-instrument direct AI Renko signals; no premium series or delta."""
try:
    from .core import positive,SMAExit
    from .indicator import Traditional,AIRenko
    from .sizing_policy import scale_reference
except ImportError:
    from core import positive,SMAExit
    from indicator import Traditional,AIRenko
    from sizing_policy import scale_reference

class DirectStrategy:
    def __init__(self,config):
        self.config=dict(config)
        if config.get('timeframe') not in (1,5,30):raise ValueError('Execution source must be 1/5/30 minutes')
        if not config.get('underlying'):raise ValueError('Selected underlying required')
        sized=scale_reference(config['reference_value'],config['market'],config.get('asset'),explicit_category=config.get('sizing_category'))
        self.parent_hours=sized['parent_hours'];self.allow_short=config.get('product')!='CNC';self.spot_size=sized['base_brick'];self.under_renko=Traditional(self.spot_size)
        self.under_ai=AIRenko(manual_brick=self.spot_size,pine_series_precision=True)
        self.position=self.under_result=None;self.pending_direction=None;self.last_time={};self.sma=SMAExit()
        self.contract=dict(symbol=config['underlying'],underlying=config['underlying'],spot_brick=self.spot_size,execution_route='DIRECT',asset=config.get('asset'),parent_hours=self.parent_hours)
    def reset_contract(self,contract,delta=None):
        if delta is not None:raise ValueError('Direct instruments never use option delta')
        if self.position:raise ValueError('Cannot resize or replace an owned contract')
        if contract.get('symbol')!=self.config['underlying']:raise ValueError('Direct execution must match selected instrument')
        self.contract=dict(contract,spot_brick=self.spot_size,execution_route='DIRECT',asset=self.config.get('asset'),parent_hours=self.parent_hours)
    def update(self,event):
        kind=event['kind'];at=event['timestamp']
        if kind not in ('underlying','sma'):raise ValueError('Direct strategy has no option premium series')
        if kind in self.last_time and at<=self.last_time[kind]:raise ValueError('Duplicate/out-of-order observation')
        self.last_time[kind]=at;close=positive(event['close'],'Close')
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
        for bar in self.under_renko.update(close):self.under_result=self.under_ai.update(bar);formed=True
        if not formed or self.under_result['direction']==previous_direction:return []
        direction='LONG' if self.under_result['direction']<0 else 'SHORT';self.pending_direction=(direction,at)
        if self.position:
            return self.exit(at,'AI_RENKO_SUPERTREND_UNDERLYING') if self.position['side']!=direction else []
        action=self.selected_gate_entry();return [action] if action else []
    def selected_gate_entry(self):
        if self.position or self.pending_direction is None:return None
        direction,at=self.pending_direction;self.pending_direction=None
        if direction=='SHORT' and not self.allow_short:return None
        self.position=dict(self.contract,side=direction,entry_timestamp=at)
        return dict(action='OPEN_'+direction,timestamp=at,position=dict(self.position))
    def exit(self,at,reason):
        position=self.position;self.position=None
        return [dict(action='CLOSE_'+position['side'],timestamp=at,reason=reason,position=position)]
