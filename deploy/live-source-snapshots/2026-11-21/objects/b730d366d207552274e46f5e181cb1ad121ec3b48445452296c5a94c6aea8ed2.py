import struct
import unittest
from unittest.mock import Mock
from .motilal_api import Client,MotilalError,session_deadline
from .motilal_feed import QuoteFeed,decode_packet,EPOCH_1980,login_packet,subscription_packet

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.now=1792050000
        self.credentials=dict(MO_CLIENT_ID='CLIENT1',MO_API_KEY='fixture-key',MO_API_SECRET='fixture-secret',MO_AUTH_TOKEN='fixture-auth',MO_ACCESS_TOKEN='fixture-access',MO_PUBLIC_IP='192.0.2.1',MO_LOCAL_IP='10.0.0.1',MO_MAC_ADDRESS='00:11:22:33:44:55')
        self.transport=Mock();self.transport.post.return_value.status_code=200
        self.transport.post.return_value.json.return_value=dict(status='SUCCESS',data={'clientcode':'CLIENT1'})
        self.client=Client(self.credentials,requester=self.transport,clock=lambda:self.now)
    def test_profile_must_match_owned_account(self):
        self.transport.post.return_value.json.return_value=dict(status='SUCCESS',data={'clientcode':'OTHER'})
        with self.assertRaises(PermissionError):self.client.profile()
        self.assertFalse(self.client.identity_verified)
    def test_unknown_operation_cannot_choose_arbitrary_endpoint(self):
        with self.assertRaises(ValueError):self.client.request('https://other.invalid')
        self.transport.post.assert_not_called()
    def test_live_gate_blocks_every_mutation(self):
        self.client.profile();self.transport.reset_mock()
        for action in ['place','modify','cancel']:
            with self.assertRaises(PermissionError):self.client.request(action,{})
        self.transport.post.assert_not_called()
    def test_identity_required_even_with_live_gate(self):
        self.client.live_enabled=True
        with self.assertRaises(PermissionError):self.client.request('place',{})
        self.transport.post.assert_not_called()
    def test_mutation_timeout_is_uncertain_and_not_retried(self):
        self.client.profile();self.client.live_enabled=True;self.transport.reset_mock();self.transport.post.side_effect=TimeoutError('fixture-secret')
        with self.assertRaises(MotilalError) as error:self.client.request('place',{})
        self.assertTrue(error.exception.uncertain);self.assertNotIn('fixture-secret',str(error.exception));self.transport.post.assert_called_once()
    def test_redirect_cannot_leak_credentials(self):
        self.transport.post.return_value.status_code=302
        with self.assertRaises(MotilalError):self.client.profile()
        self.assertFalse(self.transport.post.call_args.kwargs['allow_redirects'])
    def test_expired_session_blocks_before_network(self):
        self.client.credentials['MO_SESSION_EXPIRES_AT']=self.now-1
        with self.assertRaises(MotilalError) as error:self.client.profile()
        self.assertTrue(error.exception.auth_required);self.transport.post.assert_not_called()
    def test_rest_ltp_is_paisa_and_never_executable_depth(self):
        self.transport.post.return_value.json.return_value=dict(status='SUCCESS',data=dict(exchange='NSE',scripcode=1,ltp=12345,bid=12340,ask=12350))
        quote=self.client.quote('NSE',1)
        self.assertEqual(quote['ltp'],123.45);self.assertFalse(quote['depth_eligible']);self.assertNotIn('bid',quote)
    def test_raw_broker_failure_is_sanitized(self):
        self.transport.post.return_value.json.return_value=dict(status='FAILURE',message='fixture-secret',errorcode='MO100')
        with self.assertRaises(MotilalError) as error:self.client.profile()
        self.assertNotIn('fixture-secret',str(error.exception));self.assertEqual(error.exception.code,'MO100')
    def test_required_headers_and_bounded_network(self):
        self.client.profile();args=self.transport.post.call_args.kwargs
        self.assertEqual(args['headers']['apisecretkey'],'fixture-secret');self.assertEqual(args['timeout'],(3,10))
    def test_foreign_client_payload_blocks_before_network(self):
        with self.assertRaises(PermissionError):self.client.request('positions',{'clientcode':'OTHER'})
        self.transport.post.assert_not_called()

