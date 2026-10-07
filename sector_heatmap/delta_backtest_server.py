"""Loopback-only public-data research worker, independent of broker runners."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import argparse, json, requests
from .delta_backtest import DeltaBacktest


def public_read(path, params=None):
    # Only public history and exact supported underlying metadata are reachable.
    if path not in ('/v2/history/candles','/v2/products/BTCUSD','/v2/products/ETHUSD'):
        raise ValueError('Research worker accepts only public underlying candles and metadata.')
    response=requests.get('https://api.india.delta.exchange'+path,params=params,headers={'Accept':'application/json','User-Agent':'SectorPulse-DeltaResearch/1.0'},timeout=15,allow_redirects=False)
    if response.status_code!=200:raise ValueError(f'Delta public history unavailable (HTTP {response.status_code}); retry later.')
    result=response.json()
    if not isinstance(result,dict) or result.get('success') is not True:raise ValueError('Delta public history request rejected; no metrics produced.')
    return result


def public_metadata(symbol):
    if symbol not in ('BTCUSD','ETHUSD'):raise ValueError('Choose a supported research underlying.')
    r=public_read('/v2/products/'+symbol)['result']
    if r.get('symbol')!=symbol or r.get('state')!='live' or r.get('trading_status')!='operational':raise ValueError('Underlying contract identity is unavailable.')
    return {k:r.get(k) for k in ('id','symbol','contract_type','contract_value','contract_unit_currency','notional_type','is_quanto','tick_size')}|{'underlying':(r.get('underlying_asset') or {}).get('symbol'),'quoting_currency':(r.get('quoting_asset') or {}).get('symbol'),'settlement_currency':(r.get('settling_asset') or {}).get('symbol')}


def handler(service,agent=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def permitted(self):
            return (self.headers.get('Host') or '').split(':')[0] in ('localhost','127.0.0.1') and (not self.headers.get('Origin') or self.headers['Origin'] in ('http://localhost:8080','http://127.0.0.1:8080'))
        def send_json(self,status,data):
            body=json.dumps(data,allow_nan=False).encode();self.send_response(status)
            origin=self.headers.get('Origin')
            if origin in ('http://localhost:8080','http://127.0.0.1:8080'):self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
            self.send_header('X-SectorPulse-Research','delta-public-v1');self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_OPTIONS(self):
            if not self.permitted():self.send_json(403,dict(error='Research access is restricted to the local dashboard.'));return
            self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.headers.get('Origin','http://127.0.0.1:8080'));self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.send_header('Vary','Origin');self.end_headers()
        def do_GET(self):
            try:
                if not self.permitted():raise PermissionError('Research access is restricted to the local dashboard.')
                parsed=urlparse(self.path)
                if parsed.path=='/api/delta-india/agent/status' and agent is not None:result=agent.status()
                elif parsed.path=='/api/delta-india/agent/proposal' and agent is not None:result=agent.proposal((parse_qs(parsed.query).get('id') or [''])[0])
                elif parsed.path=='/api/delta-india/backtest/status':result=service.status()
                elif parsed.path=='/api/delta-india/backtest/detail':result=service.detail((parse_qs(parsed.query).get('id') or [''])[0])
                else:raise ValueError('Unknown research route.')
                self.send_json(200,result)
            except Exception as error:self.send_json(409,dict(error=str(error)))
        def do_POST(self):
            try:
                if not self.permitted():raise PermissionError('Research access is restricted to the local dashboard.')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32768:raise ValueError('Research settings must fit 32 KiB.')
                payload=json.loads(self.rfile.read(length))
                if self.path.startswith('/api/delta-india/agent/') and agent is not None:
                    actions={'config':agent.configure,'run':agent.run,'start-loop':agent.start_loop,'stop-loop':agent.stop_loop,'cancel':agent.cancel,'add-proposals':agent.add_proposals,'holdout-once':agent.holdout_once}
                    action=actions.get(self.path.rsplit('/',1)[-1])
                    if action is None:raise ValueError('Unknown adaptive research action.')
                    if self.path.endswith(('/run','/start-loop','/holdout-once')) and service.status()['state'] in ('FETCHING','RUNNING'):raise ValueError('Wait for the current grid backtest before adaptive research.')
                    self.send_json(200,action(payload));return
                if agent is not None and self.path.endswith('/backtest/start') and agent.status()['job']['state'] in ('FETCHING','RUNNING','REVIEWING'):raise ValueError('Wait for adaptive research before a grid backtest.')
                actions={'/api/delta-india/backtest/plan':service.inspect,'/api/delta-india/backtest/start':service.start,'/api/delta-india/backtest/cancel':service.cancel}
                action=actions.get(self.path)
                if action is None:raise ValueError('Unknown research action.')
                self.send_json(200,action(payload))
            except Exception as error:self.send_json(409,dict(error=str(error)))
    return Handler


def main():
    parser=argparse.ArgumentParser(description='Delta public-data-only backtest worker');parser.add_argument('--port',type=int,default=8086);args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent/'.private'/'delta-backtest'
    service=DeltaBacktest(root,public_read,public_metadata)
    # Manual-only worker: adaptive code/history remains recoverable, but no AI or scheduler is instantiated.
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(service))
    print(f'Delta research worker listening on 127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    finally:service.cancel();server.server_close()



def ensure_research_worker():
    """Start/reuse the isolated worker on normal app launch, without restarting brokers."""
    import os, subprocess, sys
    root=Path(__file__).resolve().parent.parent
    try:
        response=requests.get('http://127.0.0.1:8086/api/delta-india/backtest/status',timeout=2)
        if response.headers.get('X-SectorPulse-Research')!='delta-public-v1':
            return 'Port 8086 is occupied by another service; research worker not started.'
        return 'Delta public research worker already running.'
    except requests.ConnectionError:
        output=root/'output';output.mkdir(exist_ok=True)
        with (output/'delta-backtest-worker.log').open('ab') as log:
            subprocess.Popen([sys.executable,'-u','-m','sector_heatmap.delta_backtest_server'],cwd=str(root),stdout=log,stderr=log,start_new_session=True,env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL','TMPDIR','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')})
        return 'Delta public research worker launched independently.'
    except requests.RequestException:
        return 'Delta research worker did not respond; no broker process restarted.'

if __name__=='__main__':main()
