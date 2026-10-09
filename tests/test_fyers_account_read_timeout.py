import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import requests
from fyers_apiv3 import fyersModel
from sector_heatmap.fyers_history import account_read


class AccountReads(unittest.TestCase):
    def client(self):
        client = object.__new__(fyersModel.FyersModel)
        client.header = 'test-token'
        client.service = SimpleNamespace(content='application/json')
        return client

    def test_timeout_blocks_without_retry(self):
        with patch('sector_heatmap.fyers_history.requests.get', side_effect=requests.Timeout) as get:
            with self.assertRaisesRegex(ValueError, 'execution blocked'):
                account_read(self.client(), 'positions')
            self.assertEqual(get.call_count, 1)
            self.assertEqual(get.call_args.kwargs['timeout'], (3, 10))

    def test_endpoint_and_response_preserved(self):
        response = Mock()
        response.json.return_value = {'s':'ok', 'orderBook':[]}
        with patch('sector_heatmap.fyers_history.requests.get', return_value=response) as get:
            self.assertEqual(account_read(self.client(), 'orderbook'), response.json.return_value)
            self.assertEqual(get.call_args.args[0], fyersModel.Config.API + fyersModel.Config.orderbook)

    def test_mutations_prohibited(self):
        with patch('sector_heatmap.fyers_history.requests.get') as get:
            with self.assertRaises(ValueError):
                account_read(self.client(), 'place_order')
            get.assert_not_called()