class LogoutTests(ApiTests):
    def test_session_logout_is_not_an_order_action(self):
        self.client.profile();self.transport.reset_mock();self.client.request('logout',{'userid':'CLIENT1'})
        self.assertIn('/rest/login/v5/logout',self.transport.post.call_args.args[0]);self.transport.post.assert_called_once()
    def test_logout_needs_verified_owned_identity(self):
        with self.assertRaises(PermissionError):self.client.request('logout',{'userid':'CLIENT1'})
        self.client.profile();self.transport.reset_mock()
        with self.assertRaises(PermissionError):self.client.request('logout',{'userid':'OTHER'})
        self.transport.post.assert_not_called()

class FeedTests(unittest.TestCase):
    def setUp(self):
        self.now=1792050000
        self.feed=QuoteFeed(Mock(client_id='CLIENT1'),clock=lambda:self.now);self.feed.subscribe('NSEFO',35000);self.feed.connected=True
    def packet(self,kind=b'B',age=0):
        header=struct.pack('<cii c',b'N',35000,int(self.now-EPOCH_1980-age),kind)
        body=struct.pack('<fihfih',100,65,1,100.5,65,1) if kind==b'B' else struct.pack('<fiiii',100,65,65,0,0)
        return header+body
    def test_login_and_subscription_packet_lengths(self):
        self.assertEqual(len(login_packet('CLIENT1')),114);self.assertEqual(len(subscription_packet('NSEFO',35000)),10)
    def test_fragmented_packet_retains_exact_depth(self):
        packet=self.packet();self.feed.ingest(packet[:12]);self.feed.ingest(packet[12:])
        quote=self.feed.quote('NSEFO',35000);self.assertEqual(quote['bid'],100);self.assertEqual(quote['ask'],100.5)
    def test_stale_exchange_time_cannot_become_fresh_on_receipt(self):
        self.feed.ingest(self.packet(age=60))
        with self.assertRaises(ValueError):self.feed.quote('NSEFO',35000)
    def test_ltp_does_not_freshen_old_depth(self):
        self.feed.ingest(self.packet());self.now+=20;self.feed.ingest(self.packet(kind=b'A'))
        with self.assertRaises(ValueError):self.feed.quote('NSEFO',35000)
    def test_old_socket_generation_is_ignored(self):
        self.feed.generation=2;self.feed.ingest(self.packet(),generation=1)
        with self.assertRaises(ValueError):self.feed.quote('NSEFO',35000)
    def test_ambiguous_native_identity_is_rejected(self):
        with self.assertRaises(ValueError):self.feed.subscribe('NSE',35000)
    def test_invalid_price_cannot_authorize_execution(self):
        packet=self.packet();packet=packet[:10]+struct.pack('<fihfih',float('nan'),65,1,100.5,65,1)
        with self.assertRaises(ValueError):decode_packet(packet)
    def test_native_ltp_volume_and_interest_reach_depth_snapshot(self):
        header=struct.pack('<cii c',b'N',35000,int(self.now-EPOCH_1980),b'A')
        self.feed.ingest(header+struct.pack('<fiifi',100,65,12000,99.5,48000))
        self.feed.ingest(self.packet())
        quote=self.feed.quote('NSEFO',35000)
        self.assertEqual((quote['cumulative_volume'],quote['open_interest']),(12000,48000))
        self.feed.ingest(header+struct.pack('<fiifi',100,65,-1,99.5,-1))
        quote=self.feed.quote('NSEFO',35000)
        self.assertIsNone(quote['cumulative_volume']);self.assertIsNone(quote['open_interest'])
    def test_socket_stop_clears_quotes(self):
        self.feed.ingest(self.packet());self.feed.stop()
        with self.assertRaises(ValueError):self.feed.quote('NSEFO',35000)

