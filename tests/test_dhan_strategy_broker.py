import json
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from sector_heatmap.dhan_execution import IST
from sector_heatmap.dhan_strategy_broker import Broker
from sector_heatmap.dhan_strategy_service import DhanRenkoRunner,renko_configuration


class FakeClient:
    client_id='owner'
    def __init__(self,now):
        self.calls=[];self.now=now;self.owner='owner';self.positions=[];self.orders=[];self.fail_submit=False
        self.balance=100000
    def request(self,method,path,payload=None):
        self.calls.append((method,path,payload))
        if path=='/profile':return dict(dhanClientId=self.owner,dataPlan='active')
        if path=='/positions':return self.positions
        if path=='/orders' and method=='GET':return self.orders
        if path.startswith('/orders/external/'):raise RuntimeError('Unknown')
        if path=='/fundlimit':return dict(dhanClientId=self.owner,availabelBalance=self.balance)
        if path=='/margincalculator':return dict(totalMargin=1000,insufficientBalance=0)
        if path=='/ip/getIP':return dict(primaryIP='127.0.0.1')
        if path=='/marketfeed/quote':
            segment=next(iter(payload));sec=str(payload[segment][0])
            return dict(data={segment:{sec:dict(last_price=100,last_trade_time=datetime.fromtimestamp(self.now,IST).strftime('%d/%m/%Y %H:%M:%S'),depth=dict(buy=[dict(price=9.95)],sell=[dict(price=10)]))}})
        if path=='/charts/intraday':
            opening=int(datetime.fromtimestamp(self.now,IST).replace(hour=9,minute=15,second=0).timestamp())
            return dict(timestamp=[opening,opening+60,opening+120],open=[100]*3,high=[101]*3,low=[99]*3,close=[100]*3,volume=[10]*3)
        if path=='/orders' and method=='POST':
            if self.fail_submit:raise RuntimeError('Timeout')
            return dict(orderId='123',orderStatus='PENDING')
        if method=='DELETE':return dict(orderId='123')
        raise AssertionError((method,path))


