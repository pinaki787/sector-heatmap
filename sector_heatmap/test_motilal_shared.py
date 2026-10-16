from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import json,tempfile,unittest
from .motilal_api import MotilalError
from .motilal_history import History
from .motilal_feed import QuoteFeed,EXCHANGE_CODES
from .motilal_strategy_broker import Broker,IST,BROKER

class NativeStrategyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=datetime(2026,10,15,12,tzinfo=IST).timestamp()
        self.meta=dict(symbol='MO:NSEFO:51480',token=51480,exchange='NSEFO',name='NIFTY',underlying='NIFTY',instrument='OPTIDX',option_type='CE',expiry='2026-10-27',strike=25750,lot_size=65,tick_size=.05,max_quantity=10000)
        self.positions=[];self.orders=[];self.calls=[]
        client=Mock(live_enabled=True);client.profile.return_value=dict(clientcode='CLIENT1',usertype='Investor Client',exchanges=['NSEFO'],products=['NORMAL'])
        def request(operation,body=None):self.calls.append((operation,body));return dict(uniqueorderid='ORDER1')
        client.request.side_effect=request
        feed=Mock(connected=True,generation=1);feed.quote.return_value=dict(bid=100,ask=100.05,exchange_at=self.now,received_at=self.now)
        master=Mock();master.exact.side_effect=lambda symbol:dict(self.meta) if symbol==self.meta['symbol'] else (_ for _ in ()).throw(ValueError('Unknown exact native symbol'))
        def book(operation):return dict(data={'positions':self.positions,'orders':self.orders,'margin':[dict(srno=103,amount=1000000)]}[operation])
        self.service=SimpleNamespace(folder=Path(self.temp.name),account=dict(id='a'*32,account_ref='CLIENT1',live_enabled=True),client=client,feed=feed,master=master,ready=lambda:None,book=book,execution_allowed=lambda:True,install_revision=1)
        from .motilal_execution import Tickets
        self.service.tickets=Tickets(self.temp.name,client,master,feed,'a'*32,clock=lambda:self.now)
        self.adapter=Broker(self.service,clock=lambda:self.now)
        self.order=self.adapter.order(self.meta['symbol'],130,1,feed.quote.return_value);self.order['orderTag']='ECabcdefghijklmnopqrst'
    def tearDown(self):self.temp.cleanup()
    def native_order(self,tag,**change):return dict(exchange='NSEFO',symboltoken=51480,buyorsell='BUY',producttype='NORMAL',orderqty=130,lotsize=65,totalqtytraded=130,averageprice=100.05,uniqueorderid='ORDER1',orderstatus='TRADED',tag=tag,**change)
    def test_actual_lots_units_and_durable_full_tag_mapping(self):
        result=self.adapter.place(self.order);self.assertEqual(result,dict(s='ok',id='ORDER1'))
        operation,body=self.calls[0];self.assertEqual(operation,'place');self.assertEqual(body['quantityinlot'],2);self.assertEqual(len(body['tag']),10);self.assertNotEqual(body['tag'],self.order['orderTag'][:10])
        self.orders=[self.native_order(body['tag'])];row=self.adapter.orders()[0]
        self.assertEqual(row['qty'],130);self.assertEqual(row['filledQty'],130);self.assertEqual(row['tradedPrice'],100.05);self.assertEqual(row['orderTag'],self.order['orderTag'])
    def test_documented_title_case_fill_reconciles_exact_owned_intent(self):
        self.adapter.place(self.order);tag=self.calls[0][1]['tag']
        row=self.native_order(tag);row.update(orderstatus='Traded',buyorsell='Buy')
        self.orders=[row]
        result=self.adapter.orders()[0]
        self.assertEqual(result['filledQty'],130);self.assertEqual(result['orderTag'],self.order['orderTag'])
        self.adapter.preflight(self.order,{})
        self.assertEqual(len(self.calls),1)
    def test_unknown_title_case_status_does_not_infer_fill(self):
        self.adapter.place(self.order);tag=self.calls[0][1]['tag']
        row=self.native_order(tag);row['orderstatus']='FutureStatus';self.orders=[row]
        with self.assertRaisesRegex(ValueError,'Unknown native order status'):self.adapter.orders()
        self.assertEqual(len(self.calls),1)
    def test_timeout_cannot_replay_and_no_match_cannot_clear(self):
        self.service.client.request.side_effect=MotilalError('Lost ack',uncertain=True)
        self.assertEqual(self.adapter.place(self.order)['code'],201)
        self.assertEqual(self.adapter.orders(),[])
        self.assertEqual(self.adapter.place(self.order)['s'],'error');self.service.client.request.assert_called_once()
        with self.adapter.db() as db:self.assertEqual(db.execute('SELECT state FROM intents').fetchone()[0],'UNCERTAIN')
    def test_unknown_recovers_only_matching_existing_native_order(self):
        self.service.client.request.side_effect=MotilalError('Lost ack',uncertain=True);self.adapter.place(self.order)
        with self.adapter.db() as db:tag=db.execute('SELECT native_tag FROM intents').fetchone()[0]
        self.orders=[self.native_order(tag)];self.assertEqual(self.adapter.orders()[0]['orderTag'],self.order['orderTag']);self.service.client.request.assert_called_once()
    def test_wrong_native_units_cannot_acquire_ownership(self):
        self.adapter.place(self.order);tag=self.calls[0][1]['tag'];row=self.native_order(tag);row['orderqty']=2;self.orders=[row]
        with self.assertRaises(PermissionError):self.adapter.orders()
    def test_wrong_contract_or_product_cannot_acquire_ownership(self):
        self.adapter.place(self.order);tag=self.calls[0][1]['tag']
        for changes in [dict(symboltoken=999),dict(producttype='DELIVERY'),dict(lotsize=50),dict(buyorsell='SELL')]:
            self.orders=[dict(self.native_order(tag),**changes)]
            with self.assertRaises(PermissionError):self.adapter.orders()
    def test_price_unit_mismatch_blocks_fill_normalization(self):
        self.adapter.place(self.order);self.orders=[dict(self.native_order(self.calls[0][1]['tag']),averageprice=10005)]
        with self.assertRaises(ValueError):self.adapter.orders()
    def test_external_orders_are_not_owned(self):
        self.orders=[self.native_order('EXTERNAL')];self.assertEqual(self.adapter.orders(),[])
    def test_external_pending_same_contract_blocks_entry(self):
        row=self.native_order('EXTERNAL');row['orderstatus']='CONFIRM';self.orders=[row]
        self.assertEqual(self.adapter.place(self.order)['s'],'error');self.assertEqual(self.calls,[])
    def test_exit_requires_exact_broker_owned_units(self):
        self.positions=[dict(exchange='NSEFO',symboltoken=51480,buyquantity=65,sellquantity=0,productname='NORMAL')]
        order=dict(self.order,side=-1,limitPrice=100)
        self.assertEqual(self.adapter.place(order)['s'],'error');self.assertEqual(self.calls,[])
    def test_matching_owned_exit_is_native_sell_not_new_short(self):
        self.positions=[dict(exchange='NSEFO',symboltoken=51480,buyquantity=130,sellquantity=0,productname='NORMAL')]
        result=self.adapter.place(dict(self.order,side=-1,limitPrice=100));self.assertEqual(result['s'],'ok');self.assertEqual(self.calls[0][1]['buyorsell'],'SELL')
    def test_disabled_live_and_moved_quote_send_nothing(self):
        self.service.account['live_enabled']=False;self.assertEqual(self.adapter.place(self.order)['s'],'error');self.assertEqual(self.calls,[])
        self.service.account['live_enabled']=True;self.service.feed.quote.return_value['ask']=101
        self.assertTrue(self.adapter.place(self.order)['entry_deferred']);self.assertEqual(self.calls,[])
    def test_cross_broker_contract_fails_closed(self):
        with self.assertRaises(ValueError):self.adapter.contract('NSE:NIFTY26OCT25750CE')
        self.assertEqual(self.calls,[])

