import json,os,signal,socket,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.workspace_supervisor import Supervisor,decide
from sector_heatmap.workspaces import WorkspaceRuntime

class DecisionTests(unittest.TestCase):
 def decision(self,**changes):
  return decide(**dict(dict(enabled=True,disconnected=False,owner_alive=False,port_busy=False,maintenance=False,attempts=[],now=100,next_attempt=0),**changes))
 def test_manual_and_maintenance_states_never_launch(self):
  for field,status in [('enabled','DISABLED'),('disconnected','DISCONNECTED'),('maintenance','MAINTENANCE')]:
   self.assertEqual(self.decision(**{field:field!='enabled'}),status)
 def test_existing_owner_or_occupied_port_never_duplicates(self):
  self.assertEqual(self.decision(owner_alive=True),'RUNNING');self.assertEqual(self.decision(port_busy=True),'BLOCKED_PORT_OCCUPIED')
 def test_persisted_backoff_and_crash_budget(self):
  self.assertEqual(self.decision(next_attempt=110),'BACKOFF')
  self.assertEqual(self.decision(attempts=[90,91,92,93,94]),'CIRCUIT_OPEN')
  self.assertEqual(self.decision(attempts=[90,91,92,93,94],now=2000),'RECOVER')

class ProcessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name);source=self.folder/'source';source.mkdir()
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
  script="""import os,json,socket,fcntl,time
from pathlib import Path
assert os.environ['DELTA_INDIA_ENABLE_LIVE_ORDERS']=='0'
assert os.environ['SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS']=='0'
assert os.environ['SECTOR_PULSE_DASHBOARD_RECOVERY_ONLY']=='1'
base=Path.cwd().parent
f=(base/'dashboard-owner.lock').open('a+')
fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
f.seek(0);f.truncate();json.dump({'pid':os.getpid()},f);f.flush()
s=socket.socket();s.bind(('127.0.0.1',int(os.environ['TEST_PORT'])));s.listen()
(base/'ready').write_text('read-only')
while True:time.sleep(.1)
"""
  (source/'heatmap_server.py').write_text(script)
  self.s=object.__new__(Supervisor);self.s.folder=self.folder;self.s.aid='test';self.s.clock=time.time
  self.s.account=dict(id='test',port=self.port);self.s.config=self.folder/'config.json';self.s.status=self.folder/'status.json';self.s.events=self.folder/'events.jsonl'
  self.s.config.write_text(json.dumps({'enabled':True}));self.s.store=type('Store',(),{'folder':lambda _,account:self.folder,'path':self.folder/'registry'})()
  self.s.runtime=WorkspaceRuntime(self.s.store,source,8080);self.children=[];self.addCleanup(self.cleanup)
 def cleanup(self):
  for pid in self.children:
   try:os.kill(pid,signal.SIGTERM)
   except ProcessLookupError:pass
  child=getattr(self.s,'child',None)
  if child:child.wait(timeout=3)
 def launch(self):
  with patch('sector_heatmap.workspace_supervisor.isolated_environment',return_value={**os.environ,'TEST_PORT':str(self.port)}):r=self.s.tick()
  if r.get('launched_pid'):self.children.append(r['launched_pid'])
  return r
 def wait_ready(self):
  end=time.monotonic()+5
  while not (self.folder/'ready').exists():
   if time.monotonic()>end:self.fail('Isolated recovery failed')
   time.sleep(.02)
 def test_dead_process_recovers_once_with_live_disabled(self):
  first=self.launch();self.assertEqual(first['status'],'RECOVERING_READ_ONLY');self.wait_ready()
  second=self.launch();self.assertEqual(second['status'],'RUNNING');self.assertEqual(len(second['attempts']),1)
  self.assertEqual((self.folder/'ready').read_text(),'read-only')
 def test_disconnect_and_saved_exposure_untouched(self):
  (self.folder/'disconnected.json').write_text('{}');p=self.folder/'runner.json';p.write_text('{"running":false,"position":{"id":"owned"}}')
  self.assertEqual(self.launch()['status'],'DISCONNECTED');self.assertEqual(p.read_text(),'{"running":false,"position":{"id":"owned"}}')
 def test_crashed_child_does_not_restart_during_backoff(self):
  first=self.launch();self.wait_ready();os.kill(first['launched_pid'],signal.SIGKILL)
  end=time.monotonic()+3
  while self.s.runtime.running('test') and time.monotonic()<end:time.sleep(.02)
  self.assertEqual(self.launch()['status'],'BACKOFF');self.assertEqual(len(json.loads(self.s.status.read_text())['attempts']),1)

if __name__=='__main__':unittest.main()
