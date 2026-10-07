"""Cash sizing, signed ownership, paper fills and live reconciliation without broker calls."""
from copy import deepcopy
import unittest
from .runner import Broker, configuration
from .test_runner import RenkoLifecycleTests
from .history import trade_history


class CashLifecycleTests(unittest.TestCase):
    setUp = RenkoLifecycleTests.setUp
    start = RenkoLifecycleTests.start

    def prepare(self, direction='BULLISH', mode='PAPER'):
        self.c.update(underlying='NSE:TRENT-EQ', execution_route='CASH_EQUITY', quantity=237, mode=mode)
        self.b.resolve = lambda c, d: dict(symbol=c['underlying'], lot_size=1, tick_size=.05,
                                           quantity_multiplier=1, entry_side=1 if d=='BULLISH' else -1)
        self.b.quote = lambda s: dict(bid=100, ask=101, received_at=self.b.now, exchange_at=self.b.now)
        self.b.order = lambda s,q,side,quote: dict(symbol=s,qty=q,side=side,type=2,productType='INTRADAY')
        self.start()
        sig=deepcopy(self.r.signal())
        sig.update(cross_direction=direction, supertrend_cross_direction=direction,
                   direction=direction,close=120 if direction=='BULLISH' else 80)
        self.r.signal=lambda: deepcopy(sig)
        return sig

    def test_cash_long_uses_exact_shares_and_long_fills(self):
        self.prepare();self.r.step()
        p=self.r.state['position']
        self.assertEqual((p['symbol'],p['quantity'],p['entry_side'],p['entry_price']),('NSE:TRENT-EQ',237,1,101))
        self.assertEqual(self.r.state['config']['quantity'],237)
        self.assertEqual(self.r.state['order_history'][0]['product'],'INTRADAY')
        self.assertEqual(self.b.sent,[])

    def test_short_sell_entry_buy_exit_pnl_and_journal(self):
        sig=self.prepare('BEARISH');self.r.step()
        p=self.r.state['position']
        self.assertEqual((p['quantity'],p['entry_side'],p['entry_price']),(237,-1,100))
        self.assertEqual(self.r.snapshot()['pnl']['unrealized'],-237)
        self.b.now+=60;sig.update(timestamp=sig['timestamp']+60,close=120,supertrend_cross_direction='BULLISH',cross_direction='BULLISH')
        self.b.quote=lambda s:dict(bid=89,ask=90,received_at=self.b.now,exchange_at=self.b.now)
        self.r.step()
        self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['realized_pnl'],2370)
        rows=self.r.state['order_history']
        self.assertEqual([(r['side'],r['is_entry']) for r in rows],[('SELL',True),('BUY',False)])
        trade=trade_history(rows)[0]
        self.assertEqual((trade['entry_side'],trade['entry_filled'],trade['exit_filled'],trade['realized_pnl']),('SELL',237,237,2370))
        self.assertEqual(self.b.sent,[])
        self.r.step();self.assertEqual(len(self.r.state['order_history']),2)

    def test_live_short_partial_fill_reconciles_negative_quantity(self):
        self.prepare('BEARISH','LIVE');self.r.step()
        pending=self.r.state['pending'];order=pending['order']
        self.assertEqual(order['side'],-1)
        self.b.book=[dict(id=pending['id'],symbol=order['symbol'],side=-1,qty=237,
                          productType='INTRADAY',status=1,filledQty=17,tradedPrice=100)]
        reconciled=[]
        self.b.reconcile_position=lambda s,q:reconciled.append(q)
        self.r.step()
        self.assertEqual(reconciled,[-17])
        self.assertEqual(self.r.state['position']['quantity'],17)
        self.assertEqual(self.r.state['position']['entry_side'],-1)
        self.assertEqual(len(self.b.sent),1)  # Fake adapter only.

    def test_cash_quantity_validation_and_option_lots_preserved(self):
        for value in (0,-1,True,'2.5',1000001):
            with self.assertRaises(ValueError):configuration({**self.c,'execution_route':'CASH_EQUITY','quantity':value})
        c=configuration({**self.c,'execution_route':'CASH_EQUITY','quantity':1000,'lots':1000})
        self.assertEqual((c['quantity'],c['lots']),(1000,1))
        self.assertEqual(configuration({**self.c,'lots':2})['lots'],2)

    def test_cnc_holds_across_cutoff_and_overnight(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.c['cash_product']='CNC'
        self.prepare();self.r.step()
        for hour in (15,17):
            self.b.now=datetime(2026,10,6,hour,45,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
            self.r.step()
            self.assertIsNotNone(self.r.state['position'])
            self.assertTrue(self.r.state['running'])
            self.assertFalse(self.r.state['position'].get('exit_requested',False))
        self.b.now=datetime(2026,10,7,8,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        self.r.step()
        self.assertEqual(self.r.state['status'],'CARRY_FORWARD_WAITING')
        self.assertEqual(len(self.r.state['order_history']),1)

    def test_intraday_short_squareoff_buys_owned_quantity(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        self.prepare('BEARISH');self.r.step()
        self.b.now=datetime(2026,10,6,15,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        self.r.step()
        self.assertIsNone(self.r.state['position'])
        row=self.r.state['order_history'][-1]
        self.assertEqual((row['side'],row['requested']),('BUY',237))
        self.assertIn('TIMED_SQUARE_OFF',row['reason'])


class CashBrokerTests(unittest.TestCase):
    def test_cash_master_resolution_never_selects_an_option_or_lot_multiplier(self):
        row=['']*17
        row[2]='0';row[3]='1';row[4]='0.05';row[6]='0915-1530';row[9]='NSE:TRENT-EQ';row[10]='10';row[11]='10'
        broker=Broker('/tmp',lambda *a,**k:[],lambda *a: self.fail('Option resolution called for equity'))
        broker.underlying=lambda symbol:row
        c=dict(underlying='NSE:TRENT-EQ',execution_route='CASH_EQUITY',quantity=237)
        for direction,side in [('BULLISH',1),('BEARISH',-1)]:
            meta=broker.resolve(c,direction)
            self.assertEqual((meta['quantity'],meta['lot_size'],meta['quantity_multiplier'],meta['entry_side']),(237,1,1,side))
            order=broker.order(meta['symbol'],237,side,{})
            broker.validate_order(order)
            self.assertEqual(order['productType'],'INTRADAY')
        row[9]='NSE:NIFTY50-INDEX'
        with self.assertRaises(ValueError):broker.cash_contract(row[9])

    def test_cnc_product_and_short_constraint(self):
        row=['']*17
        row[2]='0';row[4]='0.05';row[6]='0915-1530';row[9]='BSE:TRENT-A';row[10]='12';row[11]='10'
        broker=Broker('/tmp',lambda *a,**k:[],lambda *a:None)
        broker.underlying=lambda symbol:row
        c=dict(underlying=row[9],execution_route='CASH_EQUITY',quantity=200,cash_product='CNC')
        meta=broker.resolve(c,'BULLISH')
        order=broker.order(meta['symbol'],200,1,{})
        self.assertEqual(order['productType'],'CNC')
        broker.validate_order(order)
        with self.assertRaisesRegex(ValueError,'overnight cash short'):broker.resolve(c,'BEARISH')
        broker.positions=lambda:[]
        broker.holdings=lambda:[dict(symbol=row[9],remainingQuantity=200)]
        broker.reconcile_position(row[9],200)
        with self.assertRaisesRegex(ValueError,'differ'):broker.reconcile_position(row[9],100)
        broker.positions=lambda:[dict(symbol=row[9],netQty=200,productType='CNC')]
        with self.assertRaisesRegex(ValueError,'overlap'):broker.reconcile_position(row[9],200)