class CaptureTests(unittest.TestCase):
    def test_session_alignment_and_missing_minute_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            opening=int(datetime(2026,10,15,9,15,tzinfo=IST).timestamp());clock=[opening]
            history=History(Path(folder)/'history.sqlite3',clock=lambda:clock[0]);symbol='MO:NSE:1'
            for minute in range(16):
                clock[0]=opening+minute*60+1
                history.ingest(dict(symbol=symbol,ltp=100+minute,exch_feed_time=clock[0],cumulative_volume=minute*100),opening-1)
            rows=history.candles(symbol,15,session_open='09:15');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['timestamp'],opening)
            with history.db() as db:db.execute('DELETE FROM candles WHERE timestamp=?',(opening+60,))
            self.assertEqual(history.candles(symbol,15,session_open='09:15'),[])
    def test_disconnect_does_not_publish_partial_open(self):
        with tempfile.TemporaryDirectory() as folder:
            opening=int(datetime(2026,10,15,9,15,tzinfo=IST).timestamp());clock=[opening+1];history=History(Path(folder)/'history.sqlite3',clock=lambda:clock[0])
            history.ingest(dict(symbol='MO:NSE:1',ltp=100,exch_feed_time=clock[0]),opening-1);history.invalidate();clock[0]+=60
            history.ingest(dict(symbol='MO:NSE:1',ltp=101,exch_feed_time=clock[0]),clock[0]-1)
            self.assertEqual(history.candles('MO:NSE:1'),[])
    def test_index_broadcast_does_not_collide_with_cash_token(self):
        import struct
        clock=lambda:1792050301
        client=Mock();feed=QuoteFeed(client,clock=clock);feed.connected=True;feed.coverage_since=clock()-120
        feed.subscribe_index('NSE',26000);feed.subscriptions[(b'N',26000)]='NSE'
        from .motilal_feed import EPOCH_1980
        packet=struct.pack('<ciicf',b'N',26000,int(clock()-EPOCH_1980),b'H',25000)+b'\0'*16
        feed.ingest(packet);self.assertEqual(feed.price('NSE',26000,True)[0],25000)
        with self.assertRaises(ValueError):feed.price('NSE',26000,False)

