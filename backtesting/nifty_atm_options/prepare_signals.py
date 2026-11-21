"""Freeze a bounded grid using production indicator components, research only."""
import sys,json,itertools,pickle,gzip,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backtesting/renko_sideways_entry'))
sys.path.insert(0,str(ROOT/'backtesting/nifty_atm_options/frozen-source'))
from research import features
from replay import aggregate
from strategies.renko_supertrend.indicator_families import apply,FAMILIES
from strategies.renko_supertrend.rsi_slope import observe
from strategies.renko_supertrend import zone_target
Z=ZoneInfo('Asia/Kolkata');folder=ROOT/'backtesting/nifty_atm_options';source=folder/'inputs/underlying.json';raw=json.loads(source.read_text());original=json.loads((folder/'inputs/config.json').read_text())
rows=[dict(zip(('timestamp','open','high','low','close','volume'),r)) for r in raw['rows'] if 555<=datetime.fromtimestamp(r[0],Z).hour*60+datetime.fromtimestamp(r[0],Z).minute<930]
assert all(rows[i]['timestamp']<rows[i+1]['timestamp'] for i in range(len(rows)-1));assert all(r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] for r in rows)
days=sorted({datetime.fromtimestamp(r['timestamp'],Z).date().isoformat() for r in rows if datetime.fromtimestamp(r['timestamp'],Z).date().isoformat()>='2026-04-13'});cut=2*len(days)//3;periods={'development':set(days[:cut]),'validation':set(days[cut:])}
higher=aggregate(rows,15);rsi_rows=aggregate(rows,30);state={};rsi_values=[observe(state,r['close'],14) for r in rsi_rows];rsi_context=([r['timestamp']+1800 for r in rsi_rows],rsi_values);zones=[];zone_target.zones(rows,zones)
keys=('timestamp','direction','entry_direction','entry_qualified','raw_supertrend_cross_direction','ema10','ema30','ema_gap','rsi14','rsi14_slope','adx','host_atr','chop','er','flips8')
metadata=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),periods={k:sorted(v) for k,v in periods.items()},entry_grid=['EMA10/30 alignment+widening','EMA10 retest','host RSI14 slope','ADX14 >20','confirmed structure','15m Supertrend confirmation'],post_entry_grid=['EMA10 proximity <=0.5 ATR','30m RSI14 50 and slope'],exit_grid=['ST reversal','EMA10 breach','EMA30 breach'],secondary_exit_grid=['EMA contraction','5m supply/demand exit','10% option-premium trailing sampled at 5m opens','quick-loss range lock, 2 host candles'],source_hashes={name:hashlib.sha256((folder/'frozen-source'/name).read_bytes()).hexdigest() for name in ['strategies/renko_supertrend/signals.py','strategies/renko_supertrend/sideways.py','strategies/renko_supertrend/trailing_stop.py','strategies/renko_supertrend/zone_target.py','strategies/renko_supertrend/ema_proximity.py']})
metadata['frozen_source_hashes']={str(p.relative_to(folder/'frozen-source')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder/'frozen-source').rglob('*.py')}
metadata['config_sha256']=hashlib.sha256((folder/'inputs/config.json').read_bytes()).hexdigest()
metadata['cache_key']=hashlib.sha256((json.dumps(metadata,sort_keys=True)+Path(__file__).read_text()).encode()).hexdigest()
with gzip.open(folder/'common.pkl.gz','wb') as f:pickle.dump(dict(rows=rows,periods=periods,rsi_context=rsi_context,zones=zones),f)
for n,bits in enumerate(itertools.product((False,True),repeat=6)):
 path=folder/f'signals-{n:02d}.pkl.gz'
 if path.exists():
  with gzip.open(path,'rb') as f:cached=pickle.load(f)
  if cached.get('cache_key')==metadata['cache_key']:continue
 ema,retest,rsi,adx,structure,htf=bits;c=dict(original);c.pop('indicator_family_choices',None);c.pop('indicator_family_applied',None)
 for name in FAMILIES:c[name+'_family_enabled']=True
 c.update(supertrend_enabled=True,supertrend_exit_enabled=False,ema_fast_enabled=ema or retest,ema_slow_enabled=ema,ema_widening_enabled=ema,ema_fast_length=10,ema_slow_length=30,ema_exit_enabled=False,ema_slow_exit_enabled=False,ema_widening_exit_enabled=False,rsi_exit_enabled=False,adx_exit_enabled=False,market_structure_exit_enabled=False,rsi_slope_enabled=rsi,rsi_level_enabled=False,use_adx=adx,adx_threshold=20.,market_structure_enabled=structure,higher_timeframe_enabled=htf,supertrend_timeframe='15 minutes',retest_enabled=retest,zone_target_enabled=False,ema_proximity_enabled=False,manual_trend_enabled=False,chart_entry_guards=True,_chart_higher_rows=higher,atr_length=5,factor=3.,timeframe='5 minutes',brick_mode='Auto')
 c=apply(c);values=features(rows,c)
 # Prefix invariance checks use only corresponding confirmed HTF rows.
 prefix_cfg=dict(c,_chart_higher_rows=[r for r in higher if r['timestamp']+900<=rows[199]['timestamp']+300]);prefix=features(rows[:200],prefix_cfg)
 assert all(prefix[-1].get(k)==values[199].get(k) for k in keys),'Indicator future leakage'
 clean={k:v for k,v in c.items() if not k.startswith('_')};selected=[{k:s.get(k) for k in keys} for s in values]
 with gzip.open(path,'wb') as f:pickle.dump(dict(cache_key=metadata['cache_key'],config=clean,bits=bits,signals=selected),f)
 print('Prepared entry configurations',n+1,'/64',flush=True)
(folder/'grid.json').write_text(json.dumps(metadata,indent=2));print('Frozen grid: 64 entry configurations x 4 post-entry filters x 48 exit/risk combinations = 12288')
