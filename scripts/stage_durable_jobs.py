"""Stage reviewed changes on downloaded hosted sources, preserving newer broker code."""
from pathlib import Path
import ast,shutil,json,hashlib
root=Path(__file__).resolve().parents[1]
base=root/'outputs/durable-jobs/baseline';stage=root/'outputs/durable-jobs/stage';(stage/'sector_heatmap').mkdir(parents=True,exist_ok=True)
def read(name):return (root/name).read_text()
def save(name,text):
 p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
 if p.suffix=='.py':ast.parse(text)
for name in ('persistent_jobs','job_http','exposure_guard','handoff_ai','market_handoff'):
 save('sector_heatmap/'+name+'.py',read('sector_heatmap/'+name+'.py'))
s=(base/'web.py').read_text();local=read('sector_heatmap/web.py')
a=local.index('    from .job_http import install as install_persistent_jobs');b=local.index('    server = ThreadingHTTPServer',a)
s=s.replace('    server = ThreadingHTTPServer',local[a:b]+'    server = ThreadingHTTPServer',1)
s=s.replace('    finally:\n        delta_india.monitoring_stop.set()','    finally:\n        persistent_jobs.close(wait=False)\n        delta_india.monitoring_stop.set()',1)
a=local.index('        from .exposure_guard import exclude_exposure',local.index('    def analysis_opportunities'));b=local.index('        level_plans = {}',a)
x=s.index('        position_exposures = open_position_underlyings',s.index('    def analysis_opportunities'));y=s.index('        level_plans = {}',x)
s=s[:x]+local[a:b]+s[y:];save('sector_heatmap/web.py',s)
s=(base/'fyers_execution.py').read_text();local=read('sector_heatmap/fyers_execution.py')
s=s.replace('from .config import', 'from .exposure_guard import matches_exposure, open_exposures\nfrom .config import',1)
a=local.index("        if matches_exposure(payload.get('underlying')");b=local.index('        if enforce_risk_controls',a)
anchor='        if enforce_risk_controls and len(open_positions) >= max_positions:'
assert anchor in s;s=s.replace(anchor,local[a:b]+anchor,1);save('sector_heatmap/fyers_execution.py',s)
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
s=(base/'section_permissions.py').read_text();anchor=" assigned=set(user.get('features',[]))";s=s.replace(anchor,anchor+"\n if path.startswith('/api/jobs'):return bool(assigned & {'runner-jobs','handoff','screener','holdings','trade-parser','telegram-parser','renko-supertrend','ema-band','ema-cross','kama','delta-india','straddles','renko-engine'})",1);save('sector_heatmap/section_permissions.py',s)
s=(base/'dashboard-enhancements.js').read_text();local=read('dashboard-enhancements.js')
a=local.index('  const renderSavedScreenerAnalysis =');b=local.index('  const analyzeScreenerCandidates',a)
x=s.index('      const qualified = data.results.filter',s.index('  const analyzeScreenerCandidates'));y=s.index('      screenerAnalysisOffset += data.analyzed',x)
s=s[:x]+'      renderSavedScreenerAnalysis(data, reset)\n'+s[y:]
s=s.replace('  const analyzeScreenerCandidates =',local[a:b]+'  const analyzeScreenerCandidates =',1)
a=local.index("  window.addEventListener('sector-pulse-job-output'");b=local.index("  window.addEventListener('pagehide',saveHandoffResults)",a);anchor="  window.addEventListener('pagehide',saveHandoffResults)";assert anchor in s;s=s.replace(anchor,local[a:b]+anchor,1);save('dashboard-enhancements.js',s)
s=(base/'workspaces.py').read_text()
anchor="            public=[]"
assert anchor in s
s=s.replace(anchor,"            inventory += ['analysis-jobs.js','market-handoff.js'] + ['sector_heatmap/'+name+'.py' for name in ['persistent_jobs','job_http','exposure_guard','handoff_ai','market_handoff']]\n"+anchor,1)
save('sector_heatmap/workspaces.py',s)
s=(base/'broker-form-routing.js').read_text()
old="const control=['manual','handoff'].includes(kind)?document.querySelector('.view.active .order-account'):document.getElementById(IDS[kind]);"
new="const control=kind==='handoff'?document.getElementById('ticket-broker'):kind==='manual'?document.querySelector('.view.active .order-account'):document.getElementById(IDS[kind]);"
assert old in s;s=s.replace(old,new,1);save('broker-form-routing.js',s)
s=(base/'index.html').read_text();s=s.replace('  </body>','    <script src="/analysis-jobs.js?v=20261016-1"></script>\n    <script src="/market-handoff.js?v=20261016-1"></script>\n  </body>');save('index.html',s)
for name in ('analysis-jobs.js','market-handoff.js'):save(name,read(name))
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file()};(stage/'baseline-sha256.json').write_text(json.dumps(manifest,indent=2))
print('Staged',len(list(stage.rglob('*.py'))),'Python modules and UI files on hosted baseline.')
