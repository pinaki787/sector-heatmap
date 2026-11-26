"""Exercise the actual maintained GET route blocks without a broker request."""
import json,unittest,textwrap
from pathlib import Path
from urllib.parse import parse_qs,urlparse
ROOT=Path(__file__).resolve().parents[2]
class DashboardAiRoutes(unittest.TestCase):
 def test_maintained_search_dispatch_keeps_query_market_and_direct_route(self):
  manifest=ROOT/'.private/changes/execution-release-20261126/distribution.json'
  owners=json.loads(manifest.read_text()) if manifest.exists() else {}
  paths=[ROOT/'sector_heatmap/web.py']+[ROOT/'.private/dashboard-login/accounts'/o/'source/sector_heatmap/web.py' for o in owners]
  for path in paths:
   with self.subTest(source=str(path)):
    source=path.read_text();marker="            if path == '/api/renko-supertrend/ai-options/search':"
    begin=source.index(marker);end=source.index("            if path ==",begin+len(marker))
    body=textwrap.dedent(source[begin:end]);calls=[]
    class Service:
     def search(self,*args):calls.append(args);return {'matches':[]}
    class Handler:
     path='/api/renko-supertrend/ai-options/search?q=GOLDM&market=MCX&route=DIRECT'
     def send_json(self,status,value):self.result=(status,value)
    ns=dict(parse_qs=parse_qs,urlparse=urlparse,workspace_guard=False,renko_supertrend=object(),ai_options_service=lambda _:Service())
    exec('def dispatch(self,path):\n'+textwrap.indent(body,' '),ns)
    handler=Handler();ns['dispatch'](handler,'/api/renko-supertrend/ai-options/search')
    self.assertEqual(calls,[('GOLDM','MCX','DIRECT')]);self.assertEqual(handler.result,(200,{'matches':[]}))
