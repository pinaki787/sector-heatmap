import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from fyers_apiv3 import fyersModel
from sector_heatmap import fyers_history as module

class HistoryRateLimitTests(unittest.TestCase):
    def setUp(self):
        module._HISTORY_COOLDOWNS.clear()
        self.client=self.client_for("test-app:test-session")
    def client_for(self,header):
        client=object.__new__(fyersModel.FyersModel)
        client.header=header;client.service=SimpleNamespace(content="application/json")
        return client
    def tearDown(self):module._HISTORY_COOLDOWNS.clear()
    def response(self,status=429,headers=None,body=None):
        result=Mock(status_code=status,headers=headers or {})
        result.json.return_value=body if body is not None else {"s":"ok","candles":[]}
        return result
    def test_retry_after_is_honoured_without_inline_retry_or_another_request_during_cooldown(self):
        response=self.response(headers={"Retry-After":"120"})
        with patch.object(module.time,"monotonic",return_value=100),patch.object(module.requests,"get",return_value=response) as get:
            with self.assertRaises(module.FyersHistoryRateLimited) as error:module.history(self.client,{})
            self.assertEqual(error.exception.retry_after,120)
            self.assertEqual(get.call_count,1)
        with patch.object(module.time,"monotonic",return_value=110),patch.object(module.requests,"get") as get:
            with self.assertRaises(module.FyersHistoryRateLimited) as error:module.history(self.client,{})
            self.assertEqual(error.exception.retry_after,110)
            get.assert_not_called()
        with patch.object(module.time,"monotonic",return_value=221),patch.object(module.requests,"get",return_value=self.response(200)) as get:
            self.assertEqual(module.history(self.client,{})["s"],"ok")
            self.assertEqual(get.call_count,1)
    def test_sdk_json_rate_limit_is_distinct_from_authentication_failure(self):
        for code in (-360,-429,429):
            module._HISTORY_COOLDOWNS.clear()
            response=self.response(200,body={"s":"error","code":code})
            with patch.object(module.requests,"get",return_value=response) as get:
                with self.assertRaises(module.FyersHistoryRateLimited):module.history(self.client,{})
                self.assertEqual(get.call_count,1)
    def test_token_scopes_do_not_share_cooldown(self):
        other=self.client_for("other-app:other-session")
        with patch.object(module.requests,"get",return_value=self.response()):
            with self.assertRaises(module.FyersHistoryRateLimited):module.history(self.client,{})
        with patch.object(module.requests,"get",return_value=self.response(200)) as get:
            self.assertEqual(module.history(other,{})["s"],"ok")
            self.assertEqual(get.call_count,1)
    def test_millisecond_and_http_date_retry_headers(self):
        self.assertEqual(module._retry_seconds(self.response(headers={"Retry-After":"1","X-Retry-After-Ms":"2500"})),3)
        with patch.object(module.time,"time",return_value=0):
            self.assertEqual(module._retry_seconds(self.response(headers={"Retry-After":"Thu, 01 Jan 1970 00:02:00 GMT"})),120)
    def test_invalid_headers_have_bounded_conservative_default(self):
        self.assertEqual(module._retry_seconds(self.response(headers={"Retry-After":"NaN"})),60)
        self.assertEqual(module._retry_seconds(self.response(headers={"Retry-After":"999999999"})),86400)
        self.assertEqual(module._retry_seconds(self.response(headers={"Retry-After":"-1"})),60)
    def test_authentication_error_remains_distinct(self):
        with patch.object(module.requests,"get",return_value=self.response(401)):
            with self.assertRaises(module.FyersHistoryAuthenticationRequired):module.history(self.client,{})
        self.assertEqual(module._HISTORY_COOLDOWNS,{})
if __name__=="__main__":unittest.main()
