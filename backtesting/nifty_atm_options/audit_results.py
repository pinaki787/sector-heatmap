"""Offline consistency audit of prices, contract continuity and selection."""
import datetime,hashlib,json,collections
from pathlib import Path
from replay import load_quotes,fixed_quote,IST,LOT

folder=Path('backtesting/nifty_atm_options');output=folder/'full-grid'
data=json.loads((output/'results.json').read_text());grid=data['grid'];journals=json.loads((output/'journals.json').read_text())
assert len(data['results'])==12288
for name,digest in grid['frozen_source_hashes'].items():assert hashlib.sha256((folder/'frozen-source'/name).read_bytes()).hexdigest()==digest
assert hashlib.sha256((folder/'inputs/underlying.json').read_bytes()).hexdigest()==grid['source_sha256']
assert hashlib.sha256((folder/'inputs/config.json').read_bytes()).hexdigest()==grid['config_sha256']
valid=[r for r in data['results'] if r['valid']];eligible=sorted((r for r in valid if r['metrics']['development']['trades']>=30),key=lambda r:r['metrics']['development']['net'],reverse=True)
assert data['selected_on_development']==[r['id'] for r in eligible[:20]]
quotes,quality=load_quotes([folder/'cache']);assert quality==data['quality']
checked=0
for journal in journals:
 previous_exit=None;perday=collections.Counter()
 for period,trades in journal['trades'].items():
  assert journal['metrics'][period]['trades']==len(trades)
  assert abs(journal['metrics'][period]['net']-sum(t['net'] for t in trades))<1e-7
  for t in trades:
   entry=datetime.datetime.fromtimestamp(t['entry_at'],IST);exit=datetime.datetime.fromtimestamp(t['exit_at'],IST)
   assert entry.date()==exit.date() and exit.hour*60+exit.minute<=915
   assert t['entry_signal_at']<=t['entry_at']<t['exit_at'] and t['quantity']==LOT
   assert previous_exit is None or t['entry_at']>previous_exit
   assert str(entry.date()) in data['periods'][period]
   perday[str(entry.date())]+=1;assert perday[str(entry.date())]<=2
   for at in range(t['entry_at'],t['exit_at']+1,300):assert fixed_quote(quotes,at,t['side'],t['strike'],t['expected_expiry']) is not None
   buy=fixed_quote(quotes,t['entry_at'],t['side'],t['strike'],t['expected_expiry']);sell=fixed_quote(quotes,t['exit_at'],t['side'],t['strike'],t['expected_expiry'])
   assert abs(t['buy']-buy['buy'])<1e-9 and abs(t['sell']-sell['sell'])<1e-9
   assert abs(t['gross']-(t['sell']-t['buy'])*LOT)<1e-7
   assert abs(t['fees']-buy['buy_fee']-sell['sell_fee'])<1e-7
   assert abs(t['net']-t['gross']+t['fees'])<1e-7
   previous_exit=t['exit_at'];checked+=1
report=dict(status='PASS',configurations=len(data['results']),valid_configurations=len(valid),journals=len(journals),trades_checked=checked,missing_keys=len(data['missing_contract_keys']),quality=quality)
(output/'audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
