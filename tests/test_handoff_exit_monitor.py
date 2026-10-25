import unittest,tempfile
from pathlib import Path
from copy import deepcopy
from sector_heatmap.handoff_exit_monitor import Store,Monitor

class Fake:
    def __init__(self):
        self.now=100.;self.calls=[];self.price=100.;self.connected=True;self.stale=False;self.open=True;self.timeout=False;self.race=False
        self.parent=dict(id='P1',symbol='NSE:TEST26OCT100PE',productType='MARGIN',qty=50,filledQty=50,remainingQuantity=0,status=2,side=1,tradedPrice=100,stopLoss=10,takeProfit=10)
        self.pos=dict(id='NSE:TEST26OCT100PE-MARGIN',symbol=self.parent['symbol'],productType='MARGIN',netQty=50,stopLoss=10,takeProfit=10)
        self.orders=[self.parent];self.positions=[self.pos]
    def allowed(self,p):return True
    def entry_result(self,p):return None
    def subscribe(self,s):pass
    def session_open(self):return self.open
    def quote(self,s):return dict(price=self.price,provider_at=self.now-(10 if self.stale else 0),received_at=self.now,connected=self.connected)
    def snapshot(self):return deepcopy(dict(orders=self.orders,positions=self.positions))
    def cancel_entry(self,r):
        self.calls.append('cancel_entry');self.parent.update(status=1,remainingQuantity=0);return dict(s='ok',code=1103)
    def detach(self,r,p,parent):
        self.calls.append('detach')
        if self.timeout:raise TimeoutError()
        self.parent.update(stopLoss=None,takeProfit=None);self.pos.update(stopLoss=None,takeProfit=None)
        if self.race:
            self.positions=[];self.orders.append(dict(id='CHILD',symbol=self.parent['symbol'],productType='MARGIN',parentId='P1',side=-1,qty=50,filledQty=50,status=2,tradedPrice=110))
        return dict(s='ok',code=1102)
    def exit_position(self,r,p):
        self.calls.append(('exit',p['id']))
        if self.timeout:raise TimeoutError()
        self.positions=[];return dict(s='ok',code=200)
    def release(self,r):self.calls.append('release')
    def close(self):pass

class ExitMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name));self.store.authorize('A','U',at=1);self.b=Fake();self.m=Monitor(self.store,self.b,clock=lambda:self.b.now)
        self.r=dict(id='f'*64,symbol=self.b.parent['symbol'],underlying='NSE:TEST-EQ',product='MARGIN',quantity=50,side=1,stop=90,target=110,entry_id='P1',state='ENTRY_PENDING',actions={});self.store.save(self.r)
    def tearDown(self):self.tmp.cleanup()
    def row(self):return self.store.rows()[0]
    def step(self):self.m.cycle();return self.row()
    def test_no_trigger_no_mutations(self):self.assertEqual(self.step()['state'],'MONITORING');self.assertEqual(self.b.calls,[])
    def test_target_then_detach_verified_then_exact_position_exit(self):
        self.b.price=110;self.assertEqual(self.step()['state'],'DETACHING');self.assertEqual(self.b.calls,['detach']);self.step();self.assertEqual(self.b.calls[-1],('exit',self.b.pos['id']));self.assertEqual(self.step()['state'],'CLOSED');self.assertEqual(self.b.calls.count(('exit',self.b.pos['id'])),1)
    def test_stop_for_bought_put_is_premium_decrease(self):self.b.price=90;self.assertEqual(self.step()['trigger'],'STOP_LOSS')
    def test_short_equity_trigger_direction(self):
        self.r.update(side=-1,stop=110,target=90);self.b.parent['side']=-1;self.b.pos['netQty']=-50;self.store.save(self.r);self.b.price=90;self.assertEqual(self.step()['trigger'],'TARGET')
    def test_partial_fill_cancel_remaining_before_exit(self):
        self.b.parent.update(status=6,filledQty=20,remainingQuantity=30);self.b.pos['netQty']=20;self.b.price=90
        self.assertEqual(self.step()['state'],'CANCELLING_ENTRY');self.assertEqual(self.b.calls,['cancel_entry']);self.step();self.step();self.assertIn(('exit',self.b.pos['id']),self.b.calls)
    def test_cancel_race_full_fill_reconciles_quantity(self):
        self.b.parent.update(status=6,filledQty=20,remainingQuantity=30);self.b.pos['netQty']=20;self.b.price=90;self.step();self.b.parent.update(status=2,filledQty=50,remainingQuantity=0);self.b.pos['netQty']=50;self.step();self.step();self.assertIn(('exit',self.b.pos['id']),self.b.calls)
    def test_native_exit_wins_handover_no_second_exit(self):
        self.b.price=110;self.b.race=True;self.step();r=self.step();self.assertEqual(r['state'],'CLOSED');self.assertEqual(r['gross_realized_pnl'],500);self.assertFalse(any(isinstance(x,tuple) for x in self.b.calls))
    def test_detach_timeout_is_not_replayed(self):
        self.b.price=90;self.b.timeout=True;self.step();self.step();self.step();self.assertEqual(self.b.calls,['detach']);self.assertEqual(self.row()['state'],'REVIEW')
    def test_exit_timeout_is_not_replayed_after_restart(self):
        self.b.price=90;self.step();self.b.timeout=True;self.step();self.m=Monitor(Store(self.tmp.name),self.b,clock=lambda:self.b.now);self.step();self.step();self.assertEqual(sum(isinstance(x,tuple) for x in self.b.calls),1);self.assertEqual(self.row()['state'],'UNCERTAIN')
    def test_stale_or_disconnected_price_never_triggers(self):
        self.b.price=90;self.b.stale=True;self.assertEqual(self.step()['state'],'PRICE_STALE');self.b.stale=False;self.b.connected=False;self.step();self.assertEqual(self.b.calls,[])
    def test_foreign_quantity_blocks_exit(self):self.b.price=90;self.b.pos['netQty']=100;self.assertEqual(self.step()['state'],'REVIEW');self.assertEqual(self.b.calls,[])
    def test_foreign_order_blocks_exit(self):self.b.price=90;self.b.orders.append(dict(self.b.parent,id='OTHER'));self.assertEqual(self.step()['state'],'REVIEW');self.assertEqual(self.b.calls,[])
    def test_existing_child_pending_blocks_takeover(self):
        self.b.price=90;self.b.orders.append(dict(id='CHILD',symbol=self.r['symbol'],productType='MARGIN',parentId='P1',side=-1,status=6,filledQty=0));self.step();self.assertEqual(self.step()['state'],'DETACHING');self.assertEqual(self.b.calls,['detach'])
    def test_broker_position_id_missing_blocks_exit(self):self.b.price=90;self.b.pos.pop('id');self.assertEqual(self.step()['state'],'REVIEW');self.assertEqual(self.b.calls,[])
    def test_market_closed_and_paused_are_observable(self):
        self.b.price=90;self.b.open=False;self.assertEqual(self.step()['state'],'WAITING_SESSION');self.b.open=True;self.store.pause(False);self.assertEqual(self.step()['state'],'PAUSED');self.assertEqual(self.b.calls,[])
    def test_restart_handover_can_continue_without_second_detach(self):
        self.b.price=110;self.step();self.m=Monitor(Store(self.tmp.name),self.b,clock=lambda:self.b.now);self.step();self.assertEqual(self.b.calls.count('detach'),1);self.assertEqual(sum(isinstance(x,tuple) for x in self.b.calls),1)
    def test_after_book_day_rollover_persisted_fill_is_required(self):
        self.step();self.b.orders=[];self.b.price=90;self.assertEqual(self.step()['state'],'DETACHING')
    def test_unfilled_order_never_exits(self):self.b.parent.update(status=6,filledQty=0,remainingQuantity=50);self.b.positions=[];self.b.price=90;self.assertEqual(self.step()['state'],'ENTRY_PENDING');self.assertEqual(self.b.calls,[])

    def test_unfilled_limit_is_cancelled_if_underlying_condition_ceases(self):
        from sector_heatmap.handoff_entry_conditions import condition
        self.r.update(entry_condition=condition('NSE:TEST-EQ','BULLISH',100),entry_order={'type':'LIMIT'},created_at=90)
        self.store.save(self.r);self.b.parent.update(status=6,filledQty=0,remainingQuantity=50);self.b.positions=[];self.b.price=99
        self.assertEqual(self.step()['state'],'CANCELLING_ENTRY');self.assertEqual(self.b.calls,['cancel_entry'])
    def test_unfilled_cash_stop_limit_waits_below_trigger_without_cancellation(self):
        from sector_heatmap.handoff_entry_conditions import condition
        self.r.update(entry_condition=condition('NSE:TEST-EQ','BULLISH',100),entry_order={'type':'STOP_LIMIT'},created_at=90)
        self.store.save(self.r);self.b.parent.update(status=6,filledQty=0,remainingQuantity=50);self.b.positions=[];self.b.price=99
        self.assertEqual(self.step()['state'],'ENTRY_PENDING');self.assertEqual(self.b.calls,[])

    def test_registered_corrected_product_receipt_to_trigger_exit_and_flat(self):
        import sqlite3,json
        from sector_heatmap.handoff_entry_conditions import condition
        key='e'*64;folder=Path(self.tmp.name)
        with self.store.db() as d:d.execute('DELETE FROM trades')
        plan=dict(symbol=self.b.parent['symbol'],underlying='NSE:TEST-EQ',kind='LONG_OPTION',direction='BEARISH',quantity=50,entry=100,stop=90,target=110,entry_condition=condition('NSE:TEST-EQ','BEARISH',100),ticket_payload={'handoff_auto':True,'analysis_evidence':{'source':'ANALYSIS_HANDOFF'}})
        receipt=dict(plan=plan,result={'order_ids':['P1'],'actual_product':'INTRADAY','product_attempts':[{'status':'REJECTED','order_ids':['REJECTED_ORIGINAL']}]})
        with sqlite3.connect(folder/'handoff-schedule.sqlite3') as d:d.execute('CREATE TABLE receipts(fingerprint TEXT,state TEXT,body TEXT)');d.execute('INSERT INTO receipts VALUES(?,?,?)',(key,'PROTECTED',json.dumps(receipt)))
        (folder/'handoff-intents').mkdir();(folder/'handoff-intents'/(key+'.json')).write_text(json.dumps(dict(account_id='A',created=2,preview_id='PREVIEW')))
        self.b.parent['productType']='INTRADAY';self.b.pos.update(productType='INTRADAY',id=self.b.parent['symbol']+'-INTRADAY')
        self.assertEqual(self.step()['product'],'INTRADAY');self.b.price=110;self.step();self.step();self.assertEqual(self.step()['state'],'CLOSED');self.assertEqual(sum(isinstance(x,tuple) for x in self.b.calls),1);self.assertIn('release',self.b.calls)

    def test_uncertain_entry_identity_is_visible_and_never_guessed_or_exited(self):
        import sqlite3,json
        folder=Path(self.tmp.name);key='a'*64
        with self.store.db() as d:d.execute('DELETE FROM trades')
        plan=dict(symbol=self.b.parent['symbol'],underlying='NSE:TEST-EQ',kind='LONG_OPTION',direction='BEARISH',quantity=50,entry=100,stop=90,target=110,ticket_payload={'handoff_auto':True,'analysis_evidence':{'source':'ANALYSIS_HANDOFF'}})
        with sqlite3.connect(folder/'handoff-schedule.sqlite3') as d:d.execute('CREATE TABLE receipts(fingerprint TEXT,state TEXT,body TEXT)');d.execute('INSERT INTO receipts VALUES(?,?,?)',(key,'UNKNOWN',json.dumps(dict(plan=plan,result={'order_ids':[]}))))
        (folder/'handoff-intents').mkdir();(folder/'handoff-intents'/(key+'.json')).write_text(json.dumps(dict(account_id='A',created=2,preview_id='PREVIEW')))
        self.assertEqual(self.step()['state'],'REVIEW');self.assertIsNone(self.row()['entry_id']);self.step();self.assertEqual(self.b.calls,[]);self.assertEqual(self.store.status()['heartbeat']['state'],'ATTENTION_REQUIRED')

    def test_manual_handoff_receipt_is_never_adopted(self):
        import sqlite3,json
        folder=Path(self.tmp.name);key='b'*64
        with self.store.db() as d:d.execute('DELETE FROM trades')
        plan=dict(symbol=self.b.parent['symbol'],underlying='NSE:TEST-EQ',kind='LONG_OPTION',direction='BEARISH',quantity=50,entry=100,stop=90,target=110,ticket_payload={'analysis_evidence':{'source':'ANALYSIS_HANDOFF'}})
        with sqlite3.connect(folder/'handoff-schedule.sqlite3') as d:d.execute('CREATE TABLE receipts(fingerprint TEXT,state TEXT,body TEXT)');d.execute('INSERT INTO receipts VALUES(?,?,?)',(key,'PROTECTED',json.dumps(dict(plan=plan,result={'order_ids':['P1']}))))
        (folder/'handoff-intents').mkdir();(folder/'handoff-intents'/(key+'.json')).write_text(json.dumps(dict(account_id='A',created=2,preview_id='PREVIEW')))
        self.m.cycle();self.assertEqual(self.store.rows(),[]);self.assertEqual(self.b.calls,[])
