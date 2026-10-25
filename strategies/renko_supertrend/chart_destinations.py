"""Read-only entry study selection and source preparation for chart replay."""
from . import ema_proximity, market_structure, mtf_supertrend, mtf_rsi

def query_settings(query):
    enabled=(query.get('chart_entry_guards') or ['false'])[0]=='true'
    values={key:(query.get(key) or ['false'])[0]=='true' for key in ('ema_momentum_enabled','ema_proximity_enabled','market_structure_enabled','higher_timeframe_enabled')}
    for key in ('ema_proximity_mode','ema_proximity_distance','supertrend_timeframe','timeframe','broker'):
        if key in query:values[key]=query[key][0]
    if not values['ema_proximity_enabled']:values['ema_momentum_enabled']=False
    # Validate each chart destination independently from the saved execution config.
    return dict(chart_entry_guards=enabled,**ema_proximity.settings(values),**market_structure.settings(values),**mtf_supertrend.settings(values),**mtf_rsi.query_settings(query)) if enabled else {'chart_entry_guards':False}
