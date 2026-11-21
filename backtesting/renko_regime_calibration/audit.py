import csv,json,hashlib
from pathlib import Path
from grid import gate
from adx_candidate import assess
from run import initialize,run_trial,HERE
import run as calibration
from strategies.renko_supertrend.signals import Engine
initialize()
engine=Engine(dict(calibration.CONFIG,manual_brick=27.71),.05);history=[];mismatch=0;checked=0
for r in calibration.RAW:
 sig=engine.update(r);history=(history+[sig])[-100:]
 direction='BULLISH' if sig['pine_direction']<0 else 'BEARISH'
 expected=gate(history,'adx_60',direction)
 actual=assess(history,direction,r['timestamp']+300)['allowed']
 checked+=1;mismatch+=expected!=actual
opens={int(x['epoch']):float(x['open']) for x in csv.DictReader((calibration.lifecycle.ARCHIVE/'nifty50_1m.csv').open())}
points={}
for name in ('Baseline','adx_60'):
 for t in json.loads((HERE/'trials'/f'{name}.json').read_text())['trades']:
  points[(t['entry_at'],t['entry_price'])]=1;points[(t['exit_at'],t['exit_price'])]=1
missing=sum(at not in opens for at,p in points)
differences=[abs(p-opens[at]) for at,p in points if at in opens]
result=dict(paper_gate_bars_checked=checked,paper_gate_grid_mismatches=mismatch,
 modeled_open_observations=len(points),missing_1m_timestamps=missing,
 max_open_difference=max(differences,default=0),
 archive_5m_sha256=hashlib.sha256((calibration.lifecycle.ARCHIVE/'nifty50_5m.csv').read_bytes()).hexdigest(),
 scope='Research-gate parity and archive candle-open consistency only; not live/broker/fill verification')
(HERE/'audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if mismatch or missing or max(differences,default=0)>.050001:raise SystemExit('Audit failed')
