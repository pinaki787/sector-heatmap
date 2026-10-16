"""Stage reviewed changes on downloaded hosted sources, preserving newer broker code."""
from pathlib import Path
import ast,shutil,json,hashlib,argparse
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',type=Path,default=root/'outputs/durable-jobs/baseline')
parser.add_argument('--account-only',action='store_true',help='Preserve an account snapshot that has no native Motilal routes.')
parser.add_argument('--output',type=Path,default=root/'outputs/durable-jobs/stage')
args=parser.parse_args()
base=args.baseline;stage=args.output;(stage/'sector_heatmap').mkdir(parents=True,exist_ok=True)
def read(name):return (root/name).read_text()
def save(name,text):
 p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
 if p.suffix=='.py':ast.parse(text)
for name in ('persistent_jobs','job_http','exposure_guard','handoff_ai','market_handoff'):
 save('sector_heatmap/'+name+'.py',read('sector_heatmap/'+name+'.py'))
# Add cooperative cancellation at existing broker-read boundaries.
hooks={
 'sector_service.py': [('        while cursor <= end:\n','        while cursor <= end:\n            checkpoint("Collecting "+symbol+" broker history chunk.")\n'),('        for timeframe in ("15m", "1h"):\n            try:','        for timeframe in ("15m", "1h"):\n            checkpoint("Collecting "+symbol+" "+timeframe+" history.")\n            try:'),('        try:\n            daily_source = self.provider.get(symbol, "daily")','        checkpoint("Collecting "+symbol+" daily history.")\n        try:\n            daily_source = self.provider.get(symbol, "daily")')],
 'dhan_sector_analysis.py': [('        while cursor < end:\n','        while cursor < end:\n            checkpoint("Collecting "+symbol+" Dhan history chunk.")\n')],
 'holdings_analysis.py': [('            for row in pending:\n','            for row in pending:\n                checkpoint("Reviewing holding "+row["symbol"]+".")\n')],
 'screener_routes.py': [('    for item in candidates:\n','    for item in candidates:\n        checkpoint("Checking stock-option evidence.")\n')],
 'motilal_shared_routes.py': [('        for ticker in page:\n','        for ticker in page:\n            checkpoint("Analyzing "+ticker+" with Motilal evidence.")\n')],
}
for name,pairs in hooks.items():
 if args.account_only and not (base/name).exists():continue
 s=(base/name).read_text()
 for old,new in pairs:
  assert old in s,(name,old);s=s.replace(old,new,1)
 tree=ast.parse(s);position=0
 for node in tree.body:
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str) or isinstance(node,ast.ImportFrom) and node.module=='__future__':position=node.end_lineno
  else:break
 lines=s.splitlines(keepends=True);lines.insert(position,'from .persistent_jobs import checkpoint\n')
 save('sector_heatmap/'+name,''.join(lines))