def row(id,symbol,kind='I',option='XX',strike='',expiry=''):
    return dict(SEM_SMST_SECURITY_ID=id,SEM_TRADING_SYMBOL=symbol,SEM_SEGMENT=kind,
                SEM_EXM_EXCH_ID='NSE',SEM_LOT_UNITS='25' if kind=='D' else '1',
                SEM_TICK_SIZE='5' if kind=='D' else '.05',SEM_INSTRUMENT_NAME='OPTIDX' if kind=='D' else 'INDEX',
                SEM_OPTION_TYPE=option,SEM_STRIKE_PRICE=strike,SEM_EXPIRY_DATE=expiry)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=datetime(2026,10,12,10,0,tzinfo=IST).timestamp()
        self.client=FakeClient(self.now)
        self.rows=[row('13','NIFTY'),row('1','NIFTY-Oct2026-100-CE','D','CE','100','2026-10-15'),
                   row('2','NIFTY-Oct2026-100-PE','D','PE','100','2026-10-15')]
        class Master:
            def load(inner,now):return self.rows
        class Service:
            account=dict(id='account-a',live_enabled=True)
            folder=Path(self.temp.name)
            master=Master()
            import threading
            lock=threading.RLock()
            def _client(inner):return self.client
            def execution_allowed(inner):return True
            def egress(inner):return '127.0.0.1'
            def _submission_lock(inner):return nullcontext()
        self.service=Service();self.broker=Broker(self.service,lambda:self.now)
        self.order=self.broker.order('NSE_FNO:1',25,1,dict(bid=9.95,ask=10));self.order['orderTag']='EC-test'

    def test_bull_call_bear_put(self):
        self.assertEqual(self.broker.resolve(dict(underlying='NSE:NIFTY'),'BULLISH')['option_type'],'CE')
        self.assertEqual(self.broker.resolve(dict(underlying='NSE:NIFTY'),'BEARISH')['option_type'],'PE')

    def test_missing_contract_no_fallback(self):
        self.rows.pop()
        with self.assertRaises(ValueError):self.broker.resolve(dict(underlying='NSE:NIFTY'),'BEARISH')

    def test_tick_and_lot_validation(self):
        self.assertEqual(self.broker.host_tick_size('NSE:NIFTY'),.05)
        self.assertEqual(self.broker.contract('NSE_FNO:1')['tick_size'],.05)
        for change in (dict(qty=1),dict(qty=25.5),dict(side=0),dict(type=2),dict(validity='DAY'),dict(limitPrice=10.01)):
            with self.assertRaises(ValueError):self.broker.validate_order(dict(self.order,**change))

    def test_account_mismatch_fails_before_order(self):
        self.client.owner='other'
        self.assertEqual(self.broker.place(self.order)['code'],400)
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))

    def test_no_live_gate(self):
        self.service.account=dict(id='account-a',live_enabled=False)
        self.assertEqual(self.broker.place(self.order)['code'],400)
        self.assertEqual(self.client.calls,[])

    def test_owner_bound_positions(self):
        self.client.positions=[dict(dhanClientId='other')]
        with self.assertRaises(PermissionError):self.broker.positions()

    def test_native_limit_ioc_and_no_duplicate(self):
        self.assertEqual(self.broker.place(self.order),dict(s='ok',id='123'))
        payload=[v for m,p,v in self.client.calls if m=='POST' and p=='/orders'][0]
        self.assertEqual((payload['orderType'],payload['validity'],payload['transactionType']),('LIMIT','IOC','BUY'))
        self.assertEqual(self.broker.place(self.order)['code'],400)
        self.assertEqual(sum(m=='POST' and p=='/orders' for m,p,_ in self.client.calls),1)

    def test_unknown_submission_blocks_new_tag(self):
        self.client.fail_submit=True
        self.assertEqual(self.broker.place(self.order)['code'],201)
        self.assertEqual(self.broker.place(dict(self.order,orderTag='another'))['code'],400)
        self.assertEqual(sum(m=='POST' and p=='/orders' for m,p,_ in self.client.calls),1)

    def test_preflight_rejection_is_not_unknown_runner_intent(self):
        from sector_heatmap.dhan_strategy_service import DhanRsiRunner,rsi_config
        runner=DhanRsiRunner(self.broker,Path(self.temp.name)/'known-rejection.json',clock=lambda:self.now)
        config=rsi_config(dict(broker='DHAN',strategy='RSI_BASED_EMA_V1',underlying='NSE:NIFTY',lots='1',timeframe='1 minute',mode='LIVE'))
        runner.state.update(config=config,running=True,accepting_entries=True,trades_used=0,
                            last_signal=dict(timestamp=self.now-60,close=100,cross_direction='BULLISH'))
        position=dict(symbol='NSE_FNO:1',direction='BULLISH',entry_side=1,lot_size=25,quantity=25,
                      quantity_multiplier=1,tick_size=.05,entry_price=None,opened_at=None,entry_signal_timestamp=self.now-60)
        self.service.egress=lambda:'192.0.2.99'
        runner.submit(self.order,position,'RSI_CLOSE_ENTRY')
        self.assertIsNone(runner.state['pending'])
        self.assertEqual(runner.state['status'],'ORDER_REJECTED')
        self.assertFalse(runner.state['running'])
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))

    def test_owned_exit_quantity_required(self):
        sell=self.broker.order('NSE_FNO:1',25,-1,dict(bid=9.95,ask=10))
        self.assertEqual(self.broker.place(dict(sell,orderTag='exit'))['code'],400)
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))

    def test_insufficient_funds(self):
        self.client.balance=10
        with self.assertRaises(ValueError):self.broker.preflight(self.order,{})
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))

    def test_partial_fill_normalization(self):
        r=dict(orderId='1',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',transactionType='BUY',
               productType='MARGIN',quantity=50,filledQty=25,averageTradedPrice=10,orderStatus='PART_TRADED',correlationId='tag')
        self.client.orders=[r]
        normalized=self.broker.orders()[0]
        self.assertEqual((normalized['status'],normalized['filledQty'],normalized['qty']),(6,25,50))
        r['orderStatus']='NEW_UNKNOWN'
        with self.assertRaises(ValueError):self.broker.orders()

    def test_cancellation_requires_durable_owner(self):
        self.client.orders=[dict(orderId='1',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',
            transactionType='BUY',productType='MARGIN',quantity=25,filledQty=0,averageTradedPrice=0,
            orderStatus='PENDING',correlationId='external')]
        with self.assertRaises(PermissionError):self.broker.cancel('1')
        self.assertFalse(any(m=='DELETE' for m,_,_ in self.client.calls))

    def test_complete_timeframe_aggregation(self):
        rows=self.broker.candles(dict(underlying='NSE:NIFTY',timeframe='3 minutes'))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['volume'],30)
        self.assertFalse(rows[0]['is_forming'])
        self.assertEqual(self.broker.candles(dict(underlying='NSE:NIFTY',timeframe='5 minutes'))[0]['timestamp'],rows[0]['timestamp'])

    def test_incomplete_aggregation_not_synthesized(self):
        self.assertEqual(self.broker.candles(dict(underlying='NSE:NIFTY',timeframe='10 minutes')),[])

    def test_paper_activation_is_owner_bound_and_does_not_submit(self):
        runner=DhanRenkoRunner(self.broker,Path(self.temp.name)/'paper.json',clock=lambda:self.now)
        payload=dict(broker='DHAN',strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',
                     underlying='NSE:NIFTY',timeframe='3 minutes',lots='1',mode='PAPER',
                     configuration_revision=runner.runtime_revision)
        result=runner.activate(payload,background=False)
        self.assertTrue(result['running'])
        self.assertEqual(result['config']['broker'],'DHAN')
        self.assertTrue(result['account_identity'])
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))
        runner.stop()

    def test_live_intent_to_confirmed_fill_uses_dhan_normalization(self):
        from sector_heatmap.dhan_strategy_service import DhanRsiRunner,rsi_config
        runner=DhanRsiRunner(self.broker,Path(self.temp.name)/'fill.json',clock=lambda:self.now)
        config=rsi_config(dict(broker='DHAN',strategy='RSI_BASED_EMA_V1',underlying='NSE:NIFTY',lots='1',timeframe='1 minute',mode='LIVE'))
        runner.state.update(config=config,running=True,accepting_entries=True,trades_used=0,
                            last_signal=dict(timestamp=self.now-60,close=100,cross_direction='BULLISH'))
        self.broker.authenticated_client()
        position=dict(symbol='NSE_FNO:1',direction='BULLISH',entry_side=1,lot_size=25,quantity=25,
                      quantity_multiplier=1,tick_size=.05,entry_price=None,opened_at=None,entry_signal_timestamp=self.now-60)
        runner.submit(self.order,position,'RSI_CLOSE_ENTRY')
        pending=runner.state['pending']
        self.assertIsNotNone(pending);self.assertIsNone(runner.state['position'])
        self.client.orders=[dict(orderId='123',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',
            transactionType='BUY',productType='MARGIN',quantity=25,filledQty=25,averageTradedPrice=10,
            orderStatus='TRADED',correlationId=pending['tag'])]
        self.client.positions=[dict(dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',netQty=25,costPrice=10,productType='MARGIN')]
        runner.reconcile()
        self.assertIsNone(runner.state['pending']);self.assertEqual(runner.state['position']['quantity'],25)
        self.assertEqual(runner.state['position']['entry_price'],10)
        self.assertEqual(runner.state['order_history'][-1]['requested_type'],'LIMIT')

    def test_renko_live_route_with_fake_broker(self):
        runner=DhanRenkoRunner(self.broker,Path(self.temp.name)/'fill.json',clock=lambda:self.now)
        config=renko_configuration(dict(broker='DHAN',strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',underlying='NSE:NIFTY',lots='1',timeframe='1 minute',mode='LIVE'))
        runner.state.update(config=config,running=True,accepting_entries=True,trades_used=0,
                            last_signal=dict(timestamp=self.now-60,close=100,cross_direction='BULLISH'))
        self.broker.authenticated_client()
        position=dict(symbol='NSE_FNO:1',direction='BULLISH',entry_side=1,lot_size=25,quantity=25,
                      quantity_multiplier=1,tick_size=.05,entry_price=None,opened_at=None,entry_signal_timestamp=self.now-60)
        from unittest.mock import patch
        runner.state['renko_engine']={'anchor':{},'last':{'host_atr':1}}
        with patch('strategies.renko_supertrend.runner.ema_exit_observation',return_value=dict(entry_qualified=True,entry_direction='BULLISH',ema10=100)):
            runner.submit(self.order,position,'CONFIRMED_ENTRY')
        pending=runner.state['pending']
        self.assertIsNotNone(pending);self.assertIsNone(runner.state['position'])
        self.client.orders=[dict(orderId='123',dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',
            transactionType='BUY',productType='MARGIN',quantity=25,filledQty=25,averageTradedPrice=10,
            orderStatus='TRADED',correlationId=pending['tag'])]
        self.client.positions=[dict(dhanClientId='owner',exchangeSegment='NSE_FNO',securityId='1',netQty=25,costPrice=10,productType='MARGIN')]
        runner.reconcile()
        self.assertIsNone(runner.state['pending']);self.assertEqual(runner.state['position']['quantity'],25)
        self.assertEqual(runner.state['position']['entry_price'],10)
        self.assertEqual(runner.state['order_history'][-1]['requested_type'],'LIMIT')

    def test_renko_paper_fill_has_dhan_costs_and_no_broker_order(self):
        runner=DhanRenkoRunner(self.broker,Path(self.temp.name)/'paper-fill.json',clock=lambda:self.now)
        config=renko_configuration(dict(broker='DHAN',strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY',lots='1',timeframe='1 minute',mode='PAPER',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',sideways_enabled=True,retest_enabled=True))
        runner.state.update(config=config,running=True,accepting_entries=True,trades_used=0,
                            last_signal=dict(timestamp=self.now-60,close=100,entry_direction='BULLISH'))
        self.broker.authenticated_client()
        position=dict(symbol='NSE_FNO:1',direction='BULLISH',entry_side=1,lot_size=25,quantity=25,
                      quantity_multiplier=1,tick_size=.05,entry_price=None,opened_at=None,entry_signal_timestamp=self.now-60)
        from unittest.mock import patch
        runner.state['renko_engine']={'anchor':{},'last':{'host_atr':1}}
        with patch('strategies.renko_supertrend.runner.ema_exit_observation',return_value=dict(entry_qualified=True,entry_direction='BULLISH',ema10=100)):
            runner.submit(self.order,position,'EMA10_RETEST_BOUNCE')
        self.assertIsNotNone(runner.state['position'])
        row=runner.state['order_history'][-1]
        self.assertEqual(row['broker'],'DHAN');self.assertEqual(row['dhan_exchange_rate'],.000355299)
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))
        held=runner.state['position']
        held['exposure_range'].update(high=101,low=99,ticks=2)
        self.now+=60;self.client.now=self.now
        exit_order=self.broker.order(held['symbol'],held['quantity'],-1,dict(bid=9.95,ask=10))
        runner.submit(exit_order,held,'OPPOSITE_CONFIRMED_SIGNAL')
        self.assertIsNone(runner.state['position'])
        self.assertTrue(runner.state['sideways_lock']['active'])
        self.assertLess(runner.state['sideways_lock']['realized_pnl'],0)
        self.assertFalse(runner.sideways_entry_gate())
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))
        runner.state.update(running=False,accepting_entries=False)

    def test_dhan_retest_and_sideways_settings_persist_without_activation(self):
        path=Path(self.temp.name)/'settings-state.json'
        r=DhanRenkoRunner(self.broker,path,clock=lambda:self.now)
        values={'retest-enabled':True,'retest-engulfing':True,'retest-harami':False,'retest-star':False,'sideways-enabled':True,'sideways-max-candles':2}
        r.save_preferences({'settings':values})
        restored=DhanRenkoRunner(self.broker,path,clock=lambda:self.now)
        for key,value in values.items():self.assertEqual(restored.read_preferences()['settings'][key],value)
        self.assertFalse(restored.state['running'])
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))

    def test_restored_runner_stays_stopped(self):
        path=Path(self.temp.name)/'state.json'
        path.write_text(json.dumps(dict(schema=1,seen=[],running=True,accepting_entries=True,position=None,pending=None)))
        self.assertFalse(DhanRenkoRunner(self.broker,path,clock=lambda:self.now).state['running'])


if __name__=='__main__':unittest.main()
