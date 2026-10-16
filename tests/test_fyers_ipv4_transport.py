import unittest
from unittest.mock import patch
from sector_heatmap.fyers_transport import client,IPv4Adapter
from fyers_apiv3 import fyersModel

class TransportTests(unittest.TestCase):
    def test_private_sdk_session_all_verbs_and_no_global_patch(self):
        original=fyersModel.FyersServiceSync.post_call.__globals__['requests']
        c=client(client_id='test',token='test')
        session=c._sector_pulse_ipv4_session
        self.assertFalse(session.trust_env)
        self.assertIsInstance(session.get_adapter('https://api-t1.fyers.in/'),IPv4Adapter)
        self.assertEqual(session.get_adapter('https://api-t1.fyers.in/').poolmanager.connection_pool_kw['source_address'],('0.0.0.0',0))
        for name in ('get_call','post_call','delete_call','patch_call'):
            self.assertIs(getattr(c.service,name).__func__.__globals__['requests'],session)
        self.assertIs(fyersModel.FyersServiceSync.post_call.__globals__['requests'],original)
        other=client(client_id='other',token='other')
        self.assertIsNot(session,other._sector_pulse_ipv4_session)
    def test_async_rejected(self):
        with self.assertRaises(ValueError):client(is_async=True)
    def test_order_uses_private_transport_with_fake_response(self):
        c=client(client_id='test',token='test')
        response=__import__('unittest.mock',fromlist=['Mock']).Mock(status_code=200)
        response.json.return_value={'s':'ok','id':'fake-only'}
        with patch.object(c._sector_pulse_ipv4_session,'post',return_value=response) as post:
            result=c.place_order({'symbol':'FAKE','qty':1})
        self.assertEqual(result['id'],'fake-only')
        self.assertEqual(post.call_count,1)