save('holdings-review.js',read('holdings-review.js'))
s=(base/'renko-batch.py').read_text()
old="row.update(status='STARTED',running=state['running'],mode=state['config']['mode'])"
new="row.update(status='STARTED',running=state['running'],mode=state['config']['mode'],run_id=state.get('run_id'),started_at=state.get('started_at'))"
assert old in s;s=s.replace(old,new,1);save('strategies/renko_supertrend/batch.py',s)
s=(base/'delta_india.py').read_text()
s=s.replace("self.runner={'running':True,'config':cfg","self.runner={'run_id':secrets.token_hex(16),'running':True,'config':cfg")
s=s.replace("self.runner.update(running=True,exit_only=False,config=cfg","self.runner.update(run_id=secrets.token_hex(16),running=True,exit_only=False,config=cfg")
anchor="    def stop_runner(self,payload=None):\n        with self.lock:\n"
assert anchor in s;s=s.replace(anchor,anchor+"            if (payload or {}).get('run_id') and payload['run_id']!=self.runner.get('run_id'):\n                raise ValueError('Runner changed; the replacement run was preserved.')\n",1)
save('sector_heatmap/delta_india.py',s)
s=(base/'ema-runner.py').read_text()
anchor="            if expected and expected != current.get('run_id'):\n                raise ValueError('Run changed. Refresh before stopping.')"
assert anchor in s;s=s.replace(anchor,anchor+"\n            if payload.get('started_at') is not None and payload['started_at'] != current.get('started_at'):\n                raise ValueError('Run changed. Refresh before stopping.')",1)
save('strategies/ema_crossover/runner.py',s)
s=(base/'sensex_straddle.py').read_text();i=s.index('    def stop(self):')
s=s[:i]+s[i:].replace('    def stop(self):','    def stop(self, expected_started_at=None):',1)
a=s.index('        with self.lock:',i)+len('        with self.lock:\n')
s=s[:a]+"            if expected_started_at is not None and expected_started_at != self.started_at:\n                raise ValueError('Runner changed; the replacement run was preserved.')\n"+s[a:]
anchor='        with self.lock:\n            self.last_exit_code = process.returncode';assert anchor in s
s=s.replace(anchor,'        with self.lock:\n            if self.process is not process:\n                return self.snapshot_unlocked("Previous runner stopped; replacement run preserved.")\n            self.last_exit_code = process.returncode',1)
save('sector_heatmap/sensex_straddle.py',s)
s=(base/'nifty_straddle.py').read_text();anchor='    def stop(self):\n        result = super().stop()';assert anchor in s
s=s.replace(anchor,'    def stop(self, expected_started_at=None):\n        result = super().stop(expected_started_at) if expected_started_at is not None else super().stop()',1)
save('sector_heatmap/nifty_straddle.py',s)
s=(base/'web.py').read_text();local=read('sector_heatmap/web.py')
a=local.index('    from .job_http import install as install_persistent_jobs');b=local.index('    server = ThreadingHTTPServer',a)
factory=local[a:b]
if args.account_only:
 x=factory.index("        if handler.path.startswith('/api/motilal/'):")
 y=factory.index('\n        if workspace_guard:\n',x)
 factory=factory[:x]+"        if handler.path.startswith('/api/motilal/'):\n            raise PermissionError('Open the native Motilal dashboard for this analysis.')\n"+factory[y:]
s=s.replace('    server = ThreadingHTTPServer',factory+'    server = ThreadingHTTPServer',1)
s=s.replace('    finally:\n        delta_india.monitoring_stop.set()','    finally:\n        persistent_jobs.close(wait=False)\n        delta_india.monitoring_stop.set()',1)
a=local.index('        from .exposure_guard import exclude_exposure',local.index('    def analysis_opportunities'));b=local.index('        level_plans = {}',a)
x=s.index('        position_exposures = open_position_underlyings',s.index('    def analysis_opportunities'));y=s.index('        level_plans = {}',x)
s=s[:x]+local[a:b]+s[y:]
for old,new in [('            for ticker in page:\n','            for ticker in page:\n                from .persistent_jobs import checkpoint\n                checkpoint("Analyzing "+ticker+" with selected-broker evidence.")\n'),('        for candidate in candidates:\n','        for candidate in candidates:\n            from .persistent_jobs import checkpoint\n            checkpoint("Building Handoff evidence for "+str(candidate.get("symbol") or candidate.get("name"))+".")\n')]:
 assert old in s;s=s.replace(old,new,1)
a=local.index('        from .persistent_jobs import checkpoint\n        from .exposure_guard import exclude_handoff_cards',local.index('    def analysis_opportunities'))
b=local.index('        analysis_id = secrets.token_urlsafe(12)',a)
anchor='        analysis_id = secrets.token_urlsafe(12)'
assert anchor in s;s=s.replace(anchor,local[a:b]+anchor,1)
for name,lock,state in [('ema','ema_runner_lock','ema_runner'),('kama','kama_runner_lock','kama_runner')]:
 old=f'    def stop_{name}_runner():\n        with {lock}:\n'
 new=f"    def stop_{name}_runner(expected_started_at=None):\n        with {lock}:\n            if expected_started_at is not None and {state}.get('run_started_at') != expected_started_at:\n                raise ValueError('Runner changed; the replacement run was preserved.')\n"
 assert old in s;s=s.replace(old,new,1)