class SharedTicketTests(unittest.TestCase):
    def setUp(self):
        NativeStrategyTests.setUp(self)
        self.meta.update(symbol='MO:NSE:1',token=1,exchange='NSE',name='TEST',underlying='TEST',instrument='EQ',option_type='EQ',expiry=None,lot_size=1,suspended=False,banned=False)
        self.service.master.rows.return_value=[self.meta]
        self.service.client.profile.return_value['exchanges'].append('NSE')
        original=self.service.book
        self.service.book=lambda op:dict(data=[dict(srno=102,amount=1000000),dict(srno=103,amount=1000000),dict(srno=700,amount=0)]) if op=='margin' else original(op)
        from .motilal_shared_tickets import Batches
        self.batches=Batches(self.service,clock=lambda:self.now);self.batches.adapter=self.adapter
        self.user=dict(id='USER1')
        self.item=dict(account_id='a'*32,broker=BROKER,underlying='NSE:TEST-EQ',quantity=2,invalidation=95,proposal=dict(kind='EQUITY',direction='BULLISH'),enforce_risk_controls=False)
    def tearDown(self):NativeStrategyTests.tearDown(self)
    def test_shared_preview_has_exact_account_native_units_and_no_order(self):
        result=self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=201))
        self.assertEqual(result['items'][0]['units'],2);self.assertEqual(result['broker'],BROKER);self.assertEqual(result['account_id'],'a'*32);self.assertEqual(self.calls,[]);self.assertTrue(result['submission_eligible'])
    def test_exact_confirmation_consumes_batch_once(self):
        result=self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=201))
        payload=dict(preview_id=result['preview_id'],confirmation=result['confirmation_phrase'])
        self.assertEqual(self.batches.submit(self.user,payload)['status'],'ACCEPTED')
        with self.assertRaises(ValueError):self.batches.submit(self.user,payload)
        self.assertEqual(len(self.calls),1)
    def test_changed_quantity_or_budget_cannot_overallocate(self):
        with self.assertRaises(ValueError):self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=100))
        self.assertEqual(self.calls,[])
    def test_other_user_and_changed_live_capability_block_submission(self):
        result=self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=201));payload=dict(preview_id=result['preview_id'],confirmation=result['confirmation_phrase'])
        with self.assertRaises(PermissionError):self.batches.submit(dict(id='OTHER'),payload)
        self.service.account['live_enabled']=False
        self.assertEqual(self.batches.submit(self.user,payload)['status'],'RECONCILIATION_REQUIRED');self.assertEqual(self.calls,[])
    def test_paper_is_never_silently_upgraded(self):
        with self.assertRaisesRegex(ValueError,'Paper'):self.batches.prepare(self.user,dict(items=[dict(self.item,mode='PAPER')]))
        self.assertEqual(self.calls,[])
    def test_native_spread_is_explicitly_unavailable_not_an_uncovered_sell(self):
        item=dict(self.item,proposal=dict(kind='OPTION_SPREAD'))
        with self.assertRaisesRegex(ValueError,'spread submission'):self.batches.prepare(self.user,dict(items=[item]))
        self.assertEqual(self.calls,[])
    def test_bearish_cash_cannot_become_a_bought_stock(self):
        with self.assertRaisesRegex(ValueError,'bought equity'):self.batches.prepare(self.user,dict(items=[dict(self.item,proposal=dict(kind='EQUITY',direction='BEARISH'))]))
        self.assertEqual(self.calls,[])
    def test_nan_external_risk_cannot_bypass_policy(self):
        item=dict(self.item,enforce_risk_controls=True,idea_risk_limit=100,daily_loss_limit=1000,risk_reserve=100,max_simultaneous_positions=5,external_open_risk=float('nan'))
        with self.assertRaises(ValueError):self.batches.prepare(self.user,dict(items=[item]))
        self.assertEqual(self.calls,[])

    def test_external_pending_buy_reserves_position_allowance(self):
        self.orders=[dict(exchange='NSE',symboltoken=99,buyorsell='Buy',orderstatus='Confirm')]
        item=dict(self.item,enforce_risk_controls=True,idea_risk_limit=100,daily_loss_limit=1000,risk_reserve=100,max_simultaneous_positions=1,external_open_risk=0)
        with self.assertRaisesRegex(ValueError,'maximum-position'):self.batches.prepare(self.user,dict(items=[item],allocation_budget=201))
        self.assertEqual(self.calls,[])
    def test_external_pending_buy_after_review_blocks_submission(self):
        item=dict(self.item,enforce_risk_controls=True,idea_risk_limit=100,daily_loss_limit=1000,risk_reserve=100,max_simultaneous_positions=1,external_open_risk=0)
        preview=self.batches.prepare(self.user,dict(items=[item],allocation_budget=201))
        self.orders=[dict(exchange='NSE',symboltoken=99,buyorsell='Buy',orderstatus='Confirm')]
        result=self.batches.submit(self.user,dict(preview_id=preview['preview_id'],confirmation=preview['confirmation_phrase']))
        self.assertEqual(result['status'],'RECONCILIATION_REQUIRED');self.assertIn('maximum-position',result['message']);self.assertEqual(self.calls,[])
    def test_pending_buys_count_once_per_contract_and_not_twice_with_position(self):
        self.orders=[dict(exchange='NSE',symboltoken=99,buyorsell='Buy',orderstatus='Confirm')]*2
        self.assertEqual(self.batches.position_slots(),1)
        self.adapter.positions=Mock(return_value=[dict(symbol='MO:NSE:99',netQty=1)])
        self.assertEqual(self.batches.position_slots(),1)
    def test_terminal_orders_do_not_reserve_position_allowance(self):
        self.orders=[dict(exchange='NSE',symboltoken=99,buyorsell='Buy',orderstatus=status) for status in ['Traded','Cancel','Rejected','Error']]
        self.assertEqual(self.batches.position_slots(),0)
    def test_new_position_after_review_blocks_before_order_submission(self):
        item=dict(self.item,enforce_risk_controls=True,idea_risk_limit=100,daily_loss_limit=1000,risk_reserve=100,max_simultaneous_positions=1,external_open_risk=0)
        preview=self.batches.prepare(self.user,dict(items=[item],allocation_budget=201))
        self.adapter.positions=Mock(return_value=[dict(symbol='MO:NSE:OTHER',netQty=1)])
        result=self.batches.submit(self.user,dict(preview_id=preview['preview_id'],confirmation=preview['confirmation_phrase']))
        self.assertEqual(result['status'],'RECONCILIATION_REQUIRED')
        self.assertIn('maximum-position',result['message']);self.assertEqual(self.calls,[])

    def test_existing_same_underlying_blocks_even_without_risk_controls(self):
        self.positions=[dict(exchange='NSE',symboltoken=1,buyquantity=65,sellquantity=0,productname='NORMAL')]
        with self.assertRaisesRegex(ValueError,'duplicate entry blocked|Native position differs|pending order blocks entry'):
            self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=10000))
        self.assertEqual(self.calls,[])

    def test_external_pending_same_symbol_blocks_without_risk_controls(self):
        self.orders=[dict(exchange='NSE',symboltoken=1,orderstatus='CONFIRM',buyorsell='BUY')]
        with self.assertRaisesRegex(ValueError,'duplicate entry blocked|Native position differs|pending order blocks entry'):
            self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=10000))
        self.assertEqual(self.calls,[])

    def test_position_appearing_after_preview_blocks_duplicate_submit(self):
        preview=self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=10000))
        self.positions=[dict(exchange='NSE',symboltoken=1,buyquantity=65,sellquantity=0,productname='NORMAL')]
        result=self.batches.submit(self.user,dict(preview_id=preview['preview_id'],confirmation=preview['confirmation_phrase']))
        self.assertEqual(result['status'],'RECONCILIATION_REQUIRED')
        self.assertIn('duplicate entry blocked',result['message']);self.assertEqual(self.calls,[])

    def test_delivery_is_never_silently_converted_to_intraday(self):
        item=dict(self.item,cash_product='CNC',proposal=dict(kind='EQUITY',direction='BULLISH'))
        with self.assertRaisesRegex(ValueError,'silent conversion'):self.batches.prepare(self.user,dict(items=[item]))
        self.assertEqual(self.calls,[])

