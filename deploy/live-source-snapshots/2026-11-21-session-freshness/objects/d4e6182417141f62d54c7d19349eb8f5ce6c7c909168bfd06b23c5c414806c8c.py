"""Exercise the real persistent-job HTTP boundary without broker or AI calls."""
import json,threading,time,tempfile,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from sector_heatmap.job_http import install
class Settings:
 visible=True
 def sidebar_visibility(self):return {'investment':self.visible}
class Auth:
 def __init__(self):self.store=Settings()
 def check(self,handler,mutation=False):return True
 def authorize(self,headers,mutation=False):
  return {'id':headers.get('X-Test-Owner','owner'),'admin':False,'features':[] if headers.get('X-Test-Deny') else ['investment']}
class Handler(BaseHTTPRequestHandler):
 def read_json(self):return json.loads(self.rfile.read(int(self.headers['Content-Length'])))
 def send_json(self,status,value):
  body=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
 def do_GET(self):self.send_json(404,{})
 def do_POST(self):self.send_json(404,{})
 def log_message(self,*args):pass
class InvestmentHTTPTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.auth=Auth()
  class PrivateHandler(Handler):pass
  self.store=install(PrivateHandler,Path(self.tmp.name),local_auth=self.auth)
  self.server=ThreadingHTTPServer(('127.0.0.1',0),PrivateHandler)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.base='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.store.close();self.tmp.cleanup()
 def request(self,path,payload=None,headers=None):
  req=Request(self.base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
  try:
   with urlopen(req) as r:return r.status,json.load(r)
  except HTTPError as r:return r.code,json.load(r)
 def test_permission_and_visibility(self):
  self.assertEqual(self.request('/api/investment/analyze',{}, {'X-Test-Deny':'1'})[0],403)
  self.auth.store.visible=False
  self.assertEqual(self.request('/api/investment/analyze',{})[0],403)
 def test_saved_owner_scoped_output(self):
  with patch('sector_heatmap.investment.analyze',return_value={'schema':'investment/v1','rows':[]}):
   status,accepted=self.request('/api/investment/analyze',{})
   self.assertEqual(status,202);job_id=accepted['job_id']
   for _ in range(100):
    status,job=self.request('/api/jobs?job_id='+job_id)
    if job.get('terminal'):break
    time.sleep(.01)
   self.assertEqual(job['status'],'COMPLETED');self.assertEqual(job['output']['schema'],'investment/v1')
   self.assertEqual(self.request('/api/jobs?job_id='+job_id,headers={'X-Test-Owner':'other'})[0],403)
   self.assertEqual(self.request('/api/jobs?job_id='+job_id,headers={'X-Test-Deny':'1'})[0],403)
if __name__=='__main__':unittest.main()