save('sector_heatmap/web.py',s)
s=(base/'fyers_execution.py').read_text();local=read('sector_heatmap/fyers_execution.py')
s=s.replace('from .config import', 'from .exposure_guard import matches_exposure, open_exposures\nfrom .config import',1)
a=local.index("        if matches_exposure(payload.get('underlying')");b=local.index('        if enforce_risk_controls',a)
anchor='        if enforce_risk_controls and len(open_positions) >= max_positions:'
assert anchor in s;s=s.replace(anchor,local[a:b]+anchor,1);save('sector_heatmap/fyers_execution.py',s)
if not args.account_only:
 s=(base/'motilal_analysis.py').read_text();local=read('sector_heatmap/motilal_analysis.py');a=local.index('    def orders(self):',local.index('class Handoff:'));b=local.index('    def funds(self):',a)
 s=s.replace('    def funds(self):',local[a:b]+'    def funds(self):',1);save('sector_heatmap/motilal_analysis.py',s)
 s=(base/'motilal_shared_tickets.py').read_text();local=read('sector_heatmap/motilal_shared_tickets.py')
 # This file's downloaded baseline is verified against the earlier reviewed local implementation.
 original=local[0:local.index('    def exclude_duplicate')]+local[local.index('    def booked_loss'):]
 # Apply the same focused inserts to the remote version rather than copying local history.
 a=local.index('    def exclude_duplicate');b=local.index('    def booked_loss',a)
 s=s.replace('    def booked_loss',local[a:b]+'    def booked_loss',1)
 s=s.replace("                if symbol in symbols:raise ValueError('Duplicate native contract in batch.')","                underlying_key=meta['exchange'].removesuffix('FO')+':'+meta['underlying']\n                if underlying_key in symbols:raise ValueError('Duplicate native underlying in batch.')\n                symbols.add(underlying_key)\n                if symbol in symbols:raise ValueError('Duplicate native contract in batch.')",1)
 s=s.replace('                reviewed=self.execution.tickets.preview','                self.exclude_duplicate(symbol)\n                reviewed=self.execution.tickets.preview',1)
 s=s.replace('                    self.adapter.preflight(order,{})',"                    self.exclude_duplicate(item['symbol'])\n                    self.adapter.preflight(order,{})",1)
 save('sector_heatmap/motilal_shared_tickets.py',s)
s=(base/'dhan_handoff.py').read_text();anchor='    def funds(self):'
insert='''    def orders(self):
        rows=self.client.request('GET','/orders')
        if not isinstance(rows,list) or any(str(r.get('dhanClientId',self.client.client_id))!=self.client.client_id for r in rows):
            raise PermissionError('Dhan orders do not match selected account.')
        masters=self.execution.master.load(datetime.now(IST))
        lookup={(r['SEM_EXM_EXCH_ID']+{'E':'_EQ','D':'_FNO','M':'_COMM','I':''}.get(r['SEM_SEGMENT'],''),str(r['SEM_SMST_SECURITY_ID'])):r for r in masters}
        result=[]
        for row in rows:
            if row.get('orderStatus') in ('TRADED','CANCELLED','REJECTED','EXPIRED'):continue
            if row.get('orderStatus') not in ('TRANSIT','PENDING','PART_TRADED'):raise ValueError('Unknown Dhan order status; duplicate entry cannot be excluded.')
            meta=lookup.get((row.get('exchangeSegment'),str(row.get('securityId'))))
            if not meta:raise ValueError('Pending Dhan order has no verified native master mapping.')
            result.append(dict(symbol=meta['SEM_EXM_EXCH_ID']+':'+contract_underlying(meta)+'-EQ',status=row['orderStatus']))
        return result

'''
assert anchor in s;s=s.replace(anchor,insert+anchor,1);save('sector_heatmap/dhan_handoff.py',s)
s=(base/'section_permissions.py').read_text();anchor=" assigned=set(user.get('features',[]))";s=s.replace(anchor,anchor+"\n if path.startswith('/api/jobs'):return bool(assigned & {'broker','runner-jobs','handoff','screener','holdings','trade-parser','telegram-parser','renko-supertrend','ema-band','ema-cross','kama','delta-india','straddles','renko-engine'})",1);save('sector_heatmap/section_permissions.py',s)
s=(base/'dashboard-enhancements.js').read_text();local=read('dashboard-enhancements.js')
a=local.index('  const renderSavedScreenerAnalysis =');b=local.index('  const analyzeScreenerCandidates',a)
x=s.index('      const qualified = data.results.filter',s.index('  const analyzeScreenerCandidates'));y=s.index('      screenerAnalysisOffset += data.analyzed',x)
renderer='  const renderSavedScreenerAnalysis = (data, reset) => {\n'+s[x:y]+'  }\n'
s=s[:x]+'      renderSavedScreenerAnalysis(data, reset)\n'+s[y:]
s=s.replace('  const analyzeScreenerCandidates =',renderer+'  const analyzeScreenerCandidates =',1)
a=local.index('  const requestScreenerJobStop =');b=local.index('  const renderSavedScreenerAnalysis =',a)
s=s.replace('  const renderSavedScreenerAnalysis =',local[a:b]+'  const renderSavedScreenerAnalysis =',1)
s=s.replace('  let screenerAnalysisCancelled = false','  let screenerAnalysisCancelled = false\n  let screenerActiveJob = null, screenerStopSent = false',1)
anchor='      screenerAnalysisCancelled = false\n      syncScreenerCandidateSelectionUi()'
assert anchor in s;s=s.replace(anchor,'      screenerAnalysisCancelled = false\n      screenerActiveJob = null; screenerStopSent = false\n      syncScreenerCandidateSelectionUi()',1)
s=s.replace("  $('screener-analysis-next').textContent = 'Cancel analysis'","  $('screener-analysis-next').textContent = 'Stop analysis job'",1)
old="    $('screener-analysis-status').textContent = `Cancellation requested · finishing the current safe batch (${screenerAnalysisOffset} complete).`"
assert old in s;s=s.replace(old,"    $('screener-analysis-status').textContent = 'Stop requested; the server will retain partial analysis output.'\n    requestScreenerJobStop()",1)
s=s.replace('  const analyzeScreenerOptionPlans = async () => {\n','  const analyzeScreenerOptionPlans = async () => {\n    screenerAnalysisCancelled = false\n',1)

