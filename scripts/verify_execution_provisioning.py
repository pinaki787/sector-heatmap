"""Exercise public provisioning in an isolated directory; never opens an account."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import hashlib,json
from sector_heatmap.workspaces import WorkspaceRuntime
root=Path.cwd()
case=root/'.private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119'
entries=[
 ('strategies/ema_crossover/broker.py',root/'.private/chart-order-rollouts/fyers-master-memory-20261119/broker.candidate.py'),
 ('strategies/renko_supertrend/confirmed_feed.py',case/'confirmed_feed.candidate.py'),
 ('strategies/renko_supertrend/price_basis.py',case/'price_basis.candidate.py'),
 ('strategies/renko_supertrend/option_premium.py',case/'option_premium.candidate.py')]
with TemporaryDirectory(prefix='execution-provision-') as temp:
 t=Path(temp);source=t/'canonical';source.mkdir();(source/'.git').mkdir()
 account=t/'account';(account/'source').mkdir(parents=True)
 journal=account/'source/.private/journal.json';journal.parent.mkdir();journal.write_text('{"sentinel":"retain"}')
 for name,candidate in entries:
  p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((root/name).read_bytes())
  p=account/'source'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('old fixture')
 runtime=WorkspaceRuntime(SimpleNamespace(folder=lambda a:account),source)
 with patch('sector_heatmap.workspaces.subprocess.check_output',return_value=('\0'.join(n for n,_ in entries)+'\0').encode()):
  runtime.provision({'id':'isolated-fixture','broker':'FYERS'})
  runtime.provision({'id':'isolated-fixture','broker':'FYERS'})
 overlay=json.loads((account/'public-source-overlay.json').read_text())
 for name,candidate in entries:
  assert (account/'source'/name).read_bytes()==candidate.read_bytes()
  assert next(e['sha256'] for e in overlay if e['path']==name)==hashlib.sha256(candidate.read_bytes()).hexdigest()
 assert journal.read_text()=='{"sentinel":"retain"}'
report={'passed':True,'files':4,'provision_passes':2,'journal_preserved':True,'live_account_used':False}
(case/'canonical-provision-fixture.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
