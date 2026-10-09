import unittest
from unittest.mock import patch,Mock
import requests
from fyers_apiv3 import fyersModel
from sector_heatmap.fyers_history import history

class HistoryTests(unittest.TestCase):
    def test_sdk_history_uses_bounded_read_without_orders(self):
        client=fyersModel.FyersModel(client_id='test',token='test')
        response=Mock();response.json.return_value={'s':'ok','candles':[]}
        with patch('sector_heatmap.fyers_history.requests.get',return_value=response) as get:
            self.assertEqual(history(client,{'symbol':'BSE:SENSEX-INDEX'})['s'],'ok')
            self.assertEqual(get.call_args.kwargs['timeout'],(3,10))
    def test_timeout_is_recoverable_and_does_not_retry_inline(self):
        with patch('sector_heatmap.fyers_history.requests.get',side_effect=requests.Timeout()) as get:
            with self.assertRaisesRegex(RuntimeError,'timed out'):history(fyersModel.FyersModel(),{})
            self.assertEqual(get.call_count,1)