class RecoveryTests(unittest.TestCase):
    def test_application_heartbeat_is_answered(self):
        feed=QuoteFeed(Mock(client_id='CLIENT1'))
        feed.socket=Mock();feed.connected=True
        feed.ingest(struct.pack('<cii c',b'N',0,0,b'1')+b' '*20)
        self.assertEqual(feed.socket.send.call_args.args[0],struct.pack('<cH',b'1',0))

    def test_access_token_exchange_has_no_json_body(self):
        transport=Mock();transport.post.return_value.status_code=200
        transport.post.return_value.json.return_value={'status':'SUCCESS'}
        credentials=dict(MO_CLIENT_ID='CLIENT1',MO_API_KEY='key',MO_API_SECRET='secret',MO_AUTH_TOKEN='auth',MO_PUBLIC_IP='192.0.2.1',MO_LOCAL_IP='10.0.0.1',MO_MAC_ADDRESS='00:11:22:33:44:55')
        Client(credentials,requester=transport).request('access_token')
        self.assertIsNone(transport.post.call_args.kwargs['json'])

    def test_disconnect_invalidates_captured_candle(self):
        import tempfile
        from pathlib import Path
        from .motilal_history import History
        with tempfile.TemporaryDirectory() as folder:
            now=[120.0]
            history=History(Path(folder)/'candles.sqlite',clock=lambda:now[0])
            history.ingest(dict(symbol='MO:NSE:1',exch_feed_time=120,ltp=100),120)
            history.invalidate()
            now[0]=180
            history.ingest(dict(symbol='MO:NSE:1',exch_feed_time=180,ltp=101),180)
            self.assertEqual(history.candles('MO:NSE:1'),[])

    def test_complete_native_minutes_survive_reopening(self):
        import tempfile
        from pathlib import Path
        from .motilal_history import History
        with tempfile.TemporaryDirectory() as folder:
            now=[120.0];path=Path(folder)/'candles.sqlite'
            history=History(path,clock=lambda:now[0])
            for stamp,price in [(120,100),(150,102),(180,101),(210,103),(240,104)]:
                now[0]=stamp
                history.ingest(dict(symbol='MO:NSE:1',exch_feed_time=stamp,ltp=price),120)
            bars=History(path,clock=lambda:now[0]).candles('MO:NSE:1',minutes=2)
            self.assertEqual(len(bars),1)
            self.assertEqual((bars[0]['open'],bars[0]['high'],bars[0]['close']),(100,103,103))

    def test_fractional_native_token_is_rejected(self):
        from .motilal_master import contract
        with self.assertRaises(ValueError):contract(dict(exchangename='NSE',scripcode=1.5,marketlot=1,ticksize=.05),'NSE')

class ConnectionGenerationTests(unittest.TestCase):
    def packet(self,now,token=1,price=100):
        return struct.pack('<cii c',b'N',token,int(now-EPOCH_1980),b'A')+struct.pack('<fiiii',price,1,1,0,0)

    def test_late_old_socket_callbacks_cannot_poison_replacement(self):
        import threading
        now=1792050000;callbacks=[];observed=[]
        feed=None
        def factory(url,**handlers):
            socket=Mock();callbacks.append((socket,handlers))
            number=len(callbacks)
            def run(**kwargs):
                handlers['on_open'](socket)
                if number==1:handlers['on_close'](socket,1000,'closed');return
                handlers['on_message'](socket,self.packet(now,price=101))
                old,old_handlers=callbacks[0]
                old_handlers['on_message'](old,self.packet(now,price=999))
                old_handlers['on_close'](old,1000,'late close')
                observed.append((feed.connected,feed.quotes[(b'N',1)]['ltp']))
                feed.stop()
            socket.run_forever.side_effect=run
            return socket
        feed=QuoteFeed(Mock(client_id='CLIENT1'),clock=lambda:now,socket_factory=factory)
        feed.subscribe('NSE',1)
        feed.closed=Mock(is_set=Mock(return_value=False),wait=Mock(return_value=False))
        feed.start();feed.thread.join(timeout=2)
        self.assertFalse(feed.thread.is_alive())
        self.assertEqual(observed,[(True,101)])

    def test_subscribing_mid_minute_does_not_claim_full_minute_coverage(self):
        now=[1792050000.0];ticks=[]
        feed=QuoteFeed(Mock(client_id='CLIENT1'),clock=lambda:now[0],on_tick=ticks.append)
        feed.socket=Mock();feed.connected=True;feed.coverage_since=now[0]-120
        now[0]+=20;feed.subscribe('NSE',1)
        feed.ingest(self.packet(now[0]))
        self.assertEqual(ticks[0]['coverage_since'],now[0])
        self.assertGreater(ticks[0]['coverage_since'],int(now[0])//60*60)

    def test_older_tick_cannot_overwrite_current_price(self):
        now=1792050000;feed=QuoteFeed(Mock(client_id='CLIENT1'),clock=lambda:now)
        feed.subscribe('NSE',1);feed.connected=True
        feed.ingest(self.packet(now,price=101));feed.ingest(self.packet(now-5,price=99))
        self.assertEqual(feed.quotes[(b'N',1)]['ltp'],101)
