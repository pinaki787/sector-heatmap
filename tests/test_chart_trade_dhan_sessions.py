import unittest
from datetime import datetime, timezone
from sector_heatmap.chart_trade_dhan_sessions import validate_session, conditional_expiry
from types import SimpleNamespace
from sector_heatmap.dhan_execution import IST


class DhanChartSessionTests(unittest.TestCase):
    def now(self, text):return datetime.fromisoformat(text).replace(tzinfo=IST)
    def test_equity_open_boundaries_holiday_and_special_session(self):
        contract={"exchange_segment":"NSE_EQ"}
        for text in ("2026-11-18T09:15:00","2026-11-18T15:29:59","2026-02-01T10:00:00"):
            self.assertTrue(validate_session(contract,self.now(text)))
        for text in ("2026-11-18T09:14:59","2026-11-18T15:30:00",
                     "2026-11-24T10:00:00","2026-11-22T10:00:00","2026-01-15T10:00:00"):
            with self.assertRaises(ValueError):validate_session(contract,self.now(text))

    def test_expiry_unknown_year_and_timezone(self):
        for contract,now in (
            ({"exchange_segment":"NSE_EQ","expiry":"2026-11-17"},self.now("2026-11-18T10:00:00")),
            ({"exchange_segment":"NSE_EQ"},self.now("2027-01-04T10:00:00")),
            ({"exchange_segment":"NSE_EQ"},datetime(2026,11,18,10))):
            with self.assertRaises(ValueError):validate_session(contract,now)
        self.assertTrue(validate_session({"exchange_segment":"NSE_EQ"},
                        self.now("2026-11-18T10:00:00").astimezone(timezone.utc)))

    def test_mcx_partial_holiday_and_preexpiry_gate(self):
        contract={"exchange_segment":"MCX_COMM","valuation_revision":"DHAN_MCX_2026_10",
                  "expiry":"2026-12-30","expiry_epoch":self.now("2026-12-30T23:55:00").timestamp(),
                  "entry_cutoff":self.now("2026-12-29T23:25:00").timestamp()}
        self.assertTrue(validate_session(contract,self.now("2026-11-24T17:00:00")))
        for text in ("2026-11-24T10:00:00","2026-12-25T18:00:00","2026-12-29T23:25:00"):
            with self.assertRaises(ValueError):validate_session(contract,self.now(text))
        contract["valuation_revision"]="unknown"
        with self.assertRaises(ValueError):validate_session(contract,self.now("2026-11-18T18:00:00"))

    def test_nse_derivative_calendar_and_exact_classification(self):
        contract={"exchange_segment":"NSE_FNO","instrument_name":"OPTIDX","expiry":"2026-11-24"}
        for text in ("2026-11-18T09:15:00","2026-11-18T15:29:59","2026-02-01T10:00:00"):
            self.assertTrue(validate_session(contract,self.now(text)))
        for text in ("2026-01-15T10:00:00","2026-11-24T10:00:00","2026-11-18T15:30:00"):
            with self.assertRaises(ValueError):validate_session(contract,self.now(text))
        contract["instrument_name"]=""
        with self.assertRaisesRegex(ValueError,"classification"):validate_session(contract,self.now("2026-11-18T10:00:00"))

    def test_stock_option_policy_uses_nearest_listed_expiry_not_selected_next_month(self):
        contract={"exchange_segment":"NSE_FNO","instrument_name":"OPTSTK","expiry":"2026-12-29",
                  "stock_option_expiries":["2026-11-19","2026-12-29"]}
        with self.assertRaisesRegex(ValueError,"Equity only"):
            validate_session(contract,self.now("2026-11-18T10:00:00"))
        contract["stock_option_expiries"]=["2026-11-24","2026-12-29"]
        self.assertTrue(validate_session(contract,self.now("2026-11-18T10:00:00")))
        del contract["stock_option_expiries"]
        with self.assertRaisesRegex(ValueError,"expiry evidence"):
            validate_session(contract,self.now("2026-11-18T10:00:00"))

    def test_bse_equity_and_derivatives_use_their_calendar(self):
        for segment in ("BSE_EQ","BSE_FNO"):
            contract={"exchange_segment":segment,"instrument_name":"FUTIDX","expiry":"2026-12-31"}
            self.assertTrue(validate_session(contract,self.now("2026-11-18T10:00:00")))
            self.assertTrue(validate_session(contract,self.now("2026-02-01T10:00:00")))
            for text in ("2026-01-15T10:00:00","2026-11-24T10:00:00","2026-11-18T15:30:00"):
                with self.assertRaises(ValueError):validate_session(contract,self.now(text))
        self.assertTrue(validate_session({"exchange_segment":"BSE_EQ"},self.now("2026-11-18T10:00:00")))

    def test_nse_currency_holidays_and_hours_are_distinct_from_equities(self):
        contract={"exchange_segment":"NSE_CURRENCY","instrument_name":"FUTCUR",
                  "native_symbol":"USDINR-DEC2026-FUT","expiry":"2026-12-29"}
        for text in ("2026-11-18T09:00:00","2026-11-18T16:59:59"):
            self.assertTrue(validate_session(contract,self.now(text)))
        for text in ("2026-11-18T08:59:59","2026-11-18T17:00:00","2026-02-19T10:00:00",
                     "2026-03-19T10:00:00","2026-04-01T10:00:00","2026-08-26T10:00:00",
                     "2026-02-01T10:00:00"):
            with self.assertRaises(ValueError):validate_session(contract,self.now(text))
        for symbol in ("EURUSD-DEC2026-FUT","USDINRFAKE",""):
            with self.assertRaisesRegex(ValueError,"trading hours"):
                validate_session(dict(contract,native_symbol=symbol),self.now("2026-11-18T10:00:00"))

    def test_server_conditional_expiry_uses_exact_current_session_and_contract(self):
        for segment,closing in (("NSE_EQ","15:30:00"),("BSE_FNO","15:30:00"),("NSE_CURRENCY","17:00:00")):
            contract=dict(symbol=segment+":123",exchange_segment=segment,expiry="2026-12-29",
                          instrument_name="FUTCUR" if segment=="NSE_CURRENCY" else "FUTIDX",
                          native_symbol="USDINR-DEC2026-FUT")
            plan=SimpleNamespace(broker="DHAN",symbol=contract["symbol"])
            now=self.now("2026-11-18T10:00:00").timestamp()
            self.assertEqual(conditional_expiry(plan,{"contract":contract},now),
                             self.now("2026-11-18T"+closing).timestamp())
            with self.assertRaises(ValueError):
                conditional_expiry(SimpleNamespace(broker="DHAN",symbol="other"),{"contract":contract},now)

    def test_currency_expiry_day_needs_explicit_native_cutoff(self):
        contract=dict(exchange_segment="NSE_CURRENCY",instrument_name="FUTCUR",
                      native_symbol="USDINR-NOV2026-FUT",expiry="2026-11-18")
        now=self.now("2026-11-18T10:00:00")
        with self.assertRaises(ValueError):validate_session(contract,now)
        contract["currency_entry_cutoff"]=self.now("2026-11-18T12:00:00").timestamp()
        self.assertTrue(validate_session(contract,now))
        with self.assertRaises(ValueError):validate_session(contract,self.now("2026-11-18T12:00:00"))
        plan=SimpleNamespace(broker="DHAN",symbol="NSE_CURRENCY:123")
        contract["symbol"]=plan.symbol
        self.assertEqual(conditional_expiry(plan,{"contract":contract},now.timestamp()),contract["currency_entry_cutoff"])

    def test_mcx_conditional_expiry_respects_preexpiry_cutoff(self):
        now=self.now("2026-11-18T18:00:00")
        contract=dict(symbol="MCX_COMM:123",exchange_segment="MCX_COMM",valuation_revision="DHAN_MCX_2026_10",
            expiry="2026-11-19",expiry_epoch=self.now("2026-11-19T23:55:00").timestamp(),
            entry_cutoff=self.now("2026-11-18T23:25:00").timestamp())
        plan=SimpleNamespace(broker="DHAN",symbol=contract["symbol"])
        self.assertEqual(conditional_expiry(plan,{"contract":contract},now.timestamp()),contract["entry_cutoff"])

    def test_other_segments_do_not_borrow_an_equity_calendar(self):
        for segment in ("BSE_CURRENCY","IDX_I"):
            with self.assertRaisesRegex(ValueError,"calendar"):
                validate_session({"exchange_segment":segment},self.now("2026-11-18T10:00:00"))


if __name__ == "__main__":unittest.main()
