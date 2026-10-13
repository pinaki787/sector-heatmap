import unittest
from unittest.mock import Mock,patch
import requests
from sector_heatmap.fyers_history import quotes
from sector_heatmap.fyers_transport import client
class QuoteErrors(unittest.TestCase):
 def run_response(self,response):
  c=client(client_id='test',token='test')
  with patch('sector_heatmap.fyers_history.requests.get',return_value=response):return quotes(c,{'symbols':'NSE:RELIANCE-EQ'})
 def test_rate_limited(self):
  with self.assertRaisesRegex(RuntimeError,'rate-limited'):self.run_response(Mock(status_code=429))
 def test_rate_limited_json(self):
  with self.assertRaisesRegex(RuntimeError,'rate-limited'):self.run_response(Mock(status_code=200,json=Mock(return_value={'code':-429,'s':'error'})))
 def test_unreadable(self):
  with self.assertRaisesRegex(RuntimeError,'unreadable'):self.run_response(Mock(status_code=200,json=Mock(side_effect=ValueError())))
 def test_access_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'authentication'):self.run_response(Mock(status_code=401))
 def test_valid(self):
  data={'s':'ok','d':[{'v':{'lp':100}}]};self.assertEqual(self.run_response(Mock(status_code=200,json=Mock(return_value=data))),data)
 def test_sdk_http_error_preserved(self):
  c=client(client_id='test',token='test');r=Mock(status_code=429,json=Mock(return_value={'code':-429,'s':'error'}),raise_for_status=Mock(side_effect=requests.HTTPError()))
  with patch.object(c._sector_pulse_ipv4_session,'get',return_value=r):self.assertEqual(c.quotes({'symbols':'NSE:RELIANCE-EQ'})['code'],-429)
if __name__=='__main__':unittest.main()
