import unittest
from copy import deepcopy
from types import SimpleNamespace
from sector_heatmap.handoff_analysis import opportunities,size

class Provider:
    broker="FYERS"
    execution=SimpleNamespace(account={"id":"owned"})
    def __init__(self,exposed=False):
        self.exposed=exposed;self.positions_calls=0
    def candidates(self,mode):
        states={t:dict(label="STRONG BEARISH",close=100,ema20=104,atr=5,adx=31,
            relative_strength_state="UNDERPERFORMING",data_quality="DELAYED",reasons=[])
            for t in ("15m","1h","daily","weekly")}
        c=dict(key="stock:TEST",kind="stock",symbol="NSE:TEST-EQ",name="Test",price=100,
            direction="BEARISH",mtf_alignment="FULL BEARISH ALIGNMENT",data_quality="DELAYED",timeframe_states=states)
        return dict(candidates=[c],scope={"scanned_stocks":1},updated_at="current")
    def positions(self):
        self.positions_calls+=1
        return [dict(symbol="NSE:TEST-EQ",netQty=1)] if self.exposed else []
    def orders(self):return []
    def quote(self,symbol):return 100,123
    def tick(self,symbol):return .05

class AnalysisTests(unittest.TestCase):
    def payload(self):
        return dict(recipient="codex",instrument_route="cash_equity",mode="intraday",
            risk_policy=dict(planning_capital=100000,daily_loss_limit=10000,
                enforce_risk_controls=False,enforce_minimum_reward_to_risk=True,minimum_reward_to_risk=1,
                stop_basis="price",order_type="LIMIT"))
    def test_real_rules_build_bearish_card_and_accept_fresh_structural_levels(self):
        runs={};provider=Provider()
        report=opportunities(self.payload(),provider,runs)
        self.assertEqual(len(report["cards"]),1)
        self.assertEqual(report["cards"][0]["candidate"]["direction"],"BEARISH")
        self.assertEqual(provider.positions_calls,2)
        review=size(dict(analysis_id=report["analysis_id"],card_id="card-1",
            risk_policy=self.payload()["risk_policy"],selection={"method":"structure"}),runs)
        self.assertGreater(review["active_invalidation"]["price"],100)
        self.assertLess(review["active_invalidation"]["target"],100)
    def test_existing_position_is_excluded_before_card_generation(self):
        report=opportunities(self.payload(),Provider(True),{})
        self.assertEqual(report["cards"],[])
        self.assertEqual(report["exclusions"][0]["kind"],"OPEN_POSITION")
    def test_exposure_appearing_during_analysis_is_rechecked(self):
        provider=Provider();base=provider.positions
        def positions():
            if provider.positions_calls:provider.exposed=True
            return base()
        provider.positions=positions
        report=opportunities(self.payload(),provider,{})
        self.assertEqual(report["cards"],[])
        self.assertTrue(report["exclusions"])

class AdapterIntegration(unittest.TestCase):
    def test_real_engine_sizing_shape_is_accepted_by_owned_adapter(self):
        from sector_heatmap.handoff_bridge import OwnedBridge
        provider=Provider();provider.quote=lambda symbol:(102,123)
        runs={};payload=AnalysisTests().payload()
        report=opportunities(payload,provider,runs)
        # The real engine's 6-point evidence grade is retained.
        self.assertEqual(str(report["cards"][0]["analysis"]["conviction"]["rating"]).upper(),"HIGH")
        bridge=object.__new__(OwnedBridge);bridge.account={"broker":"FYERS"};bridge.account_id="owned"
        bridge.analysis=lambda route,p:deepcopy(report) if route=="cash_equity" else dict(source={"broker":"FYERS"},cards=[],exclusions=[],scope={})
        prepared=[]
        def request(operation,payload):
            if operation=="size":return size(payload,runs)
            self.assertEqual(operation,"prepare")
            prepared.append(payload)
            return dict(instrument=dict(kind="EQUITY",contracts=[dict(symbol="NSE:TEST-EQ",action="SELL",limit_price=102,tick_size=.05)]),
                protection=dict(stop_loss_price=104,target_price=100),submission_eligible=True)
        bridge.request=request
        rows,result=bridge.collect(dict(capital=100000,cash_product="INTRADAY"))
        self.assertEqual(result["exclusions"],[])
        self.assertEqual(len(rows),1)
        self.assertEqual(prepared[0]["underlying_exit_plan"],dict(entry=102,stop=104,target=100))
        self.assertEqual(prepared[0]["proposal"]["entry"],102)
