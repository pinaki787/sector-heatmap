"""Execute real GET handler code without starting a server or trading runner."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs,urlparse
import unittest

class SnapshotScope(unittest.TestCase):
 def handler(self,path):
  tree=ast.parse(Path("sector_heatmap/web.py").read_text())
  get=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="do_GET")
  scope=dict(local_auth=None,workspace_guard=None,
    renko_default_bundle=(None,)*9,delta_default_service=SimpleNamespace(get=lambda *args:False),
    parse_qs=parse_qs,urlparse=urlparse,json=json,
    snapshot=lambda:dict(sectors=[dict(sector_id="pharma",drivers=[dict(ticker="TEST")],attribution={})]),
    state=dict(sector_analysis=SimpleNamespace(snapshot=lambda **kw:dict(sector=dict(sector_id=kw["sector_id"],name="Pharma",timeframe_states={})))))
  exec(compile(ast.Module(body=[get],type_ignores=[]),"GET-handler","exec"),scope)
  result={}
  handler=SimpleNamespace(path=path,send_json=lambda status,value:result.update(status=status,value=value))
  scope["do_GET"](handler)
  return result
 def test_detail_retains_market_snapshot_instead_of_telemetry_local(self):
  result=self.handler("/api/sector-analysis/detail?mode=intraday&sector=pharma")
  self.assertEqual(result["status"],200)
  self.assertEqual(result["value"]["sector"]["constituent_movers"],[dict(ticker="TEST")])
 def test_resource_import_has_distinct_binding(self):
  tree=ast.parse(Path("sector_heatmap/web.py").read_text())
  get=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="do_GET")
  imports=[a.asname or a.name for n in ast.walk(get) if isinstance(n,ast.ImportFrom) for a in n.names]
  self.assertNotIn("snapshot",imports)
  self.assertIn("resource_snapshot",imports)
