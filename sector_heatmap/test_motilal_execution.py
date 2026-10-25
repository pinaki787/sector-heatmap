import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from .motilal_execution import Tickets
from .motilal_api import MotilalError


class TicketTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=1000
        self.client=Mock(live_enabled=True)
        self.client.profile.return_value=dict(clientcode='CLIENT1',exchanges=['NSEFO'],products=['Normal'],usertype='Investorclient')
        self.client.request.return_value=dict(uniqueorderid='ORDER123')
        self.master=Mock();self.master.exact.return_value=dict(symbol='MO:NSEFO:1',name='Native option',exchange='NSEFO',token=1,lot_size=65,tick_size=.05,instrument='OPTIDX')
        self.feed=Mock();self.feed.quote.return_value=dict(bid=100,ask=100.1,exchange_at=1000)
        self.service=Tickets(self.temp.name,self.client,self.master,self.feed,'ACCOUNT1',clock=lambda:self.now)
        self.payload=dict(account_id='ACCOUNT1',broker='MOTILAL_OSWAL',mode='LIVE',symbol='MO:NSEFO:1',side='BUY',product='NORMAL',lots=2,limit_price=100.1,max_notional=14000)
    def tearDown(self):self.temp.cleanup()
    def preview(self):return self.service.preview('USER1',self.payload)
    def test_preview_is_native_lots_and_never_places_order(self):
        ticket=self.preview();self.client.request.assert_not_called()
        self.assertEqual(ticket['units'],130);self.assertEqual(ticket['body']['quantityinlot'],2)
    def test_native_limit_submission_is_once_and_not_a_fill(self):
        ticket=self.preview();result=self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        body=self.client.request.call_args.args[1]
        self.assertEqual((body['ordertype'],body['amoorder'],body['symboltoken']),('LIMIT','N',1))
        self.assertEqual(len(body['tag']),10);self.assertEqual(result['state'],'ACCEPTED')
        with self.assertRaises(ValueError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_called_once()
    def test_uncertain_submission_cannot_replay_even_after_process_reopen(self):
        ticket=self.preview();self.client.request.side_effect=MotilalError('Timeout',uncertain=True)
        with self.assertRaises(MotilalError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        reopened=Tickets(self.temp.name,self.client,self.master,self.feed,'ACCOUNT1',clock=lambda:self.now)
        with self.assertRaises(ValueError):reopened.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_called_once()
    def test_foreign_owner_cannot_submit(self):
        ticket=self.preview()
        with self.assertRaises(PermissionError):self.service.submit('OTHER',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_not_called()
    def test_wrong_confirmation_cannot_submit(self):
        ticket=self.preview()
        with self.assertRaises(PermissionError):self.service.submit('USER1',ticket['ticket_id'],'LIVE')
        self.client.request.assert_not_called()
    def test_expired_ticket_cannot_submit(self):
        ticket=self.preview();self.now+=31
        with self.assertRaises(ValueError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_not_called()
    def test_fresh_depth_rechecked_before_submit(self):
        ticket=self.preview();self.feed.quote.side_effect=ValueError('Stale depth')
        with self.assertRaises(ValueError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_not_called()
    def test_live_flag_and_foreign_broker_block(self):
        self.client.live_enabled=False
        with self.assertRaises(PermissionError):self.preview()
        self.client.live_enabled=True;self.payload['broker']='FYERS'
        with self.assertRaises(PermissionError):self.preview()
        self.client.request.assert_not_called()
    def test_budget_and_native_tick_are_enforced(self):
        for change in [dict(max_notional=1),dict(limit_price=100.123),dict(lots=1.5),dict(lots=True),dict(limit_price='NaN'),dict(mode='live')]:
            with self.assertRaises(ValueError):self.service.preview('USER1',{**self.payload,**change})
        self.client.request.assert_not_called()
    def test_paper_route_does_not_call_order_api_or_claim_fill(self):
        self.payload['mode']='PAPER';ticket=self.preview()
        result=self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.assertEqual(result['state'],'PAPER_RECORDED');self.client.request.assert_not_called()
    def test_profile_product_and_exchange_are_required(self):
        for profile in [dict(exchanges=[],products=['NORMAL'],usertype='Investorclient'),dict(exchanges=['NSEFO'],products=[],usertype='Investorclient'),dict(exchanges=['NSEFO'],products=['Normal'],usertype='Dealer')]:
            self.client.profile.return_value=profile
            with self.assertRaises(PermissionError):self.preview()
    def test_missing_broker_id_is_uncertain_and_consumes_ticket(self):
        ticket=self.preview();self.client.request.return_value={}
        with self.assertRaises(MotilalError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.assertEqual(self.service.list('USER1')[0]['state'],'UNCERTAIN')

    def test_uncertain_result_blocks_other_tickets_until_matching_book_evidence(self):
        ticket=self.preview();self.client.request.side_effect=MotilalError('Timeout',uncertain=True)
        with self.assertRaises(MotilalError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        with self.assertRaises(ValueError):self.preview()
        self.client.request.side_effect=None
        self.client.request.return_value={'data':[dict(clientid='CLIENT1',orderqty=130,lotsize=65,tag=self.service.list('USER1')[0]['tag'],exchange='NSEFO',symboltoken=1,buyorsell='BUY',producttype='NORMAL',uniqueorderid='ORDER1',orderstatus='Traded')]}
        result=self.service.reconcile('USER1',ticket['ticket_id'])
        self.assertEqual(result['state'],'BROKER_TRADED')
        self.assertEqual(self.client.request.call_args.args[0],'orders')
        self.assertTrue(self.preview()['ticket_id'])

    def test_no_orderbook_match_cannot_clear_uncertainty(self):
        ticket=self.preview();self.client.request.side_effect=MotilalError('Timeout',uncertain=True)
        with self.assertRaises(MotilalError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.side_effect=None;self.client.request.return_value={'data':[]}
        with self.assertRaises(ValueError):self.service.reconcile('USER1',ticket['ticket_id'])
        self.assertEqual(self.service.list('USER1')[0]['state'],'UNCERTAIN')

    def test_lot_size_change_cannot_silently_change_reviewed_units(self):
        ticket=self.preview()
        self.master.exact.return_value={**self.master.exact.return_value,'lot_size':50}
        with self.assertRaisesRegex(ValueError,'metadata changed'):
            self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_not_called()
        self.assertEqual(self.service.list('USER1')[0]['state'],'REVIEW')

    def test_reused_native_token_for_different_expiry_requires_new_review(self):
        self.master.exact.return_value['expiry']='2026-10-22'
        ticket=self.preview();self.master.exact.return_value['expiry']='2026-10-29'
        with self.assertRaisesRegex(ValueError,'metadata changed'):
            self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_not_called()

    def test_new_tick_size_that_still_accepts_price_requires_new_review(self):
        ticket=self.preview();self.master.exact.return_value['tick_size']=.1
        with self.assertRaisesRegex(ValueError,'metadata changed'):
            self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.assert_not_called()

    def test_reconciliation_rejects_wrong_account_or_quantity(self):
        ticket=self.preview();self.client.request.side_effect=MotilalError('Timeout',uncertain=True)
        with self.assertRaises(MotilalError):self.service.submit('USER1',ticket['ticket_id'],ticket['confirmation'])
        self.client.request.side_effect=None
        native=dict(clientid='CLIENT1',orderqty=130,lotsize=65,tag=self.service.list('USER1')[0]['tag'],exchange='NSEFO',symboltoken=1,buyorsell='BUY',producttype='NORMAL',uniqueorderid='ORDER1',orderstatus='Traded')
        for change in [dict(clientid='OTHER'),dict(orderqty=65),dict(lotsize=50)]:
            self.client.request.return_value={'data':[{**native,**change}]}
            with self.assertRaises((PermissionError,ValueError)):self.service.reconcile('USER1',ticket['ticket_id'])
            self.assertEqual(self.service.list('USER1')[0]['state'],'UNCERTAIN')

    def test_actual_broker_investor_client_spelling_is_supported(self):
        self.client.profile.return_value['usertype']='Investor Client'
        self.assertEqual(self.preview()['mode'],'LIVE')
        self.client.request.assert_not_called()