a=local.index("  window.addEventListener('sector-pulse-job-output'");b=local.index("  window.addEventListener('pagehide',saveHandoffResults)",a);anchor="  window.addEventListener('pagehide',saveHandoffResults)";assert anchor in s;s=s.replace(anchor,local[a:b]+anchor,1)
if args.account_only:s=s.replace("BrokerForms?.account('screener')","BrokerForms?.account('account')")
save('dashboard-enhancements.js',s)
s=(base/'workspaces.py').read_text()
anchor="            public=[]"
assert anchor in s
s=s.replace(anchor,"            inventory += ['analysis-jobs.js','market-handoff.js'] + ['sector_heatmap/'+name+'.py' for name in ['persistent_jobs','job_http','exposure_guard','handoff_ai','market_handoff']]\n"+anchor,1)
save('sector_heatmap/workspaces.py',s)
s=(base/'broker-form-routing.js').read_text()
old="const control=['manual','handoff'].includes(kind)?document.querySelector('.view.active .order-account'):document.getElementById(IDS[kind]);"
new="const control=kind==='handoff'?document.getElementById('ticket-broker'):kind==='manual'?document.querySelector('.view.active .order-account'):document.getElementById(IDS[kind]);"
assert old in s;s=s.replace(old,new,1);save('broker-form-routing.js',s)
s=(base/'index.html').read_text()
assert '</body>' in s,'Hosted dashboard closing body tag missing.'
for asset in ('analysis-jobs.js','market-handoff.js'):
    assert asset not in s,'Job assets already installed; refresh baseline before staging.'
s=s.replace('</body>','    <script src="/analysis-jobs.js?v=20261016-1"></script>\n    <script src="/market-handoff.js?v=20261016-1"></script>\n</body>',1)
assert s.count('/analysis-jobs.js?')==1 and s.count('/market-handoff.js?')==1
import re
for asset in ('holdings-review.js','dashboard-enhancements.js','broker-form-routing.js'):
 s=re.sub(re.escape(asset)+r'\?v=[^"\s]+',asset+'?v=20261016-durable-jobs-2',s)
save('index.html',s)
for name in ('analysis-jobs.js','market-handoff.js'):save(name,read(name))
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()};(stage/'baseline-sha256.json').write_text(json.dumps(manifest,indent=2))
print('Staged',len(list(stage.rglob('*.py'))),'Python modules and UI files on hosted baseline.')
