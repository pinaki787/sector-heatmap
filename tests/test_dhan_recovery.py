import unittest
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from pathlib import Path
import hashlib
from sector_heatmap.dhan_recovery import external_close_evidence

class ExternalCloseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.position=dict(symbol='NSE_FNO:1',quantity=25,entry_side=1,entry_price=10,entry_order_id='entry')
        self.pending=dict(id=None,tag='unsent',order=dict(side=-1,symbol='NSE_FNO:1'))
        self.history=[dict(order_id='entry',mode='LIVE',side='BUY',symbol='NSE_FNO:1',filled=25)]
        common=dict(exchangeSegment='NSE_FNO',securityId='1',productType='MARGIN')
        self.rows={
            '/positions':[{**common,'netQty':0}],
            '/orders':[{**common,'orderId':'exit','transactionType':'SELL','orderStatus':'TRADED'}],
            '/trades':[
                {**common,'orderId':'entry','transactionType':'BUY','tradedQuantity':25,'tradedPrice':10,'exchangeTime':'2026-10-13 10:00:00','exchangeTradeId':'a'},
                {**common,'orderId':'exit','transactionType':'SELL','tradedQuantity':25,'tradedPrice':12,'exchangeTime':'2026-10-13 10:10:00','exchangeTradeId':'b'}]}
        self.broker=SimpleNamespace(service=SimpleNamespace(folder=Path(self.tmp.name)),_account_rows=lambda path:self.rows[path])
    def evidence(self):return external_close_evidence(self.broker,self.position,self.pending,self.history)
    def test_exact_external_close(self):
        e=self.evidence();self.assertEqual(e['price'],12);self.assertEqual(e['exit_order_id'],'exit')
    def test_durable_intent_blocks(self):
        folder=Path(self.tmp.name)/'dhan-strategy-intents';folder.mkdir()
        (folder/(hashlib.sha256(b'unsent').hexdigest()+'.json')).write_text('{}')
        with self.assertRaisesRegex(ValueError,'Durable submission'):self.evidence()
    def test_outstanding_exposure_blocks(self):
        self.rows['/positions'][0]['netQty']=25
        with self.assertRaisesRegex(ValueError,'still has exposure'):self.evidence()
    def test_intervening_entry_blocks(self):
        self.rows['/trades'][1]['transactionType']='BUY'
        with self.assertRaisesRegex(ValueError,'Intervening'):self.evidence()
    def test_partial_exit_blocks(self):
        self.rows['/trades'][1]['tradedQuantity']=20
        with self.assertRaisesRegex(ValueError,'exactly match'):self.evidence()
    def test_other_contract_not_used(self):
        self.rows['/trades'][1]['securityId']='2'
        with self.assertRaises(ValueError):self.evidence()
    def test_paper_entry_not_used(self):
        self.history[0]['mode']='PAPER'
        with self.assertRaisesRegex(ValueError,'ownership'):self.evidence()
    def test_duplicate_trade_rejected(self):
        self.rows['/trades'][1]['exchangeTradeId']='a'
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.evidence()
    def test_entry_price_mismatch(self):
        self.position['entry_price']=9
        with self.assertRaisesRegex(ValueError,'entry price'):self.evidence()
    def test_pending_broker_order_blocks(self):
        self.rows['/orders'][0]['orderStatus']='PENDING'
        with self.assertRaisesRegex(ValueError,'outstanding'):self.evidence()

    def test_recovery_archives_exact_fills_without_order_or_rearm(self):
        from sector_heatmap.dhan_recovery import reconcile_external_close
        from threading import RLock
        from copy import deepcopy
        entry=self.history[0]
        entry.update(requested=25,tag='owned-entry',lifecycle_id='owned-life')
        state=dict(config={'mode':'LIVE'},position=self.position,pending=self.pending,
                   order_history=self.history,run_id='run-a',running=False,
                   realized_pnl=0,losses={},accepting_entries=False)
        runner=SimpleNamespace(state=state,lock=RLock(),thread=None,adapter=self.broker,clock=lambda:123,
            event=lambda code,message:state.update(status=code,message=message),snapshot=lambda:deepcopy(state))
        result=reconcile_external_close(runner,{'run_id':'run-a'})
        self.assertIsNone(result['position']);self.assertIsNone(result['pending'])
        self.assertFalse(result['running']);self.assertFalse(result['accepting_entries'])
        self.assertFalse(result['rearm_after_exit']);self.assertEqual(result['realized_pnl'],50)
        self.assertEqual(result['order_history'][-1]['reason'],'EXTERNAL_BROKER_CLOSE')
        self.assertEqual(len(result['external_reconciliations']),1)
        with self.assertRaises(ValueError):reconcile_external_close(runner,{'run_id':'run-a'})

    def test_active_runner_cannot_be_reconciled(self):
        from sector_heatmap.dhan_recovery import reconcile_external_close
        from threading import RLock
        runner=SimpleNamespace(state={'running':True},lock=RLock(),thread=None)
        with self.assertRaisesRegex(ValueError,'Stop monitoring'):
            reconcile_external_close(runner,{})

    def test_other_process_lock_prevents_recovery(self):
        import fcntl
        from threading import RLock
        from sector_heatmap.dhan_recovery import reconcile_external_close
        path=Path(self.tmp.name)/'state.json'
        lock=open(path.with_suffix('.lock'),'a')
        self.addCleanup(lock.close);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        runner=SimpleNamespace(path=path,file_lock=None,lock=RLock(),state={},thread=None)
        with self.assertRaisesRegex(ValueError,'Another process'):
            reconcile_external_close(runner,{})

class UnfilledHistoryRegression(unittest.TestCase):
    def test_unsubmitted_exit_without_price_does_not_break_closed_trade(self):
        from strategies.ema_crossover.history import position_history
        base=dict(mode='LIVE',strategy='RENKO',lifecycle_id='owned',symbol='NSE_FNO:1',quantity_multiplier=1,lot_size=65,requested=65)
        rows=[dict(base,side='BUY',filled=65,average_price=20.7),dict(base,side='SELL',filled=0,average_price=None),dict(base,side='SELL',filled=65,average_price=28.2)]
        trade=position_history(rows)[0]
        self.assertEqual(trade['status'],'CLOSED')
        self.assertAlmostEqual(trade['realized_pnl'],487.5)
