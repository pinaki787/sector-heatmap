import importlib.util,threading,unittest,inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from sector_heatmap import chart_workspace as canonical
ROOT=Path(__file__).resolve().parents[1]
class NoHistory(dict):
    def __iter__(self):raise AssertionError('quote path traversed candle cache')
    def items(self):raise AssertionError('quote path traversed candle cache')
    def values(self):raise AssertionError('quote path traversed candle cache')
    def __getitem__(self,key):raise AssertionError('quote path read candle cache')
def modules():
    yield canonical
    for owner in ['a6ef4c9bcecd21d54c4a07e2b9b137a7','bf46fc364b610a0dfd338419e133cb41']:
        path=ROOT/'.private/dashboard-login/accounts'/owner/'source/sector_heatmap/chart_workspace.py'
        if path.exists():
            spec=importlib.util.spec_from_file_location('sector_heatmap._quote_'+owner,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);yield module
class QuoteFastPathTests(unittest.TestCase):
    def test_delta_reads_only_exact_cached_tick_without_candle_traversal(self):
        for module in modules():
            stream=SimpleNamespace(lock=threading.RLock(),connected=True,ticks={'ETHUSD':dict(symbol='ETHUSD',ltp=100,exch_feed_time=123)},forming_bars=NoHistory())
            result=module.delta_live_snapshot(stream,5,symbol='ETHUSD',price_only=True)
            self.assertEqual(result['latest_price'],100);self.assertEqual(result['latest_tick'],123);self.assertEqual(result['rows'],[])
            self.assertIsNone(module.delta_live_snapshot(stream,5,symbol='BTCUSD',price_only=True)['latest_price'])
            stream.connected=False;self.assertIsNone(module.delta_live_snapshot(stream,5,symbol='ETHUSD',price_only=True)['latest_price'])
    def test_fyers_retains_session_bounds_without_reading_candle_series(self):
        for module in modules():
            modern='mcx_bounds' in inspect.signature(module.FyersChartBars).parameters
            bars=module.FyersChartBars('MCX:GOLDM26DECFUT',mcx_bounds=lambda stamp:(540,1430)) if modern else module.FyersChartBars()
            bars.series=NoHistory();bars.latest=123;bars.latest_price=456
            result=bars.quote_snapshot(True)
            self.assertEqual(result['latest_price'],456);self.assertEqual(result['session_bounds'],(540,1430) if modern else None);self.assertEqual(result['rows'],[])
            self.assertIsNone(bars.quote_snapshot(False)['latest_price'])
    def test_authenticated_delta_route_passes_quote_intent_to_snapshot(self):
        for module in modules():
            handler=SimpleNamespace(path='/api/chart-workspace/live?interval=5&symbol=ETHUSD&price_only=1',workspace_identity=({},dict(broker='DELTA_INDIA')),send_json=Mock())
            callback=Mock(return_value=dict(symbol='ETHUSD',connected=True,latest_tick=123,latest_price=100))
            with patch.object(module,'require_chart'):
                module.serve_live(handler,None,SimpleNamespace(store=None),None,None,callback)
            self.assertTrue(callback.call_args.kwargs['price_only']);self.assertEqual(handler.send_json.call_args.args[0],200)
