"""Credential-free, network-isolated startup probe of an installed release."""
import json,os,subprocess,sys,tempfile,time,urllib.request,socket
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
with socket.socket() as probe:
    probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
child_code='''
import urllib.request,requests
from unittest.mock import patch
import sector_heatmap.config as config
config.load_config=lambda:{}
import sector_heatmap.web as web
web.load_config=lambda:{}
def blocked(*a,**k):raise requests.ConnectionError('External HTTP disabled during installation smoke test')
with patch('urllib.request.urlopen',blocked),patch('requests.sessions.Session.request',blocked):web.run_server()
'''
env={**os.environ,'HEATMAP_PORT':str(port),'FYERS_ACCESS_TOKEN':'','FYERS_APP_ID':'','FYERS_SECRET_KEY':'','SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS':'0','SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS':'0'}
with tempfile.TemporaryFile() as log:
    process=subprocess.Popen([sys.executable,'-c',child_code],cwd=root,env=env,stdout=log,stderr=log)
    try:
        for _ in range(100):
            if process.poll() is not None:
                log.seek(0);raise RuntimeError(log.read().decode())
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/renko-instances',timeout=1) as response:result=json.load(response)
                break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('Startup did not become ready')
        assert all(not r.get('running') and not r.get('position') and not r.get('pending') for r in result['instances'])
        fy=next(r for r in result['instances'] if r['id']=='FYERS:default')
        assert fy['runtime_revision']=='renko-supertrend-rsi-slope-v13'
        for path in ['/','/renko-supertrend.js','/renko-assessment.js','/vendor/lightweight-charts-4.2.3.js']:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=2) as response:assert response.status==200
        from strategies.renko_supertrend.signals import settings
        assert settings({})['rsi_slope_enabled'] is True
        print('Installed server HTTP smoke passed; all instances stopped/flat, v13 loaded, UI assets served, default RSI ON. External HTTP blocked, no credentials or orders.')
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()