class ExitRaceTests(unittest.TestCase):
    setUp=NativeStrategyTests.setUp
    tearDown=NativeStrategyTests.tearDown
    native_order=NativeStrategyTests.native_order
    def test_external_pending_sell_cannot_race_the_strategy_exit(self):
        self.positions=[dict(exchange='NSEFO',symboltoken=51480,buyquantity=130,sellquantity=0,productname='NORMAL')]
        self.orders=[dict(self.native_order('EXTERNAL'),orderstatus='CONFIRM',buyorsell='SELL',totalqtytraded=0)]
        result=self.adapter.place(dict(self.order,side=-1,limitPrice=100))
        self.assertEqual(result['s'],'error');self.assertEqual(self.calls,[])


class NativeMcxMappingTests(unittest.TestCase):
    def setUp(self):
        self.host=dict(token=101,exchange='MCX',instrument='FUTCOM',underlying='CRUDEOILM',expiry='2026-11-19',lot_size=10)
        self.rows=[dict(symbol='MO:MCX:'+str(token),token=token,instrument='OPTFUT',underlying_token=101,underlying='CRUDEOILM',expiry='2026-11-17',strike=9100,option_type=side,lot_size=10,suspended=False,banned=False) for token,side in [(201,'CE'),(202,'PE')]]
        self.master=Mock();self.master.rows.return_value=self.rows
        self.broker=Broker.__new__(Broker);self.broker.service=SimpleNamespace(master=self.master);self.broker.clock=lambda:datetime(2026,10,15,12,tzinfo=IST).timestamp();self.broker.underlying=lambda symbol:self.host
    def test_exact_parent_token_pairs_both_sides(self):
        self.assertEqual(len(self.broker.option_rows('MCX:101')),2)
    def test_other_month_and_mini_family_cannot_leak(self):
        for field,value in [('underlying_token',999),('underlying','CRUDEOIL')]:
            rows=[dict(r,**{field:value}) for r in self.rows];self.master.rows.return_value=rows
            with self.assertRaises(ValueError):self.broker.option_rows('MCX:101')
    def test_missing_side_cannot_be_selected(self):
        self.master.rows.return_value=self.rows[:1];self.assertEqual(self.broker.option_rows('MCX:101'),[])
    def test_bad_expiry_and_lot_are_blocked(self):
        for field,value in [('expiry','2026-11-20'),('lot_size',100)]:
            self.master.rows.return_value=[dict(r,**{field:value}) for r in self.rows]
            with self.assertRaises(ValueError):self.broker.option_rows('MCX:101')
    def test_old_cache_is_refreshed_for_parent_tokens(self):
        old=[{k:v for k,v in r.items() if k!='underlying_token'} for r in self.rows]
        self.master.rows.side_effect=[old,self.rows];self.assertEqual(len(self.broker.option_rows('MCX:101')),2);self.master.rows.assert_called_with('MCX',refresh=True)
    def test_direction_uses_fixed_host_price_and_native_call_or_put(self):
        self.broker.live_price=lambda config,now:(9110,self.broker.clock());self.broker.subscribe=lambda symbol:None
        self.broker.contract=lambda symbol:next(r for r in self.rows if r['symbol']==symbol)
        for direction,side in [('BULLISH','CE'),('BEARISH','PE')]:
            self.assertEqual(self.broker.resolve(dict(underlying='MCX:101'),direction)['option_type'],side)

