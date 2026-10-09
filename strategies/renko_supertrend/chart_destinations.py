"""Read-only entry study selection and source preparation for chart replay."""
from . import ema_proximity, market_structure, mtf_supertrend

def query_settings(query):
    enabled=(query.get('chart_entry_guards') or ['false'])[0]=='true'
    values={key:(query.get(key) or ['false'])[0]=='true' for key in ('ema_proximity_enabled','market_structure_enabled','higher_timeframe_enabled')}
    for key in ('ema_proximity_mode','ema_proximity_distance','supertrend_timeframe','timeframe','broker'):
        if key in query:values[key]=query[key][0]
    # Validate each chart destination independently from the saved execution config.
    return dict(chart_entry_guards=enabled,**ema_proximity.settings(values),**market_structure.settings(values),**mtf_supertrend.settings(values)) if enabled else {'chart_entry_guards':False}
