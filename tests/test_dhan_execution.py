import csv
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from sector_heatmap.dhan_execution import DhanExecutionService, DhanMaster, IST
from sector_heatmap.fyers_execution import PreviewChanged
from sector_heatmap.workspaces import WorkspaceStore, isolated_environment
from sector_heatmap.workspace_guard import WorkspaceGuard


class FakeMaster:
    def resolve(self,payload,now):
        return dict(security_id=str(payload.get('security_id','2885')),exchange_segment=payload.get('exchange_segment','NSE_EQ'),symbol='RELIANCE',lot_size=1,tick_size=.05,option_type='',expiry='',kind=(payload.get('proposal') or {}).get('kind','NATIVE'))


class FakeClient:
    client_id='10001'
    def __init__(self,now):
        self.now=now;self.calls=[];self.price=100;self.profile_id='10001';self.cash=100000;self.margin=1000
        self.orders=[];self.positions=[];self.unknown=False;self.ip='187.126.123.18';self.data_plan='Active';self.stale=False
        self.ack='PENDING';self.external=None
    def request(self,method,path,payload=None):
        self.calls.append((method,path,deepcopy(payload)))
        if path=='/profile':return dict(dhanClientId=self.profile_id,dataPlan=self.data_plan)
        if path=='/ip/getIP':return dict(primaryIP=self.ip)
        if path=='/marketfeed/quote':
            segment,ids=next(iter(payload.items()));stamp=self.now()-timedelta(minutes=10) if self.stale else self.now()
            return {'data':{segment:{str(ids[0]):{'last_trade_time':stamp.strftime('%d/%m/%Y %H:%M:%S'),'depth':{'buy':[{'price':self.price-.1}],'sell':[{'price':self.price}]}}}}}
        if path=='/fundlimit':return dict(dhanClientId='10001',availabelBalance=self.cash)
        if path=='/positions':return deepcopy(self.positions)
        if path=='/orders' and method=='GET':return deepcopy(self.orders)
        if path=='/super/orders' and method=='GET':
            if self.external is not None:
                sent=next(c for c in reversed(self.calls) if c[0]=='POST' and c[1]=='/super/orders')
                return [{**self.external,'correlationId':sent[2]['correlationId']}]
            return deepcopy(self.orders)
        if path=='/margincalculator':return dict(totalMargin=self.margin,insufficientBalance=0)
        if path.startswith('/orders/external/'):
            if self.external is None:raise RuntimeError('No matching order')
            return {**self.external,'correlationId':path.split('/')[-1]}
        if path in ('/orders','/super/orders') and method=='POST':
            if self.unknown:raise RuntimeError('Timed out')
            result=dict(orderId=str(len(self.orders)+1),orderStatus=self.ack)
            self.orders.append({**payload,**result});return result
        raise AssertionError((method,path))


class DhanExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.clock=datetime(2026,10,12,10,0,tzinfo=IST)
        self.account=dict(id='a'*32,broker='DHAN',label='Owner Dhan',account_ref='10001',live_enabled=False)
        (self.root/'credentials.json').write_text(json.dumps(dict(DHAN_CLIENT_ID='10001',DHAN_ACCESS_TOKEN='fake-test-token')))
        self.client=FakeClient(lambda:self.clock)
        self.service=DhanExecutionService(self.account,self.root,client_factory=lambda _:self.client,master=FakeMaster(),now=lambda:self.clock,egress=lambda:'187.126.123.18')
        self.payload=dict(broker='DHAN',account_id=self.account['id'],security_id='2885',exchange_segment='NSE_EQ',transaction_type='BUY',quantity=10,invalidation=95,target_price=110)
    def test_cash_entry_sends_native_linked_protection(self):
        self.live()
        preview=self.service.prepare(self.payload)
        self.assertEqual(preview['order_route'],'SUPER')
        self.assertEqual(preview['ticket']['stopLossPrice'],95)
        self.assertEqual(preview['ticket']['targetPrice'],110)
        result=self.service.submit(preview['preview_id'],preview['confirmation_phrase'])
        sent=self.sent()
        self.assertEqual(sent[0][1],'/super/orders')
        self.assertEqual(sent[0][2]['stopLossPrice'],95)
        self.assertEqual(sent[0][2]['targetPrice'],110)
        self.assertFalse(result['protection_confirmed'])

    def test_cash_short_protection_and_missing_target(self):
        p=self.service.prepare({**self.payload,'transaction_type':'SELL','invalidation':105,'target_price':90})
        self.assertEqual(p['ticket']['stopLossPrice'],105)
        self.assertEqual(p['ticket']['targetPrice'],90)
        with self.assertRaises(ValueError):self.service.prepare({**self.payload,'target_price':None})
        self.assertEqual(self.sent(),[])

    def test_token_rotation_reloads_existing_service_without_order(self):
        from sector_heatmap.dhan_execution import DhanClient
        self.service.client_factory=DhanClient
        before=self.service._client()
        (self.root/'credentials.json').write_text(json.dumps(dict(DHAN_CLIENT_ID='10001',DHAN_ACCESS_TOKEN='renewed-token')))
        after=self.service._client()
        self.assertIsNot(before,after)
        self.assertEqual(after.headers['access-token'],'renewed-token')
        self.assertEqual(before.headers['access-token'],'fake-test-token')
        self.assertEqual(self.client.orders,[])

    def test_status_requests_reauthentication_only_for_auth_failure(self):
        from unittest.mock import patch
        from sector_heatmap.dhan_execution import DhanAPIError
        with patch.object(self.client,'request',side_effect=DhanAPIError('Sign in',True,True)):
            result=self.service.status()
            self.assertFalse(result['authenticated'])
            self.assertTrue(result['reauthentication_required'])
        with patch.object(self.client,'request',side_effect=DhanAPIError('Permission denied',True)):
            with self.assertRaises(DhanAPIError):self.service.status()

    def tearDown(self):self.tmp.cleanup()
    def sent(self):return [c for c in self.client.calls if c[0]=='POST' and c[1] in ('/orders','/super/orders')]
    def live(self):self.service.account['live_enabled']=True
    def test_preview_is_read_only_and_private(self):
        preview=self.service.prepare(self.payload)
        self.assertEqual(preview['broker'],'DHAN');self.assertEqual(preview['account_id'],self.account['id'])
        self.assertFalse(preview['live_submission_enabled']);self.assertEqual(self.sent(),[])
        self.assertNotIn('fake-test-token',json.dumps(preview));self.assertEqual(preview['ticket']['quantity'],10)
    def test_owner_and_broker_cannot_change(self):
        for update in (dict(account_id='b'*32),dict(broker='FYERS')):
            with self.assertRaises((PermissionError,ValueError)):self.service.prepare({**self.payload,**update})
        self.client.profile_id='99999'
        with self.assertRaises(PermissionError):self.service.prepare(self.payload)
        self.assertEqual(self.sent(),[])
    def test_live_gate_and_exact_confirmation(self):
        p=self.service.prepare(self.payload)
        with self.assertRaises(PermissionError):self.service.submit(p['preview_id'],p['confirmation_phrase'])
        self.live()
        with self.assertRaises(ValueError):self.service.submit(p['preview_id'],'yes')
        self.assertEqual(self.sent(),[])
    def test_expired_preview(self):
        self.live();p=self.service.prepare(self.payload);self.clock+=timedelta(minutes=3)
        with self.assertRaises(ValueError):self.service.submit(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(self.sent(),[])
    def test_changed_price_replaces_preview_without_submission(self):
        self.live();p=self.service.prepare(self.payload);self.client.price=101
        with self.assertRaises(PreviewChanged):self.service.submit(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(self.sent(),[])
    def test_submit_ack_is_not_fill_and_cannot_repeat(self):
        self.live();p=self.service.prepare(self.payload);result=self.service.submit(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(result['status'],'PENDING');self.assertEqual(len(self.sent()),1)
        with self.assertRaises(ValueError):self.service.submit(p['preview_id'],p['confirmation_phrase'])
        with self.assertRaises(ValueError):self.service.prepare(self.payload)
        journal=next((self.root/'dhan-orders').glob('*.json'));self.assertEqual(journal.stat().st_mode&0o777,0o600)
    def test_unknown_submission_blocks_new_tickets_until_reconciled(self):
        self.live();self.client.unknown=True;p=self.service.prepare(self.payload)
        self.assertEqual(self.service.submit(p['preview_id'],p['confirmation_phrase'])['status'],'UNKNOWN')
        with self.assertRaisesRegex(ValueError,'uncertain'):self.service.prepare(self.payload)
        self.assertEqual(len(self.sent()),1)
        self.client.external=dict(orderId='1',dhanClientId='10001',orderStatus='REJECTED')
        self.assertEqual(self.service.reconcile()['unresolved'],0)
        self.service.prepare(self.payload)
    def test_reconciliation_rejects_different_owner(self):
        self.live();self.client.unknown=True;p=self.service.prepare(self.payload);self.service.submit(p['preview_id'],p['confirmation_phrase'])
        self.client.external=dict(orderId='1',dhanClientId='99999',orderStatus='REJECTED')
        self.assertEqual(self.service.reconcile()['unresolved'],1)
    def test_bad_static_ip_data_plan_and_stale_quote(self):
        for attr,value in (('ip','192.0.2.1'),('data_plan','Deactive')):
            old=getattr(self.client,attr);setattr(self.client,attr,value)
            with self.assertRaises(ValueError):self.service.prepare(self.payload)
            setattr(self.client,attr,old)
        self.assertEqual(self.sent(),[])
    def test_funds_risk_stop_and_products_fail_closed(self):
        for update in (dict(quantity=1000),dict(quantity=1.2),dict(quantity=0),dict(invalidation=105),dict(product_type='MTF'),dict(order_type='MARKET'),dict(transaction_type='SELL',product_type='CNC'),dict(idea_risk_limit='NaN')):
            with self.subTest(update=update),self.assertRaises(ValueError):self.service.prepare({**self.payload,**update})
        self.client.cash=1
        with self.assertRaises(ValueError):self.service.prepare(self.payload)
        self.assertEqual(self.sent(),[])
    def test_pending_order_and_existing_position_block_duplicate(self):
        self.client.orders=[dict(dhanClientId='10001',securityId='2885',exchangeSegment='NSE_EQ',orderStatus='PENDING')]
        with self.assertRaises(ValueError):self.service.prepare(self.payload)
        self.client.orders=[];self.client.positions=[dict(dhanClientId='10001',securityId='2885',exchangeSegment='NSE_EQ',netQty=1)]
        with self.assertRaises(ValueError):self.service.prepare(self.payload)
    def test_account_wide_process_lock(self):
        other=DhanExecutionService(self.account,self.root)
        with self.service._submission_lock():
            with self.assertRaises(PermissionError):
                with other._submission_lock():pass
    def test_batch_has_combined_risk_and_distinct_contracts(self):
        other={**self.payload,'security_id':'11536'}
        preview=self.service.prepare_batch({'items':[self.payload,other]})
        self.assertEqual(preview['aggregate']['order_count'],2);self.assertEqual(self.sent(),[])
        with self.assertRaises(ValueError):self.service.prepare_batch({'items':[self.payload,self.payload]})
        with self.assertRaises(PermissionError):self.service.prepare_batch({'items':[self.payload,{**other,'account_id':'b'*32}]})
        with self.assertRaises(PermissionError):self.service.prepare_batch({'items':[{**self.payload,'broker':'FYERS'}]})
    def test_batch_submit_stops_on_uncertain_result(self):
        self.live();self.client.unknown=True;p=self.service.prepare_batch({'items':[self.payload,{**self.payload,'security_id':'11536'}]})
        result=self.service.submit_batch(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(result['status'],'PARTIAL');self.assertEqual(len(self.sent()),1)
    def test_batch_submits_exact_reviewed_orders(self):
        self.live();p=self.service.prepare_batch({'items':[self.payload,{**self.payload,'security_id':'11536'}]})
        result=self.service.submit_batch(p['preview_id'],p['confirmation_phrase'])
        self.assertEqual(result['status'],'ACKNOWLEDGED');self.assertEqual(len(self.sent()),2)
        self.assertEqual([c[2]['securityId'] for c in self.sent()],['2885','11536'])
    def test_closed_session(self):
        self.clock=datetime(2026,10,10,10,tzinfo=IST)
        with self.assertRaises(ValueError):self.service.prepare(self.payload)
        self.assertEqual(self.sent(),[])


class DhanAccountTests(unittest.TestCase):
    def test_account_credentials_owned_and_environment_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            store=WorkspaceStore(Path(folder)/'registry.sqlite3')
            admin=store.create_user('admin','administrator-password',bootstrap=True)
            alice=store.create_user('alice','alice-private-password',actor=admin)
            bob=store.create_user('bob','bob-private-password',actor=admin)
            account=store.create_account(alice,'DHAN','Alice Dhan','10001')
            fields=dict(DHAN_CLIENT_ID='10001',DHAN_ACCESS_TOKEN='fake-private-token')
            with self.assertRaises(PermissionError):store.configure(bob,account['id'],fields)
            with self.assertRaises(ValueError):store.configure(alice,account['id'],{**fields,'DHAN_CLIENT_ID':'10002'})
            store.configure(alice,account['id'],fields)
            self.assertNotIn('fake-private-token',json.dumps(store.accounts(alice)))
            env=isolated_environment(account,store.folder(account),store.path,8080)
            self.assertNotIn('DHAN_ACCESS_TOKEN',env);self.assertEqual(env['DHAN_ENABLE_LIVE_ORDERS'],'0')
            env=isolated_environment({**account,'live_enabled':True},store.folder(account),store.path,8080)
            self.assertEqual(env['DHAN_ENABLE_LIVE_ORDERS'],'1');self.assertEqual(env['DELTA_INDIA_ENABLE_LIVE_ORDERS'],'0')
            guard=WorkspaceGuard(store,account['id'],account['port'],8080)
            guard.validate_action(account,'/api/dhan/prepare',dict(broker='DHAN'))
            for path in ('/api/renko-supertrend/start','/api/ema-crossover/start','/api/delta-india/submit'):
                with self.assertRaises(PermissionError):guard.validate_action(account,path,{})
    def test_real_master_resolves_security_lot_tick_and_expiry(self):
        now=datetime(2026,10,12,10,tzinfo=IST)
        master=DhanMaster();master.day=now.date()
        master.rows=[dict(SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='E',SEM_SMST_SECURITY_ID='2885',SEM_TRADING_SYMBOL='RELIANCE',SEM_LOT_UNITS='1.0',SEM_TICK_SIZE='10.0000',SEM_EXPIRY_DATE='',SEM_OPTION_TYPE='',SEM_SERIES='EQ')]
        result=master.resolve(dict(underlying='NSE:RELIANCE-EQ',proposal={'kind':'EQUITY'}),now)
        self.assertEqual(result['security_id'],'2885');self.assertEqual(result['tick_size'],.1)
        with self.assertRaises(ValueError):master.resolve(dict(security_id='2885',exchange_segment='BSE_EQ'),now)


class PreviewQuoteRefreshTests(unittest.TestCase):
    def test_old_last_trade_does_not_invalidate_current_depth_snapshot(self):
        from sector_heatmap.dhan_execution import fresh_quote_snapshot
        now = datetime(2026, 10, 13, 12, 0, tzinfo=IST)
        client = FakeClient(lambda: now)
        client.stale = True
        quote, received = fresh_quote_snapshot(client, 'NSE_EQ', '1', lambda: now.timestamp())
        self.assertEqual(received, now.timestamp())
        self.assertTrue(quote['depth']['buy'])
        self.assertEqual(len(client.calls), 1)

    def test_delayed_response_refreshes_once(self):
        from sector_heatmap.dhan_execution import fresh_quote_snapshot
        now = datetime(2026, 10, 13, 12, 0, tzinfo=IST)
        client = FakeClient(lambda: now)
        ticks = iter([0, 20, 20, 21])
        fresh_quote_snapshot(client, 'NSE_EQ', '1', lambda: next(ticks))
        self.assertEqual(len(client.calls), 2)

    def test_persistent_response_delay_fails_after_two_reads(self):
        from sector_heatmap.dhan_execution import fresh_quote_snapshot
        now = datetime(2026, 10, 13, 12, 0, tzinfo=IST)
        client = FakeClient(lambda: now)
        ticks = iter([0, 20, 20, 40])
        with self.assertRaisesRegex(ValueError, 'remained delayed'):
            fresh_quote_snapshot(client, 'NSE_EQ', '1', lambda: next(ticks))
        self.assertEqual(len(client.calls), 2)

    def test_missing_instrument_and_provider_failure_rejected(self):
        from sector_heatmap.dhan_execution import fresh_quote_snapshot
        class Client:
            def request(self, *args): return {'status': 'failure', 'data': {}}
        with self.assertRaisesRegex(ValueError, 'successful'):
            fresh_quote_snapshot(Client(), 'NSE_EQ', '1')

class SubmissionFreshnessTests(unittest.TestCase):
    setUp=DhanExecutionTests.setUp
    tearDown=DhanExecutionTests.tearDown
    def test_last_moment_quote_move_sends_nothing(self):
        preview=self.service.prepare(self.payload)
        self.client.price=102
        with self.assertRaisesRegex(ValueError,'reviewed limit'):
            self.service._send('TEST-NO-ORDER',preview)
        self.assertFalse(any(method=='POST' and path in ('/orders','/super/orders') for method,path,*_ in self.client.calls))
        self.assertFalse((self.root/'dhan-orders'/'TEST-NO-ORDER.json').exists())
    def test_fyers_analysis_cannot_be_submitted_as_dhan(self):
        with self.assertRaisesRegex(PermissionError,'Proposal broker'):
            self.service.prepare(dict(self.payload,proposal={'kind':'LONG_OPTION','source':'ANALYSIS_HANDOFF','broker':'FYERS'}))
        self.assertEqual(self.client.calls,[])

class ProtectedHandoffTests(unittest.TestCase):
    setUp=DhanExecutionTests.setUp
    tearDown=DhanExecutionTests.tearDown
    def test_native_super_order_preview_ack_and_reconciliation(self):
        outer=self
        class Client(FakeClient):
            def request(inner,method,path,payload=None):
                if path=='/marketfeed/quote':
                    segment,ids=next(iter(payload.items()));price=100 if segment=='NSE_EQ' else 10
                    inner.calls.append((method,path,deepcopy(payload)))
                    return {'status':'success','data':{segment:{str(ids[0]):{'last_price':price,'last_trade_time':'01/01/1980 00:00:00',
                        'depth':{'buy':[{'price':price-.05}],'sell':[{'price':price}]}}}}}
                if path=='/super/orders' and method=='POST':
                    inner.calls.append((method,path,deepcopy(payload)));inner.ticket=payload
                    return {'orderId':'super-1','orderStatus':'PENDING'}
                if path=='/super/orders' and method=='GET':
                    return [{'dhanClientId':inner.client_id,'correlationId':inner.ticket['correlationId'],'orderId':'super-1','orderStatus':'TRADED'}]
                return super().request(method,path,payload)
        client=Client(lambda:self.clock)
        self.service.client_factory=lambda values:client
        master=DhanMaster();master.day=self.clock.date()
        master.rows=[
            dict(SEM_SMST_SECURITY_ID='1',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='E',SEM_SERIES='EQ',SEM_TRADING_SYMBOL='TEST',SEM_OPTION_TYPE='XX',SEM_EXPIRY_DATE='',SEM_STRIKE_PRICE='0',SEM_LOT_UNITS='1',SEM_TICK_SIZE='5'),
            dict(SEM_SMST_SECURITY_ID='2',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='D',SEM_SERIES='OPTSTK',SEM_TRADING_SYMBOL='TEST-Oct2026-100-CE',SEM_OPTION_TYPE='CE',SEM_EXPIRY_DATE='2026-10-27',SEM_STRIKE_PRICE='100',SEM_LOT_UNITS='25',SEM_TICK_SIZE='5')]
        self.service.master=master;self.service.account['live_enabled']=True
        payload=dict(broker='DHAN',account_id=self.account['id'],underlying='NSE:TEST-EQ',lots=1,expiry='2026-10-27',invalidation=90,
            underlying_exit_plan={'entry':100,'stop':90,'target':110},proposal={'kind':'LONG_OPTION','source':'ANALYSIS_HANDOFF','broker':'DHAN','direction':'BULLISH','legs':[{'action':'BUY','option_type':'CE','strike':100,'symbol':'NSE_FNO:2'}]})
        preview=self.service.prepare(payload)
        self.assertEqual(preview['order_route'],'SUPER')
        self.assertEqual(preview['ticket']['securityId'],'2')
        result=self.service.submit(preview['preview_id'],preview['confirmation_phrase'])
        self.assertEqual(result['status'],'PENDING')
        self.assertFalse(result['protection_confirmed'])
        self.assertEqual(len([c for c in client.calls if c[:2]==('POST','/super/orders')]),1)
        self.assertFalse(any(c[:2]==('POST','/orders') for c in client.calls))
        reconciled=self.service.reconcile()
        self.assertEqual(reconciled['orders'][0]['status'],'TRADED')
        with self.assertRaises(ValueError):self.service.submit(preview['preview_id'],preview['confirmation_phrase'])


class TransportEvidenceTests(unittest.TestCase):
    def test_quote_throttle_wait_is_not_mistaken_for_response_delay(self):
        from sector_heatmap.dhan_execution import DhanClient,fresh_quote_snapshot
        from unittest.mock import Mock
        client=DhanClient({'DHAN_CLIENT_ID':'test-only','DHAN_ACCESS_TOKEN':'fake'})
        client.request=Mock(return_value={'status':'success','data':{'NSE_EQ':{'1':{'last_price':100}}},
            '_sector_snapshot_timing':{'received_at':100,'elapsed':1}})
        ticks=iter([0,30])
        quote,received=fresh_quote_snapshot(client,'NSE_EQ','1',lambda:next(ticks))
        self.assertEqual(received,100)
        self.assertEqual(client.request.call_count,1)

    def test_rate_limited_submission_is_never_retried_by_transport(self):
        from sector_heatmap.dhan_execution import DhanClient
        from unittest.mock import Mock,patch
        client=DhanClient({'DHAN_CLIENT_ID':'test-only','DHAN_ACCESS_TOKEN':'fake'})
        response=Mock(status_code=429)
        with patch('sector_heatmap.dhan_execution.requests.request',return_value=response) as request:
            with self.assertRaisesRegex(RuntimeError,'rate limit'):
                client.request('POST','/orders',{'quantity':1})
        self.assertEqual(request.call_count,1)

class DefiniteRejectionTests(unittest.TestCase):
    setUp=DhanExecutionTests.setUp
    tearDown=DhanExecutionTests.tearDown
    def test_broker_rejection_does_not_create_uncertain_block(self):
        from sector_heatmap.dhan_execution import DhanAPIError
        request=self.client.request
        def reject(method,path,payload=None):
            if method=='POST' and path in ('/orders','/super/orders'):
                self.client.calls.append((method,path,payload))
                raise DhanAPIError('Dhan explicitly rejected the request.',True)
            return request(method,path,payload)
        self.client.request=reject
        self.service.account['live_enabled']=True
        preview=self.service.prepare(self.payload)
        result=self.service.submit(preview['preview_id'],preview['confirmation_phrase'])
        self.assertEqual(result['status'],'REJECTED')
        self.assertEqual(result['account_id'],self.account['id'])
        self.assertEqual(self.service.reconcile()['unresolved'],0)
        self.assertTrue(self.service.prepare(self.payload)['preview_id'])
        self.assertEqual(len([c for c in self.client.calls if c[0]=='POST' and c[1] in ('/orders','/super/orders')]),1)

class McxManualTests(unittest.TestCase):
    setUp=DhanExecutionTests.setUp
    tearDown=DhanExecutionTests.tearDown
    def prepare(self):
        self.clock=datetime(2026,10,12,20,0,tzinfo=IST)
        self.payload.update(exchange_segment='MCX_COMM',security_id='901',quantity=1,
                            idea_risk_limit=20000,daily_loss_limit=30000)
        self.service.master.resolve=lambda payload,now:dict(security_id='901',exchange_segment='MCX_COMM',
            symbol='CRUDEOIL-15Oct2026-7750-CE',lot_size=1,tick_size=.1,option_type='CE',
            expiry='2026-10-15',kind='NATIVE',quantity_multiplier=100,
            entry_cutoff=datetime(2026,10,14,23,tzinfo=IST).timestamp())
    def test_evening_preview_values_full_premium(self):
        self.prepare();result=self.service._preflight(self.payload)
        self.assertEqual(result['instrument']['worst_case_risk'],10000)
        self.assertEqual(result['margin_required'],10000)
        self.assertEqual(result['ticket']['quantity'],1)
        self.assertEqual(result['ticket']['productType'],'MARGIN')
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))
    def test_cash_and_risk_not_understated(self):
        self.prepare();self.client.cash=5000
        with self.assertRaisesRegex(ValueError,'Insufficient'):self.service._preflight(self.payload)
        self.client.cash=100000;self.payload['idea_risk_limit']=1000
        with self.assertRaisesRegex(ValueError,'risk budget'):self.service._preflight(self.payload)
    def test_expiry_and_short_option_blocked(self):
        self.prepare();self.payload['transaction_type']='SELL'
        with self.assertRaisesRegex(ValueError,'Short options'):self.service._preflight(self.payload)
        self.payload['transaction_type']='BUY';self.clock=datetime(2026,10,15,12,tzinfo=IST)
        with self.assertRaisesRegex(ValueError,'pre-expiry'):self.service._preflight(self.payload)
