from . import destinations
"""Versioned UI preferences, kept separate from armed runner configuration."""
import json
import os
from pathlib import Path
from .signals import settings
from . import exit_indicators
from . import ema_proximity, trailing_stop, zone_target, market_structure, mtf_supertrend

KEYS=('symbol','timeframe','atr-length','factor','brick-mode','manual-brick','use-adx','adx-threshold','adx-length','adx-smoothing','widening-window','rsi-slope-enabled','intrabar-entries','retest-enabled','retest-engulfing','retest-harami','retest-star','mode','lots','max-trades','max-premium','daily-budget','spot-target','spot-stop','ema-exit-enabled','ema-exit-length','sideways-enabled','sideways-max-candles','additional-slippage-points','ema-proximity-enabled','ema-proximity-mode','ema-proximity-distance','trailing-enabled','trailing-basis','trailing-distance','chart-view','history-preset','history-from','history-to')
MAP={'rsi-length':'rsi_slope_length','supertrend-enabled':'supertrend_enabled','ema-fast-enabled':'ema_fast_enabled','ema-slow-enabled':'ema_slow_enabled','ema-widening-enabled':'ema_widening_enabled','ema-fast-length':'ema_fast_length','ema-slow-length':'ema_slow_length','atr-length':'atr_length','brick-mode':'brick_mode','manual-brick':'manual_brick','use-adx':'use_adx','adx-threshold':'adx_threshold','adx-length':'adx_length','adx-smoothing':'adx_smoothing','widening-window':'widening_window','rsi-slope-enabled':'rsi_slope_enabled','retest-enabled':'retest_enabled','retest-engulfing':'retest_engulfing','retest-harami':'retest_harami','retest-star':'retest_star'}
KEYS=KEYS+tuple(k.replace('_','-') for k in exit_indicators.DEFAULTS)+( 'rsi-length','volume-enabled','rsi-sma-enabled','supertrend-enabled','ema-fast-enabled','ema-slow-enabled','ema-widening-enabled','ema-fast-length','ema-slow-length','higher-timeframe-enabled','supertrend-timeframe','market-structure-enabled','zone-target-enabled','paper-capital','commodity-holding','cash-product','market','session-deadline','price-source','order-terms','carry-policy','delta-execution-route')

KEYS=KEYS+tuple(key.replace('_','-')+'-indicator' for key in destinations.RULES)

def read(path):
    p=Path(path)
    if not p.exists():return dict(schema_version=1,settings={},saved_at=None)
    d=json.loads(p.read_text())
    if d.get('schema_version')!=1 or not isinstance(d.get('settings'),dict):raise ValueError('Saved preferences format is unsupported; preferences were preserved.')
    return d

def write(path,payload,now):
    values=payload.get('settings')
    if not isinstance(values,dict):raise ValueError('A settings object is required.')
    c={k:values[k] for k in KEYS if k in values}
    for k in ('volume-enabled','rsi-sma-enabled','supertrend-enabled','ema-fast-enabled','ema-slow-enabled','ema-widening-enabled','rsi-slope-enabled','use-adx','intrabar-entries','retest-enabled','retest-engulfing','retest-harami','retest-star','ema-exit-enabled','sideways-enabled','ema-proximity-enabled','trailing-enabled','zone-target-enabled','market-structure-enabled','higher-timeframe-enabled'):
        if k in c and not isinstance(c[k],bool):raise ValueError('Saved checkbox settings must be booleans.')
    settings({MAP.get(k,k):v for k,v in c.items()})
    extras={k.replace('-','_'):v for k,v in c.items()}
    exit_indicators.settings(extras)
    destinations.settings(extras)
    mtf_supertrend.settings(extras)
    ema_proximity.settings(extras);trailing_stop.settings(extras);zone_target.settings(extras);market_structure.settings(extras)
    if c.get('commodity-holding','INTRADAY') not in ('INTRADAY','CARRY_FORWARD'):raise ValueError('Unknown MCX holding policy.')
    if c.get('cash-product','INTRADAY') not in ('INTRADAY','CNC'):raise ValueError('Unknown cash holding product.')
    if c.get('market','ALL') not in ('ALL','NSE_INDEX','BSE_INDEX','NSE_STOCK','BSE_STOCK','MCX','CRYPTO','NSE_EQUITY','BSE_EQUITY'):raise ValueError('Unknown Renko market.')
    if 'paper-capital' in c:
        from sector_heatmap.paper_wallet import capital
        capital(c['paper-capital'])
    if c.get('delta-execution-route','OPTIONS') not in ('OPTIONS','DELTA_PERPETUAL'):raise ValueError('Unknown Delta execution route.')
    if c.get('mode','PAPER') not in ('PAPER','LIVE'):raise ValueError('Choose Paper or Live explicitly.')
    if c.get('chart-view','host') not in ('host','synthetic'):raise ValueError('Unknown chart view.')
    for k in ('lots','max-trades'):
        if k in c and (int(c[k])<1 or float(c[k])!=int(c[k])):raise ValueError('Lots and trade limit must be positive integers.')
    if c.get('history-preset','45') not in ('7','45','90','custom'):raise ValueError('Unknown historical range preset.')
    result=dict(schema_version=1,settings=c,saved_at=now)
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp')
    with tmp.open('w') as f:
        os.chmod(tmp,0o600);json.dump(result,f,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    return result
