import unittest
from sector_heatmap.chart_trade_dhan_evidence import account_identity, no_contract_exposure, margin_coverage


class DhanChartEvidenceTests(unittest.TestCase):
    def identity(self, **overrides):
        values = dict(account={"broker":"DHAN","id":"a","account_ref":"client"},
                      client_id="client", profile={"dhanClientId":"client","dataPlan":"Active",
                      "activeSegment":"Equity, Derivative, Currency, Commodity","mtf":"Active"},
                      ips={"primaryIP":"203.0.113.10","secondaryIP":None},
                      egress="203.0.113.10", segment="NSE_FNO", product="MARGIN")
        values.update(overrides)
        return account_identity(**values)

    def test_identity_and_all_documented_segments(self):
        for segment in ("NSE_EQ","BSE_EQ","NSE_FNO","BSE_FNO","NSE_CURRENCY","BSE_CURRENCY","MCX_COMM"):
            self.assertEqual(len(self.identity(segment=segment, product="INTRADAY")),64)
        for change in ({"client_id":"foreign"}, {"egress":"203.0.113.11"},
                       {"segment":"IDX_I"}, {"product":"CNC"}, {"product":"MTF"}):
            with self.subTest(change=change), self.assertRaises((ValueError,PermissionError)):
                self.identity(**change)

    def test_missing_permission_identity_subscription_and_ip_fail(self):
        profile={"dhanClientId":"client","dataPlan":"Active","activeSegment":"Derivative"}
        for key,value in (("dhanClientId","other"),("dataPlan","Inactive"),("activeSegment","Equity")):
            with self.subTest(key=key), self.assertRaises((ValueError,PermissionError)):
                self.identity(profile=dict(profile,**{key:value}))
        with self.assertRaises(ValueError):self.identity(ips={"primaryIP":"invalid"})
        with self.assertRaises(ValueError):self.identity(segment="NSE_EQ",product="MTF",profile=profile)

    def test_unrelated_exposure_does_not_relabel_selected_contract(self):
        row=dict(dhanClientId="client",exchangeSegment="NSE_FNO",securityId="123",netQty=1)
        no_contract_exposure("client","NSE_EQ","123",[row],[])
        with self.assertRaises(ValueError):no_contract_exposure("client","NSE_FNO","123",[row],[])
        row.update(netQty=0)
        no_contract_exposure("client","NSE_FNO","123",[row],[])
        for status in ("PENDING","PART_TRADED","TRANSIT"):
            with self.assertRaises(ValueError):
                no_contract_exposure("client","NSE_FNO","123",[],[dict(row,orderStatus=status)])
        for status in ("TRADED","CANCELLED","REJECTED","EXPIRED"):
            no_contract_exposure("client","NSE_FNO","123",[],[dict(row,orderStatus=status)])

    def test_malformed_or_mixed_account_state_fails_closed(self):
        row=dict(dhanClientId="client",exchangeSegment="NSE_FNO",securityId="123",netQty=0)
        for change in ({"dhanClientId":"other"},{"netQty":True},{"netQty":"NaN"},{"securityId":None}):
            with self.assertRaises((ValueError,PermissionError)):
                no_contract_exposure("client","NSE_FNO","123",[dict(row,**change)],[])
        with self.assertRaises(ValueError):
            no_contract_exposure("client","NSE_FNO","123",[],[dict(row,orderStatus="UNKNOWN")])

    def test_margin_uses_both_balances_and_minimum_not_surplus_sign(self):
        funds=dict(dhanClientId="client",availabelBalance="10000")
        margin=dict(totalMargin="500",availableBalance="1000",insufficientBalance="500")
        self.assertEqual(margin_coverage("client",funds,margin)["required_margin"],"500")
        with self.assertRaises(ValueError):
            margin_coverage("client",funds,margin,minimum_required="1001")
        for change in ({"availableBalance":None},{"totalMargin":0},{"totalMargin":"NaN"},{"totalMargin":True}):
            with self.assertRaises(ValueError):
                margin_coverage("client",funds,dict(margin,**change))
        with self.assertRaises(PermissionError):
            margin_coverage("client",dict(funds,dhanClientId="foreign"),margin)


if __name__ == "__main__":unittest.main()
