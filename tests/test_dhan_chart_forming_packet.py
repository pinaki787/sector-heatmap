import importlib.util,threading,unittest,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from sector_heatmap import chart_workspace as canonical
ROOT=Path(__file__).resolve().parents[1]
def modules():
 yield canonical
 manifest=ROOT/'.private/changes/execution-release-20261126/distribution.json'
 for owner in (json.loads(manifest.read_text()) if manifest.exists() else {}):
  p=ROOT/'.private/dashboard-login/accounts'/owner/'source/sector_heatmap/chart_workspace.py'
  spec=importlib.util.spec_from_file_location('sector_heatmap._dhan_forming_'+owner,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);yield m
class FormingPacket(unittest.TestCase):
 def test_small_selected_symbol_packet_keeps_cached_forming_ohlc_without_history(self):
  for m in modules():
   with self.subTest(module=m.__name__):
    bars=m.FyersChartBars();bars.latest=123;bars.latest_price=102;bars.coverage_since=60;bars.series={1:{120:[120,100,103,99,102,None]}}
    bars.snapshot=Mock(side_effect=AssertionError('No history snapshot on quote path'))
    stream=SimpleNamespace(subscribe=lambda symbol:bars,bars=bars,connected=True)
    symbol=None if 'legacy Dhan' in (m.DhanChartStream.quote_snapshot.__doc__ or '') else 'IDX_I:13'
    result=m.DhanChartStream.quote_snapshot(stream,symbol=symbol)
    self.assertEqual(result['rows'],[]);self.assertEqual(result['latest_price'],102)
    self.assertEqual(result['forming_row'],[120,100,103,99,102,None]);self.assertEqual(result['forming_frame'],1)
    self.assertLess(len(json.dumps(result)),600);bars.snapshot.assert_not_called()
    bars.coverage_since=121
    self.assertNotIn('forming_row',m.DhanChartStream.quote_snapshot(stream,symbol=symbol))
    stream.connected=False
    disconnected=m.DhanChartStream.quote_snapshot(stream,symbol=symbol)
    self.assertIsNone(disconnected['latest_price']);self.assertNotIn('forming_row',disconnected)
 def test_route_passes_small_packet_intent_and_exact_symbol_to_selected_dhan_stream(self):
  for m in modules():
   with self.subTest(module=m.__name__):
    frame=dict(symbol='MCX_COMM:575011',connected=True,latest_tick=123,latest_price=102,rows=[],forming_row=[120,100,103,99,102,None],forming_frame=1)
    try:m.requested_chart_symbol({'symbol':['MCX_COMM:575011']},'DHAN');supported=True
    except ValueError:supported=False
    callback=Mock(return_value=frame);h=SimpleNamespace(path='/api/chart-workspace/live?interval=5&symbol=MCX_COMM%3A575011&price_only=1',workspace_identity=({},dict(broker='DHAN')),send_json=Mock())
    with patch.object(m,'require_chart'):m.serve_live(h,None,SimpleNamespace(store=None),None,None,None,callback)
    if not supported:
     callback.assert_not_called();self.assertEqual(h.send_json.call_args.args[0],400);continue
    self.assertEqual(callback.call_args.kwargs,dict(symbol='MCX_COMM:575011',price_only=True))
    self.assertEqual(h.send_json.call_args.args[0],200);self.assertEqual(h.send_json.call_args.args[1]['forming_row'],frame['forming_row']);self.assertEqual(h.send_json.call_args.args[1]['rows'],[])

class DhanReconnectCoverage(unittest.TestCase):
 def test_reconnect_invalidates_old_forming_coverage_without_a_broker_request(self):
  import inspect
  for m in modules():
   with self.subTest(module=m.__name__):
    client=SimpleNamespace(client_id='fixture',headers={'access-token':'fixture'})
    with patch('threading.Thread'),patch('websocket.WebSocketApp') as socket:
     modern='symbol' in inspect.signature(m.DhanChartStream).parameters
     stream=m.DhanChartStream(client,symbol='IDX_I:13',account_id='fixture') if modern and 'account_id' in inspect.signature(m.DhanChartStream).parameters else m.DhanChartStream(client,symbol='IDX_I:13') if modern else m.DhanChartStream(client)
     bars=stream.subscribe('IDX_I:13') if modern else stream.bars
     bars.latest=123;bars.latest_price=100;bars.coverage_since=60;bars.series[1][120]=[120,100,101,99,100,None]
     socket.call_args.kwargs['on_open'](Mock())
     self.assertIsNone(bars.coverage_since);self.assertIsNone(bars.latest)
     packet=stream.quote_snapshot(symbol='IDX_I:13')
     self.assertNotIn('forming_row',packet);self.assertIsNone(packet['latest_price'])
