"""Read-only exact-account chart marker evidence; no strategy/order mutation."""
import runpy,json,secrets,hashlib,time,urllib.request,urllib.parse
from pathlib import Path
ctx=runpy.run_path('/home/trading/sector-heatmap/scripts/activate_swing_breakout_fyers_20261103.py')
store,actor,account,STATE=map(ctx.get,('store','actor','account','STATE'))
s=json.loads(STATE.read_text());config=s['config'];token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
with store.db() as db:db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest,actor['id'],secrets.token_urlsafe(32),time.time()+180))
try:
 prefs=json.loads(STATE.with_name('renko-supertrend-settings.json').read_text())['settings']
 # Use actual chart-only settings translation, preserving UI selection evidence.
 import subprocess
 code="const fs=require('fs'),m=require('./renko-supertrend.js');const f=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(m.chartSettings(f)))"
 raw=subprocess.check_output(['node','-e',code],input=json.dumps(prefs).encode(),cwd=ctx['SOURCE'])
 chart_settings=json.loads(raw);query={**chart_settings,'symbol':config['underlying'],'timeframe':config['timeframe'],'history_preset':'45','live_price_chart':True,'instance':ctx['INSTANCE']}
 query={k:str(v).lower() if isinstance(v,bool) else v for k,v in query.items()}
 url='http://127.0.0.1:'+str(account['port'])+'/api/renko-supertrend/chart?'+urllib.parse.urlencode(query)
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Cookie':'sector_pulse_session='+token}),timeout=120) as r:data=json.load(r)
 out=ctx['ROOT']/'.private/chart-label-audit-20261103';out.mkdir(mode=0o700,exist_ok=True)
 (out/'chart-response.json').write_text(json.dumps(data));(out/'chart-response.json').chmod(0o600)
 (out/'runner-config.json').write_text(json.dumps(config));(out/'runner-config.json').chmod(0o600)
 events=[b for r in data['rows'] for b in (r.get('brick_events') or [r]) if b.get('lifecycle_event')]
 print(json.dumps({'settings_differences':{k:[config.get(k),v] for k,v in data['settings'].items() if k in config and config[k]!=v},'runner_running':s.get('running'),'runner_position':bool(s.get('position')),'runner_pending':bool(s.get('pending')),'events':[{k:b.get(k) for k in ('timestamp','close','lifecycle_event','lifecycle_reason','entry_qualified','entry_direction','entry_diagnostic','direction','brick_direction','swing_breakout','supertrend_slope_filter')} for b in events[-12:]]},indent=2))
finally:
 with store.db() as db:db.execute('DELETE FROM sessions WHERE digest=?',(digest,))