class NativeExchangeParentTests(unittest.TestCase):
    def test_bse_aliases_use_exact_parent_and_keep_index_cash_namespaces_separate(self):
        b=Broker.__new__(Broker);b.clock=lambda:datetime(2026,10,15,12,tzinfo=IST).timestamp()
        host=dict(exchange='BSE',token=999901,instrument='INDEX',underlying='SENSEX',name='SENSEX')
        b.underlying=lambda _:host
        def option(token,kind,parent,alias,side):return dict(token=token,instrument=kind,underlying_token=parent,underlying=alias,option_type=side,expiry='2026-10-22',strike=80000,suspended=False,banned=False)
        rows=[option(1,'OPTIDX',999901,'BSX','CE'),option(2,'OPTIDX',999901,'BSX','PE'),option(3,'OPTSTK',999901,'OTHER','CE'),option(4,'OPTSTK',999901,'OTHER','PE'),option(5,'OPTIDX',999912,'BANKEX','CE')]
        master=Mock();master.rows.return_value=rows;b.service=SimpleNamespace(master=master)
        self.assertEqual([r['token'] for r in b.option_rows('BSE:SENSEX-INDEX')],[1,2]);master.rows.assert_called_with('BSEFO')
        host['instrument']='';self.assertEqual([r['token'] for r in b.option_rows('BSE:OTHER-EQ')],[3,4])
    def test_bse_cash_groups_are_not_misread_as_option_types(self):
        from .motilal_strategy_broker import cash_row
        self.assertTrue(cash_row(dict(exchange='BSE',option_type='A',expiry=None)))
        self.assertFalse(cash_row(dict(exchange='BSE',option_type='F',expiry=None)))
        self.assertFalse(cash_row(dict(exchange='BSEFO',option_type='CE',expiry='2026-10-22')))


