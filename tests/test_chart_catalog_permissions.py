import unittest
from types import SimpleNamespace
from sector_heatmap.chart_catalog import serve_delta_chart_catalog


class ChartCatalogPermissions(unittest.TestCase):
    def fixture(self, features=('chart-workspace',), visible=True, broker='DELTA_INDIA', admin=False):
        handler = SimpleNamespace(workspace_identity=({'features': list(features), 'admin': admin}, {'broker': broker}))
        sent=[]; calls=[]
        handler.send_json=lambda status, payload: sent.append((status,payload))
        guard=SimpleNamespace(store=SimpleNamespace(sidebar_visibility=lambda: {'chart-workspace':visible}))
        payload={'broker':'DELTA_INDIA','complete':True,'instruments':[{'symbol':'PAXGUSD','underlying':'PAXG','tick_size':'0.01','contract_type':'perpetual_futures'}]}
        def catalog(**kwargs): calls.append(kwargs); return payload
        return handler,guard,SimpleNamespace(catalog=catalog),sent,calls,payload

    def test_chart_only_assignment_gets_full_native_catalog_without_trading_section(self):
        h,g,d,s,c,p=self.fixture();serve_delta_chart_catalog(h,g,d)
        self.assertEqual(s,[(200,p)]);self.assertEqual(c,[{'chart':True}])
        self.assertEqual(s[0][1]['instruments'][0]['underlying'],'PAXG')

    def test_unassigned_user_and_global_hidden_admin_do_not_query_broker(self):
        for features,visible,admin in [((),True,False),(('delta-india',),True,False),(('chart-workspace',),False,False),((),False,True)]:
            with self.subTest(features=features,visible=visible,admin=admin):
                h,g,d,s,c,_=self.fixture(features,visible,admin=admin);serve_delta_chart_catalog(h,g,d)
                self.assertEqual(s[0][0],403);self.assertEqual(c,[])

    def test_other_broker_or_no_workspace_cannot_fall_back_to_delta(self):
        h,g,d,s,c,_=self.fixture(broker='FYERS');serve_delta_chart_catalog(h,g,d)
        self.assertEqual(s[0][0],404);self.assertEqual(c,[])
        h,g,d,s,c,_=self.fixture();serve_delta_chart_catalog(h,None,d)
        self.assertEqual(s[0][0],403);self.assertEqual(c,[])

    def test_partial_or_wrong_provider_catalog_is_not_published(self):
        for payload in ({'broker':'DELTA_INDIA','complete':False,'instruments':[]},{'broker':'FYERS','complete':True,'instruments':[]}):
            h,g,d,s,c,_=self.fixture();d.catalog=lambda **kwargs:payload;serve_delta_chart_catalog(h,g,d)
            self.assertEqual(s[0][0],503)


if __name__=='__main__':unittest.main()
