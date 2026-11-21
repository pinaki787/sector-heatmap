from pathlib import Path
import os,shutil,subprocess,time,hashlib,json,re
root=Path.cwd();account=root/'.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/source'
stage=root/'.private'/('confirmed-feed-candidate-'+str(int(time.time())));stage.mkdir(mode=0o700)
files=['strategies/renko_supertrend/runner.py','strategies/renko_supertrend/stream.py','strategies/renko_supertrend/chart_history.py','sector_heatmap/chart_feed_recovery.py','sector_heatmap/web.py','renko-supertrend.js','index.html']
before={}
for name in files:
 p=account/name;before[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
assert before['strategies/renko_supertrend/runner.py']==hashlib.sha256((root/'.private/confirmed-feed-backup-1792679287/strategies/renko_supertrend/runner.py').read_bytes()).hexdigest()
os.chdir(stage)
for name in ['implement_confirmed_feed.py','finish_confirmed_feed.py','wire_confirmed_feed_health.py','optimize_confirmed_feed.py']:
 source=(root/'scripts'/name).read_text().replace("root=Path('/home/trading/sector-heatmap')",f"root=Path({str(stage)!r})")
 source=source.replace("def edit(name,changes):\n","def edit(name,changes):\n if name=='strategies/renko_supertrend/confirmed_feed.py':return\n")
 source=source.replace("def edit(name,old,new):\n","def edit(name,old,new):\n if name=='strategies/renko_supertrend/confirmed_feed.py':return\n")
 exec(compile(source,name,'exec'),{'__name__':'__main__'})
# The remaining reviewed changes are the old-price-history digest and the
# atomic source-revision / stale-preview guards tested after these patches.
shutil.copy2(root/'strategies/renko_supertrend/runner.py',stage/'strategies/renko_supertrend/runner.py')
shutil.copy2(root/'strategies/renko_supertrend/confirmed_feed.py',stage/'strategies/renko_supertrend/confirmed_feed.py')
def change(name,old,new):
 p=stage/name;s=p.read_text();assert s.count(old)==1,(name,old[:60],s.count(old));p.write_text(s.replace(old,new,1))
change('strategies/renko_supertrend/stream.py',"if fetcher and getattr(fetcher, '_renko_shared_pipeline', False):","if fetcher and getattr(fetcher, '_renko_shared_pipeline', False) is True and config.get('timeframe'):")
change('strategies/renko_supertrend/chart_history.py'," or retry_forming\n"," or retry_forming or bool(self.tail_provider and entry.get('complete') and last==datetime.fromtimestamp(now,IST).date())\n")
change('strategies/renko_supertrend/chart_history.py',"                            shared=self.tail_provider(symbol,timeframe)\n","                            shared=self.tail_provider(symbol,timeframe)\n                            entry['deferred_completed']={r['timestamp'] for r in shared if r.get('is_forming') and r['timestamp']+seconds<=now}\n")
change('strategies/renko_supertrend/chart_history.py',"is_forming=int(r[0])+seconds>now)","is_forming=int(r[0])+seconds>now or int(r[0]) in entry.get('deferred_completed',set()))")
change('renko-supertrend.js',"line.setData([]);fiveMinuteLine?.setData([]);","line.setData([]);liveSupertrendLine?.setData([]);fiveMinuteLine?.setData([]);")
change('renko-supertrend.js',"settings.confirmed_run_id=state.run_id;","settings.confirmed_run_id=state.confirmed_feed_revision==='shared-confirmed-live-v1'?state.run_id:'';")
change('renko-supertrend.js',"confirmed.revision!==confirmedRevision){const previous","confirmed.revision!==confirmedRevision&&!busy){const previous")
change('renko-supertrend.js',"preview.timestamp>base.timestamp&&Number.isFinite(preview.supertrend)","preview.timestamp===base.timestamp+d.bar_seconds&&Number.isFinite(preview.supertrend)")
change('renko-supertrend.js',"chartParity=runnerChartAlignment(context,lastRunner,d);paintChartBasis();","chartParity=runnerChartAlignment(context,lastRunner,d);confirmedRevision=d.confirmed_source?.revision||confirmedRevision;paintChartBasis();")
exec(compile((root/'scripts/bind_runner_chart_source.py').read_text(),'bind_runner_chart_source.py','exec'),{'__name__':'__main__'})
p=stage/'index.html';s=p.read_text();s,n=re.subn(r'/renko-supertrend.js\?v=[^"\s]+','/renko-supertrend.js?v=20261022-shared-confirmed-1',s);assert n==1;p.write_text(s)
files.append('strategies/renko_supertrend/confirmed_feed.py')
for name in files:
 p=stage/name
 if p.suffix=='.py':compile(p.read_bytes(),str(p),'exec')
 if p.suffix=='.js':subprocess.run(['node','--check',str(p)],check=True)
# Reviewed package and per-file source guards; installation is a separate step.
(stage/'manifest.json').write_text(json.dumps(dict(account=str(account),before=before,files=files),indent=2))
print(json.dumps({'candidate':str(stage),'files':len(files)}))
