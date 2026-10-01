import unittest,time
from unittest.mock import patch,MagicMock
from strategies.ema_crossover.broker import FyersBroker,IndependentDataSocket
class Tests(unittest.TestCase):
 def broker(self):return FyersBroker('/tmp',lambda *a:[],lambda *a:None)
 def test_sdk_instance_isolation(self):
  self.assertIsNot(IndependentDataSocket.__new__(IndependentDataSocket),IndependentDataSocket.__new__(IndependentDataSocket))
 def preflight(self,positions,orders):
  b=self.broker();b.validate_order=lambda o:None;b.quote=lambda s:dict(bid=10,ask=10)
  b.positions=lambda:positions;b.orders=lambda:orders
  with patch('strategies.ema_crossover.broker._current_client',side_effect=RuntimeError('REACHED_FUNDS')):
   b.preflight(dict(symbol='BSE:EXACTCE',qty=10),{})
 def test_unrelated_positions_and_orders_reach_funds(self):
  with self.assertRaisesRegex(RuntimeError,'REACHED_FUNDS'):
   self.preflight([dict(symbol='BSE:OTHERPE',netQty=10)],[dict(symbol='BSE:OTHERCE',status=6)])
 def test_same_contract_position_any_product_blocks(self):
  for qty in [10,-10]:
   with self.assertRaisesRegex(ValueError,'same option contract'):
    self.preflight([dict(symbol='BSE:EXACTCE',netQty=qty)],[])
 def test_same_contract_pending_buy_or_sell_blocks(self):
  for side in [1,-1]:
   with self.assertRaisesRegex(ValueError,'same option contract'):
    self.preflight([],[dict(symbol='BSE:EXACTCE',status=6,side=side)])
 def test_flat_and_terminal_order_do_not_block(self):
  with self.assertRaisesRegex(RuntimeError,'REACHED_FUNDS'):
   self.preflight([dict(symbol='BSE:EXACTCE',netQty=0)],[dict(symbol='BSE:EXACTCE',status=2)])
 def test_stream_reconnect_errors_and_stale_callbacks(self):
  b=self.broker();b.symbols={'BSE:SENSEX-INDEX'};socket=MagicMock()
  with patch('strategies.ema_crossover.broker.IndependentDataSocket',return_value=socket) as factory,patch('strategies.ema_crossover.broker.configure_websocket_ca_bundle'),patch('strategies.ema_crossover.broker.load_config',return_value={}),patch('strategies.ema_crossover.broker.threading.Thread'):
   b.start();callbacks=factory.call_args.kwargs
   callbacks['on_connect']()
   with self.assertRaisesRegex(ValueError,'no tick'):b.tick('BSE:OPTIONPE')
   self.assertEqual(set(socket.subscribe.call_args.kwargs['symbols']),{'BSE:SENSEX-INDEX','BSE:OPTIONPE'})
   now=time.time();callbacks['on_message'](dict(symbol='BSE:SENSEX-INDEX',ltp=80000,exch_feed_time=now))
   self.assertEqual(b.tick('BSE:SENSEX-INDEX')['ltp'],80000)
   callbacks['on_error'](dict(code=-99,message='private-secret'))
   self.assertTrue(b.connected);self.assertNotIn('private-secret',str(b.stream_status()))
   callbacks['on_close']();self.assertFalse(b.connected)
   with self.assertRaisesRegex(ValueError,'disconnected'):b.tick('BSE:SENSEX-INDEX')
   callbacks['on_connect']();self.assertTrue(b.connected)
   self.assertEqual(set(socket.subscribe.call_args.kwargs['symbols']),{'BSE:SENSEX-INDEX','BSE:OPTIONPE'})
   b.stop();callbacks['on_connect']();self.assertFalse(b.connected)
 def test_freshness_not_relaxed(self):
  b=self.broker();b.connected=True;b.socket=MagicMock();symbol='BSE:SENSEX-INDEX';b.symbols.add(symbol)
  for received,exchange,message in [(time.time()-16,time.time(),'receive age'),(time.time(),time.time()-61,'exchange timestamp')]:
   b.ticks[symbol]=(dict(ltp=80000,exch_feed_time=exchange),received)
   with self.assertRaisesRegex(ValueError,message):b.tick(symbol)
 def test_partial_updates_do_not_refresh_old_executable_bid(self):
  b=self.broker();b.symbols={'BSE:OPTIONPE'};socket=MagicMock()
  with patch('strategies.ema_crossover.broker.IndependentDataSocket',return_value=socket) as factory,patch('strategies.ema_crossover.broker.configure_websocket_ca_bundle'),patch('strategies.ema_crossover.broker.load_config',return_value={}),patch('strategies.ema_crossover.broker.threading.Thread'):
   b.start();callbacks=factory.call_args.kwargs;callbacks['on_connect']()
   with patch('strategies.ema_crossover.broker.time.time',return_value=100):callbacks['on_message'](dict(symbol='BSE:OPTIONPE',bid_price=10,ask_price=11,exch_feed_time=100))
   with patch('strategies.ema_crossover.broker.time.time',return_value=110):
    callbacks['on_message'](dict(symbol='BSE:OPTIONPE',ltp=12,exch_feed_time=110))
    q=b.quote('BSE:OPTIONPE');self.assertEqual(q['received_at'],100);self.assertEqual(q['exchange_at'],100)
   b.stop()
if __name__=='__main__':unittest.main()