class NativeSessionCalendarTests(unittest.TestCase):
    def test_regular_dst_winter_and_holiday_sessions(self):
        from .motilal_calendar import trading_bounds
        for day,expected in [('2026-10-15',(540,1410)),('2026-11-03',(540,1435)),('2026-10-20',(1020,1410)),('2026-10-02',(0,0)),('2026-10-17',(0,0))]:
            self.assertEqual(trading_bounds(datetime.fromisoformat(day+'T12:00:00').replace(tzinfo=IST).timestamp()),expected)
        with self.assertRaises(ValueError):trading_bounds(datetime(2027,1,1,tzinfo=IST).timestamp())

class NativeAtmTicketTests(unittest.TestCase):
    def setUp(self):
        NativeStrategyTests.setUp(self)
        from .motilal_shared_tickets import Batches
        self.batches=Batches(self.service,clock=lambda:self.now);self.batches.adapter=self.adapter
        self.adapter.option_rows=Mock(return_value=[self.meta])
        self.adapter.resolve=Mock(return_value=self.meta)
        self.user=dict(id='USER1')
        self.item=dict(account_id='a'*32,broker=BROKER,underlying='NSE:NIFTY50-INDEX',lots=1,proposal=dict(kind='LONG_OPTION',direction='BULLISH',legs=[dict(symbol=self.meta['symbol'],action='BUY')]),enforce_risk_controls=False)
    tearDown=NativeStrategyTests.tearDown
    def test_reviewed_atm_call_and_put_are_one_bought_native_leg(self):
        for direction,kind in [('BULLISH','CE'),('BEARISH','PE')]:
            self.meta['option_type']=kind;self.item['proposal']['direction']=direction
            result=self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=10000))
            self.assertEqual(result['items'][0]['body']['buyorsell'],'BUY')
            self.assertEqual(result['items'][0]['units'],65)
        self.assertEqual(self.calls,[])
    def test_non_atm_or_wrong_expiry_is_rejected_before_ticket(self):
        self.adapter.resolve.return_value=dict(self.meta,symbol='MO:NSEFO:OTHER')
        with self.assertRaisesRegex(ValueError,'current native ATM'):self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=10000))
        self.assertEqual(self.calls,[])
    def test_atm_changed_after_review_cannot_silently_switch_contract(self):
        preview=self.batches.prepare(self.user,dict(items=[self.item],allocation_budget=10000))
        self.adapter.resolve.return_value=dict(self.meta,symbol='MO:NSEFO:OTHER')
        result=self.batches.submit(self.user,dict(preview_id=preview['preview_id'],confirmation=preview['confirmation_phrase']))
        self.assertEqual(result['status'],'RECONCILIATION_REQUIRED');self.assertIn('ATM contract changed',result['message']);self.assertEqual(self.calls,[])
