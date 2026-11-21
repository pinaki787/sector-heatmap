from datetime import datetime
from unittest import TestCase, mock
import requests
from sector_heatmap.parser_quote import fetch_parser_quote, IST

class ParserQuoteTests(TestCase):
    symbol = 'MCX:CRUDEOIL26OCT8900PE'
    now = datetime(2026,9,29,14,17,10,tzinfo=IST)
    def get(self, values, symbol=None, status='ok'):
        response = mock.Mock()
        response.json.return_value = {'s': 'ok', 'd': [{'n':symbol or self.symbol,'s':status,'v':values}]}
        return mock.Mock(return_value=response)
    def test_exact_symbol_and_recent_provider_time(self):
        get = self.get({'lp':466, 'tt':self.now.timestamp()-5})
        result = fetch_parser_quote(self.symbol,'app:token',get=get,now=self.now)
        self.assertEqual(result['ltp'],466)
        self.assertEqual(result['freshness'],'FRESH')
        self.assertEqual(get.call_args.kwargs['params'],{'symbols':self.symbol})
    def test_old_or_missing_or_future_timestamp_not_live(self):
        for ts in [None, self.now.timestamp()-3600, self.now.timestamp()+100]:
            result = fetch_parser_quote(self.symbol,'app:token',get=self.get({'lp':466,'tt':ts}),now=self.now)
            self.assertEqual(result['ltp'],466)
            self.assertEqual(result['freshness'],'UNCONFIRMED')
    def test_wrong_symbol_missing_price_or_invalid_value_not_substituted(self):
        for get in [self.get({'lp':466},symbol='OTHER'), self.get({'bid':466,'ask':467}), self.get({'lp':0}), self.get({'lp':'nan'}),self.get({'lp':466},status='error')]:
            result=fetch_parser_quote(self.symbol,'app:token',get=get,now=self.now)
            self.assertEqual(result['status'],'UNAVAILABLE')
            self.assertIsNone(result['ltp'])
    def test_connection_error_and_missing_token(self):
        result=fetch_parser_quote(self.symbol,'app:token',get=mock.Mock(side_effect=requests.Timeout()),now=self.now)
        self.assertEqual(result['status'],'UNAVAILABLE')
        get=mock.Mock()
        fetch_parser_quote(self.symbol,'',get=get,now=self.now)
        get.assert_not_called()
    def test_rate_limit_diagnostic_and_cooldown(self):
        from sector_heatmap import parser_quote
        response=mock.Mock(status_code=429,headers={'Retry-After':'90'})
        get=mock.Mock(return_value=response)
        try:
            result=fetch_parser_quote(self.symbol,'app:token',get=get,now=self.now)
            self.assertEqual(result['reason'],'RATE_LIMITED')
            self.assertIn('HTTP 429',result['message'])
            self.assertEqual(result['retry_after_seconds'],90)
            response.json.assert_not_called()
            again=fetch_parser_quote(self.symbol,'app:token',get=get,now=self.now)
            self.assertEqual(again['reason'],'RATE_LIMITED');self.assertEqual(get.call_count,1)
        finally:parser_quote._retry_after=0
