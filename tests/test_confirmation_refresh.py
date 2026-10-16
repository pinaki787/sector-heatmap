from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock
from tests.test_fyers_execution import FyersExecutionTests, FakeClient
from sector_heatmap.fyers_execution import _review_terms, PreviewChanged

class ConfirmationRefreshTests(TestCase):
    def setUp(self):
        helper=FyersExecutionTests()
        self.addCleanup(helper.doCleanups)
        self.service=helper.make_service(FakeClient())
        self.service._live_submission_enabled=lambda: True
        self.item={'instrument': {'kind':'LONG_OPTION','contracts':[{'symbol':'PE100','action':'BUY','quantity':50,'limit_price':4.4,'quote':{'provider_timestamp':1},'chain':{'oi':10}}], 'worst_case_risk':220}, 'submission_eligible':True,'order_policy':{'product_type':'MARGIN'}}
        self.batch={'items':[self.item], 'aggregate':{'total_worst_case_risk':220},'submission_eligible':True,'live_submission_enabled':True}
    def test_batch_metadata_refresh_submits_once(self):
        old=self.service._store_batch_preview({},deepcopy(self.batch))
        fresh=deepcopy(self.batch)
        fresh['items'][0]['instrument']['contracts'][0]['quote']['provider_timestamp']=2
        fresh['items'][0]['instrument']['contracts'][0]['chain']['oi']=20
        self.service._batch_preflight=Mock(return_value=fresh)
        self.service._submit_option_batch=Mock(return_value={'status':'MOCK_ONLY','preview_id':old['preview_id']})
        self.assertEqual(self.service.submit_batch(old['preview_id'],old['confirmation_phrase'])['status'],'MOCK_ONLY')
        self.service._submit_option_batch.assert_called_once()
    def test_changed_limit_requires_review_without_second_refresh(self):
        old=self.service._store_batch_preview({},deepcopy(self.batch))
        fresh=deepcopy(self.batch)
        fresh['items'][0]['instrument']['contracts'][0]['limit_price']=4.5
        self.service._batch_preflight=Mock(return_value=fresh)
        self.service._submit_option_batch=Mock()
        with self.assertRaises(PreviewChanged) as caught:
            self.service.submit_batch(old['preview_id'],old['confirmation_phrase'])
        self.assertEqual(caught.exception.preview['items'][0]['instrument']['contracts'][0]['limit_price'],4.5)
        self.service._batch_preflight.assert_called_once()
        self.service._submit_option_batch.assert_not_called()
    def test_quantity_contract_product_and_risk_remain_binding(self):
        for field,value in [('quantity',100),('symbol','PE95'),('action','SELL'),('limit_price',4.5)]:
            changed=deepcopy(self.item);changed['instrument']['contracts'][0][field]=value
            self.assertNotEqual(_review_terms(self.item),_review_terms(changed))
        changed=deepcopy(self.item);changed['order_policy']['product_type']='INTRADAY'
        self.assertNotEqual(_review_terms(self.item),_review_terms(changed))
        changed=deepcopy(self.item);changed['instrument']['worst_case_risk']=250
        self.assertNotEqual(_review_terms(self.item),_review_terms(changed))

    def test_entry_evidence_is_frozen_and_result_is_separate(self):
        import json
        payload={'analysis_evidence':{'conviction':{'score':7}},'sector_evidence':[{'sector_id':'fmcg','rank':2}]}
        old=self.service._store_preview(payload,deepcopy(self.item))
        payload['analysis_evidence']['conviction']['score']=0
        stored=self.service.previews[old['preview_id']]
        self.service._archive_entry_evidence(old['preview_id'],stored,self.item)
        folder=self.service.ledger.path.parent/'entry-evidence'
        snapshot=json.loads((folder/(old['preview_id']+'.json')).read_text())
        self.assertEqual(snapshot['analysis_evidence']['conviction']['score'],7)
        self.assertFalse(snapshot['fill_confirmed'])
        self.assertEqual(snapshot['sector_ranking_snapshot'][0]['rank'],2)
        self.service._archive_entry_result({'preview_id':old['preview_id'],'status':'OPEN','order_ids':['mock-order']})
        self.assertTrue((folder/(old['preview_id']+'-result.json')).exists())
        self.assertEqual(json.loads((folder/(old['preview_id']+'.json')).read_text()),snapshot)
