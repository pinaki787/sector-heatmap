from datetime import date
from pathlib import Path
import unittest

from sector_heatmap.web import (
    candidate_has_open_position, chartink_candidate_sectors, closed_position_records, ema_master_row_matches_segment, open_position_underlyings,
    ema_band_entry_checklist, ema_cash_or_index_row_matches_exchange, ema_master_search_rank, ema_open_buy_reconciliation, enrich_chartink_candidates, fetch_chartink_source,
    ema_band_strategy_signal, ema_live_ticket_preview, ema_profit_protection, estimate_fyers_trade_charges, fetch_realized_pnl_report, instrument_route, join_unique_reasons, kama_trade_report, select_ema_atm_option,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class EmaProfitProtectionTests(unittest.TestCase):
    def test_kama_trade_report_pairs_paper_entry_marks_and_exit_pnl(self):
        records = [
            {"source": "PAPER", "at": "2026-09-15T10:15:00+05:30", "lifecycle": "PAPER_ENTRY",
             "signal": {"action": "ENTER_SHORT"}, "position": {"trade_id": "T1", "symbol": "NSE:NIFTY-PE", "quantity": 130, "entry_price": 100}},
            {"source": "PAPER", "at": "2026-09-15T10:20:00+05:30", "lifecycle": "WATCH",
             "position": {"trade_id": "T1", "symbol": "NSE:NIFTY-PE"}, "paper_mark": {"status": "READY", "price": 105, "unrealized_pnl_rupees": 650}},
            {"source": "PAPER", "at": "2026-09-15T15:20:00+05:30", "lifecycle": "PAPER_EXIT",
             "signal": {"action": "SQUARE_OFF"}, "position": {"trade_id": "T1"}, "exit_price": 110, "realized_pnl_rupees": 1300},
        ]
        report = kama_trade_report(records)
        self.assertEqual(report["summary"]["closed_trades"], 1)
        self.assertEqual(report["summary"]["realized_pnl_rupees"], 1300.0)
        self.assertEqual(report["trades"][0]["exit_price"], 110)

    def test_intraday_charge_estimate_uses_fills_and_unique_orders(self):
        estimate = estimate_fyers_trade_charges([
            {"symbol": "NSE:NIFTY2691523500PE", "tradeValue": 10000, "side": 1, "orderNumber": "ONE"},
            {"symbol": "NSE:NIFTY2691523500PE", "tradeValue": 10000, "side": -1, "orderNumber": "TWO"},
            {"symbol": "NSE:NIFTY2691523500PE", "tradeValue": 5000, "side": 1, "orderNumber": "ONE"},
        ])
        self.assertTrue(estimate["available"])
        self.assertEqual(estimate["orders"], 2)
        self.assertEqual(estimate["breakdown"]["brokerage"], 40.0)
        self.assertEqual(estimate["breakdown"]["stt_ctt"], 15.0)
        self.assertGreater(estimate["total"], 55.0)
    def test_progressively_protects_profit_without_lowering_stop(self):
        initial = ema_profit_protection(100, 100, 20)
        self.assertEqual(initial["stop_price"], 80.0)
        breakeven = ema_profit_protection(100, 120, 20, peak_price=120, prior_stop=initial["stop_price"])
        self.assertEqual(breakeven["stop_price"], 100.0)
        self.assertEqual(breakeven["stage"], "BREAKEVEN")
        trailed = ema_profit_protection(100, 140, 20, peak_price=140, prior_stop=breakeven["stop_price"])
        self.assertEqual(trailed["stop_price"], 124.0)
        self.assertEqual(trailed["stage"], "TRAIL_40_PERCENT_GIVEBACK")
        exit_signal = ema_profit_protection(100, 123, 20, peak_price=140, prior_stop=trailed["stop_price"])
        self.assertTrue(exit_signal["exit"])


class RealizedPnlReportTests(unittest.TestCase):
    def test_open_position_duplicate_detection_uses_underlying_and_ignores_squared_off_rows(self):
        exposures = open_position_underlyings([
            {"symbol": "NSE:SOLARINDS26SEP23500CE", "underlying": "NSE:SOLARINDS-EQ", "netQty": 50},
            {"symbol": "NSE:TCS-EQ", "netQty": 0},
        ])
        self.assertTrue(candidate_has_open_position({"symbol": "NSE:SOLARINDS-EQ", "ticker": "SOLARINDS"}, exposures))
        self.assertFalse(candidate_has_open_position({"symbol": "NSE:TCS-EQ", "ticker": "TCS"}, exposures))

    def test_chartink_manual_fetch_is_host_scoped_and_source_only(self):
        class Response:
            text = '<a href="/stocks/RELIANCE">Reliance</a><a href="/stocks/TCS">TCS</a>'
            def raise_for_status(self): pass
        result = fetch_chartink_source(
            "https://chartink.com/screener/example",
            requester=lambda *args, **kwargs: Response(),
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["candidates"], ["RELIANCE", "TCS"])
        self.assertIn("REQUIRES_COMPLETED_CANDLE", result["validation"])
        with self.assertRaisesRegex(ValueError, "Chartink"):
            fetch_chartink_source("https://example.com/screener/example", requester=lambda *args, **kwargs: Response())

    def test_chartink_page_shell_is_never_mislabeled_empty(self):
        class Response:
            text = '<html><title>Screener</title><div>scan_clause</div></html>'
            def raise_for_status(self): pass
        result = fetch_chartink_source("https://chartink.com/screener/example", requester=lambda *args, **kwargs: Response())
        self.assertEqual(result["status"], "ACCESS_REQUIRED")
        self.assertIsNone(result["count"])

    def test_chartink_price_enrichment_is_provider_stamped_and_fail_closed(self):
        def quotes(request):
            self.assertEqual(request["symbols"], "NSE:RELIANCE-EQ,NSE:TCS-EQ")
            return {"s": "ok", "d": [
                {"n": "NSE:RELIANCE-EQ", "v": {"lp": 1405.5, "ch": 12.25, "chp": 0.88, "tt": "1788610500"}},
                {"n": "NSE:TCS-EQ", "v": {"lp": 0, "ch": -5, "chp": -0.1, "tt": 1788610500}},
            ]}
        result = enrich_chartink_candidates(["RELIANCE", "TCS"], quotes)
        self.assertEqual(result["market_data_available"], 1)
        self.assertEqual(result["market_data"]["RELIANCE"]["day_change"], 12.25)
        self.assertNotIn("TCS", result["market_data"])
        self.assertEqual(result["market_data_provider"], "FYERS_READ_ONLY")
        self.assertEqual(result["market_data_schema"], 1)
        self.assertIn("1 of 2", result["market_data_error"])

    def test_chartink_sectors_use_only_official_constituent_mapping(self):
        result = chartink_candidate_sectors(["BRITANNIA", "JINDALSTEL", "UNKNOWN"], {"BRITANNIA": "Consumer Staples"})
        self.assertEqual(result["sectors"]["BRITANNIA"], "Consumer Staples")
        self.assertEqual(result["sector_origins"]["BRITANNIA"], "CHARTINK_SOURCE")
        self.assertEqual(result["sectors"]["JINDALSTEL"], "Metal")
        self.assertEqual(result["sector_origins"]["JINDALSTEL"], "NSE_INDEX_FALLBACK")
        self.assertNotIn("UNKNOWN", result["sectors"])
        self.assertEqual(result["sector_source"], "CHARTINK_WITH_NSE_INDICES_FALLBACK")

    def test_handoff_instrument_route_is_explicit_and_non_mixed(self):
        self.assertEqual(instrument_route({"instrument_route": "cash_equity"}), "cash_equity")
        self.assertEqual(instrument_route({"instrument_route": "stock_options"}), "stock_options")
        for payload in ({}, {"instrument_route": "both"}, {"instrument_route": "index_options"}):
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "Cash equity or Stock options"):
                instrument_route(payload)

    def test_dashboard_asset_version_identifies_route_split(self):
        index = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")
        self.assertRegex(index, r"/ema-crossover-live\.js\?v=[^\"]+")
        self.assertIn("/ema-crossover-live.js?v=", index)

    def test_ema_band_stock_option_search_excludes_futures_in_the_same_fo_master(self):
        future = ["token", "NIFTY 30 Sep 26 FUT", "11", "65", "0.05", "", "", "", "", "NSE:NIFTY26SEPFUT", "10", "11", "", "NIFTY", "", "-1", "XX"]
        option = ["token", "NIFTY 30 Sep 26 25000 CE", "14", "65", "0.05", "", "", "", "", "NSE:NIFTY26SEP25000CE", "10", "11", "", "NIFTY", "", "25000", "CE"]
        self.assertFalse(ema_master_row_matches_segment(future, "stock-option"))
        self.assertTrue(ema_master_row_matches_segment(option, "stock-option"))
        self.assertTrue(ema_master_row_matches_segment(future, "fno"))

    def test_ema_band_search_ranks_the_exact_broker_underlying_before_a_substring(self):
        needle = "NIFTY"
        nifty = {"symbol": "NSE:NIFTY2690825000CE", "underlying": "NIFTY"}
        bank_nifty = {"symbol": "NSE:BANKNIFTY2690845000CE", "underlying": "BANKNIFTY"}
        self.assertLess(ema_master_search_rank(nifty, needle), ema_master_search_rank(bank_nifty, needle))

    def test_ema_band_bse_index_is_eligible_for_picker_and_atm_resolution(self):
        sensex = ["token", "SENSEX-INDEX", "10", "0", "0.01", "", "", "", "", "BSE:SENSEX-INDEX"]
        self.assertTrue(ema_cash_or_index_row_matches_exchange(sensex, "BSE"))
        self.assertFalse(ema_cash_or_index_row_matches_exchange(sensex, "NSE"))

    def test_ema_band_atm_option_uses_nearest_unexpired_expiry_before_strike_distance(self):
        def option(symbol, expiry, strike):
            return ["token", symbol, "14", "65", "0.05", "", "", "", str(expiry), symbol, "10", "11", "", "NIFTY", "", str(strike), "CE"]
        # The later expiry has the exact spot strike.  It must not win over the
        # nearest expiry, whose available CE is deliberately farther from spot.
        rows = [option("NSE:NIFTYNEAR25000CE", 2_000, 24_950), option("NSE:NIFTYLATER25100CE", 3_000, 25_100)]
        contract = select_ema_atm_option(rows, "NIFTY", "BULLISH", 25_100, now_epoch=1_000)
        self.assertEqual(contract["symbol"], "NSE:NIFTYNEAR25000CE")
        self.assertEqual(contract["option_type"], "CE")

    def test_ema_band_atm_option_maps_bearish_direction_to_put(self):
        row = ["token", "NSE:NIFTYNEAR25000PE", "14", "65", "0.05", "", "", "", "2000", "NSE:NIFTYNEAR25000PE", "10", "11", "", "NIFTY", "", "25000", "PE"]
        contract = select_ema_atm_option([row], "NIFTY", "BEARISH", 25_000, now_epoch=1_000)
        self.assertEqual(contract["option_type"], "PE")

    def test_ema_live_ticket_sizes_by_lots_and_derives_stop_and_target_from_pct(self):
        contract = {"symbol": "NSE:NIFTYNEAR25000CE", "description": "NIFTY CE", "option_type": "CE", "strike": 25000,
                    "expiry_epoch": 2_000, "lot_size": 10, "tick_size": 0.05}
        ticket = ema_live_ticket_preview(contract, {"bid": 101.0, "ask": 102.0}, 2, 20, 40)
        self.assertEqual(ticket["status"], "LIVE_ORDER_READY")
        self.assertEqual(ticket["action"], "BUY")
        self.assertEqual(ticket["quantity"], 20)
        self.assertEqual(ticket["limit_price"], 102.0)
        self.assertLess(ticket["stop_price"], ticket["limit_price"])
        self.assertGreater(ticket["target_price"], ticket["limit_price"])
        with self.assertRaisesRegex(ValueError, "stop-loss"):
            ema_live_ticket_preview(contract, {"bid": 101.0, "ask": 102.0}, 2, 150, 40)

    def test_ema_live_ticket_stop_and_target_are_optional_indicator_drives_exit(self):
        contract = {"symbol": "NSE:NIFTYNEAR25000CE", "description": "NIFTY CE", "option_type": "CE", "strike": 25000,
                    "expiry_epoch": 2_000, "lot_size": 10, "tick_size": 0.05}
        ticket = ema_live_ticket_preview(contract, {"bid": 101.0, "ask": 102.0}, 2)
        self.assertIsNone(ticket["stop_price"])
        self.assertIsNone(ticket["target_price"])
        self.assertEqual(ticket["exit_mode"], "INDICATOR_ONLY")
        with_stop_only = ema_live_ticket_preview(contract, {"bid": 101.0, "ask": 102.0}, 2, stop_loss_pct=20)
        self.assertIsNotNone(with_stop_only["stop_price"])
        self.assertIsNone(with_stop_only["target_price"])
        self.assertEqual(with_stop_only["exit_mode"], "PERCENT_AND_INDICATOR")

    def test_ema_band_completed_signal_derives_direction_before_option_type(self):
        bullish = [
            {"timestamp": 1, "open": 100, "high": 100, "low": 99, "close": 100},
            {"timestamp": 2, "open": 100, "high": 102, "low": 100, "close": 103},
            {"timestamp": 3, "open": 102, "high": 105, "low": 101, "close": 104},
        ]
        bearish = [
            {"timestamp": 1, "open": 100, "high": 101, "low": 100, "close": 100},
            {"timestamp": 2, "open": 102, "high": 102, "low": 98, "close": 97},
            {"timestamp": 3, "open": 98, "high": 99, "low": 95, "close": 96},
        ]
        self.assertEqual(ema_band_strategy_signal(bullish, 2)["direction"], "BULLISH")
        self.assertEqual(ema_band_strategy_signal(bearish, 2)["direction"], "BEARISH")

    def test_ema_runner_reconciliation_requires_exact_symbol_and_full_open_quantity(self):
        confirmed = {"s": "ok", "netPositions": [{"symbol": "NSE:NIFTY26000CE", "netQty": 50, "buyQty": 50}]}
        squared_off = {"s": "ok", "netPositions": [{"symbol": "NSE:NIFTY26000CE", "netQty": 0, "buyQty": 50}]}
        partial = {"s": "ok", "netPositions": [{"symbol": "NSE:NIFTY26000CE", "netQty": 25, "buyQty": 50}]}
        wrong_symbol = {"s": "ok", "netPositions": [{"symbol": "NSE:NIFTY26000PE", "netQty": 50, "buyQty": 50}]}
        self.assertEqual(ema_open_buy_reconciliation(confirmed, "NSE:NIFTY26000CE", 50)[0], "CONFIRMED")
        for response in (squared_off, partial, wrong_symbol):
            with self.subTest(response=response):
                self.assertEqual(ema_open_buy_reconciliation(response, "NSE:NIFTY26000CE", 50)[0], "ABSENT_OR_PARTIAL")
        self.assertEqual(ema_open_buy_reconciliation({"s": "error"}, "NSE:NIFTY26000CE", 50)[0], "UNAVAILABLE")

    def test_ema_entry_checklist_reports_completed_candle_conditions(self):
        candles = [
            {"timestamp": 1, "open": 100, "high": 101, "low": 99, "close": 100},
            {"timestamp": 2, "open": 100, "high": 103, "low": 100, "close": 104},
            {"timestamp": 3, "open": 102, "high": 105, "low": 101, "close": 103},
        ]
        checklist = ema_band_entry_checklist(candles, 2)
        self.assertTrue(checklist["checks"]["sufficient_completed_history"]["pass"])
        self.assertTrue(checklist["checks"]["current_candle_completed"]["pass"])
        self.assertIn("prior_body_crosses_ema_high_long", checklist["checks"])
        self.assertIn("current_close_below_midpoint_short", checklist["checks"])
        self.assertEqual(checklist["checks"]["session_gate"]["value"], "disabled")

    def test_ema_runner_clears_stale_context_before_quote_or_exit_management(self):
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        live_section = backend[backend.index('if config["mode"] == "LIVE" and position:'):backend.index('else:\n                        if config["mode"] == "LIVE" and broker_has_open_position():')]
        self.assertLess(live_section.index("ema_open_buy_reconciliation("), live_section.index('client.quotes({"symbols": position["symbol"]})'))
        self.assertIn('"status": "LIVE_POSITION_RECONCILIATION_FAILED"', live_section)
        self.assertIn('ema_runner["position"] = None', live_section)
        self.assertIn('ema_runner["chart"] = None', live_section)
        self.assertIn("result == \"CONFIRMED\"", backend)
        self.assertIn('not ema_runner["running"] or ema_runner.get("position") != position', backend)
        self.assertIn('"last_watch_key"', backend)
        self.assertIn("CURRENT RUNNER", dashboard)
        self.assertIn("HISTORICAL JOURNAL", dashboard)

    def test_ema_band_segment_change_requeries_and_clears_the_previous_contract(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn("$('ema-band-segment').addEventListener('change'", dashboard)
        self.assertIn("clearEmaMasterSelection(); searchEmaMaster()", dashboard)
        self.assertIn("item.underlying || '—'", dashboard)

    def test_ema_band_ui_uses_underlying_and_strategy_direction_not_a_raw_option_picker(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('id="ema-band-underlying-search"', dashboard)
        self.assertNotIn('name="ema-band-option-direction"', dashboard)
        self.assertIn('id="ema-band-strategy-direction"', dashboard)
        self.assertIn("/api/ema-band/atm-option?underlying=", dashboard)
        self.assertIn("&timeframe=", dashboard)
        self.assertIn("nearest expiry ${expiry}, nearest ATM strike", dashboard)

    def test_ema_band_live_mode_can_submit_real_fyers_orders(self):
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('submission_available = bool(broker["fyers_configured"] and broker["live_submission_enabled"])', backend)
        self.assertIn('SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=1 runtime gate', backend)
        self.assertIn('/api/ema-band/mode-capability', backend)
        self.assertIn('id="ema-band-mode"', dashboard)
        self.assertIn('Live (auto order submission)', dashboard)
        self.assertIn('/api/ema-band/mode-capability?mode=', dashboard)

    def test_ema_band_runner_monitors_paper_or_submits_live_orders(self):
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('"PAPER_ENTRY_RECORDED"', backend)
        self.assertIn('"LIVE_ENTRY_SUBMITTED"', backend)
        self.assertIn('"LIVE_EXIT_SUBMITTED"', backend)
        self.assertIn('ema_live_ticket_preview(', backend)
        self.assertIn('submit_live_entry(', backend)
        self.assertIn('submit_live_exit(', backend)
        self.assertIn('path == "/api/ema-band/runner/start"', backend)
        self.assertIn('id="ema-band-runner-toggle"', dashboard)
        self.assertIn('id="ema-band-ticket-preview"', dashboard)
        self.assertIn('Live mode places real FYERS orders with real money.', dashboard)
        self.assertIn('Start Runner', dashboard)
        self.assertIn('/api/ema-band/runner/start', dashboard)
        self.assertIn("window.confirm('Start the LIVE EMA Band runner?", dashboard)

    def test_ema_chart_requests_oi_and_exposes_retained_position_registry(self):
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('"oi_flag": 1', backend)
        self.assertIn('"open_interest": float(row[6])', backend)
        self.assertIn('path == "/api/ema-band/tracked-positions"', backend)
        self.assertIn('PAPER_ENTRY_RECORDED', backend)
        self.assertIn('def ema_rsi_series', backend)
        self.assertIn('"rsi_14"', backend)
        self.assertIn('id="ema-band-position-cards"', dashboard)
        self.assertIn('loadEmaTrackedPositions', dashboard)
        self.assertIn('green long buildup, red short buildup, blue short covering, and amber long unwinding', dashboard)
        self.assertIn('oiProfile', dashboard)
        self.assertIn('RSI ${rsiLength}', dashboard)

    def test_stopping_ema_runner_clears_only_transient_display_context(self):
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        stop_section = backend[backend.index("    def stop_ema_runner():"):backend.index("    def ema_master_refresh_loop():")]
        self.assertIn('"last_event": None', stop_section)
        self.assertIn('"last_signal_key": None', stop_section)
        self.assertIn('"position": None, "chart": None', stop_section)
        self.assertNotIn("ema_runner_paper_log", stop_section)
        self.assertNotIn("ema_runner_live_log", stop_section)
        self.assertIn("const event = running ? state?.last_event || {} : {}", dashboard)
        self.assertIn("renderEmaBandChart(running ? state?.chart : null)", dashboard)

    def test_ema_band_picker_keeps_master_validated_bse_and_mcx_option_coverage(self):
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('def ema_cash_or_index_row_matches_exchange', backend)
        self.assertIn('endswith("-INDEX")', backend)
        self.assertIn('("MCX_COM", "MCX_COM") if exchange == "MCX"', backend)
        self.assertIn('"COMMODITY_FUTURE"', backend)
        self.assertIn('CRUDEOIL', dashboard)
        self.assertIn('MCX commodity future', dashboard)

    def test_authentication_refresh_tracks_authoritative_account_state(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn("button.disabled = connected === true", dashboard)
        self.assertIn("setAuthenticationControl(data.connected === true)", dashboard)
        self.assertIn("setAuthenticationControl(false)", dashboard)
        self.assertIn('aria-describedby="reauth-help"', dashboard)

    def test_screener_auto_refresh_is_local_bounded_and_source_only(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn("const screenerRefreshIntervals = [0, 5, 15, 30, 60]", dashboard)
        self.assertIn("const defaultScreenerRefreshMs = 15 * 60 * 1000", dashboard)
        self.assertIn("Custom auto-refresh must be a whole number from 5 to 1440 minutes", dashboard)
        self.assertIn("Auto-refresh every ${source.refresh_interval_ms / 60000} minutes", dashboard)
        self.assertIn("if (blocked || document.hidden) return", dashboard)
        self.assertIn("screenerRefreshInFlight.has(source.id)", dashboard)
        self.assertIn("refreshScreenerSource(source.id, 'auto')", dashboard)
        self.assertIn("Source auto-refresh can only update Chartink membership and read-only quote fields", dashboard)

    def test_screener_market_cap_replaces_marketplace_and_is_first_after_symbol(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertNotIn("Marketplace Name", dashboard)
        self.assertNotIn("source_marketplaces", dashboard)
        sector_header = "screenerSortHeader(source.id, 'sector', 'Sector', sort)"
        symbol_header = "screenerSortHeader(source.id, 'symbol', 'Symbol', sort)"
        cap_header = "screenerSortHeader(source.id, 'market_cap', 'Market Cap (₹ cr)', sort)"
        self.assertLess(dashboard.index(sector_header, dashboard.index("<thead>")), dashboard.index(symbol_header, dashboard.index("<thead>")))
        self.assertLess(dashboard.index(symbol_header, dashboard.index("<thead>")), dashboard.index(cap_header, dashboard.index("<thead>")))
        self.assertIn("unavailable values are not estimated", dashboard)
        for control in ("screener-price-min", "screener-price-max", "screener-change-pct-min", "screener-change-pct-max", "screener-price-as-of"):
            self.assertIn(control, dashboard)

    def test_screener_order_requires_one_selected_plan_and_fresh_fyers_preflight(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('type="checkbox" class="screener-plan-select"', dashboard)
        self.assertIn("if (!screenerSelectedPlans.size)", dashboard)
        self.assertIn("require_market_open: true", dashboard)
        self.assertIn("preview_id: screenerOrderPreview.preview_id", dashboard)
        self.assertIn("event.target.value !== screenerOrderPreview?.confirmation_phrase", dashboard)
        self.assertIn("/api/trade-ticket/prepare-batch", dashboard)
        self.assertIn("Select all high-conviction equities", dashboard)
        self.assertIn("Clear selection", dashboard)
        self.assertIn("allocateScreenerPlansByFunds", dashboard)
        self.assertIn("Allocated from fresh FYERS available funds", dashboard)
        self.assertIn("suggested_quantity", dashboard)
        self.assertIn("#screener-analysis-results .screener-plan-select", dashboard)

    def test_nifty_straddle_ui_exposes_the_external_runner_options(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        self.assertIn('data-view="straddles"', dashboard)
        self.assertIn('data-straddle-market="sensex"', dashboard)
        self.assertIn('data-straddle-market="nifty"', dashboard)
        self.assertIn('id="straddles"', dashboard)
        self.assertIn("NIFTY Long Straddle", dashboard)
        self.assertIn('id="nifty-straddle-lots"', dashboard)
        self.assertIn('id="nifty-straddle-stoploss"', dashboard)
        self.assertIn('id="nifty-straddle-target"', dashboard)
        self.assertIn("/api/nifty-straddle/${action}", dashboard)
        self.assertIn('path == "/api/nifty-straddle"', backend)

    def test_screener_advisory_lists_only_high_conviction_passes(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn("item.decision === 'PASS' && item.conviction?.rating === 'High'", dashboard)
        self.assertIn("watchlist shown separately", dashboard)
        self.assertIn("No candidate currently clears the established high-conviction gates", dashboard)
        self.assertIn("read-only advisory · no automatic selection or order authority", dashboard)
        self.assertIn("Non-actionable · no selection, ticket, or live-order path", dashboard)

    def test_screener_analysis_runs_only_selected_symbols_in_safe_batches(self):
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn("await analyzeScreenerCandidates(false)", dashboard)
        self.assertIn('class="screener-candidate-select"', dashboard)
        self.assertIn('screener-source-select-all', dashboard)
        self.assertIn("screenerAnalysisSymbols = [...screenerCandidateSelections]", dashboard)
        self.assertIn("symbols: screenerAnalysisSymbols", dashboard)
        self.assertIn("Analyze selected symbols", dashboard)
        self.assertIn("${screenerAnalysisOffset}/${screenerAnalysisSymbols.length} complete", dashboard)
        self.assertIn("screenerAnalysisCancelled = true", dashboard)
        self.assertIn("Complete · ${screenerAnalysisOffset}/${data.total} analyzed", dashboard)

    def test_screener_extra_fields_are_schema_driven_with_safe_type_fallback(self):
        backend = (Path(__file__).resolve().parents[1] / "sector_heatmap" / "web.py").read_text(encoding="utf-8")
        dashboard = (Path(__file__).resolve().parents[1] / "dashboard-enhancements.js").read_text(encoding="utf-8")
        self.assertIn('"source_fields": source_fields, "source_field_schema": source_field_schema', backend)
        self.assertIn('else "text"', backend)
        self.assertIn("dynamicSchema.forEach(field =>", dashboard)
        self.assertIn("key.startsWith('dynamic:')", dashboard)
        self.assertIn("value == null ? 'Unavailable'", dashboard)

    def test_duplicate_rejection_reasons_are_rendered_once(self):
        reason = "Bull call debit spread: analyzed R:R 1:0.78 vs hard gate 1:1."
        self.assertEqual(join_unique_reasons([{"reason": reason}, {"reason": reason}]), reason)

    def test_squared_off_positions_are_available_as_closed_records(self):
        records = closed_position_records([
            {"symbol": "NSE:NIFTY2690823900CE", "netQty": 0, "buyQty": 65, "sellQty": 65,
             "buyAvg": 131.9, "sellAvg": 175.25, "realized_profit": 2817.75},
            {"symbol": "NSE:NIFTY2690823900PE", "netQty": 10, "buyQty": 65, "sellQty": 55,
             "buyAvg": 78.25, "sellAvg": 52.05, "realized_profit": -1703.0},
        ])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["symbol"], "NSE:NIFTY2690823900CE")
        self.assertEqual(records[0]["pnl"], 2817.75)

    def test_supported_report_is_normalized_and_paginated(self):
        calls = []
        first_page = [{"symbol_name": f"STOCK-{index}"} for index in range(100)]

        def requester(url, **kwargs):
            calls.append((url, kwargs))
            if kwargs["params"]["page_no"] == 1:
                return FakeResponse(200, {"s": "ok", "message": "Fetched", "data": first_page, "summary_data": {"net_pnl": 125.5}})
            return FakeResponse(200, {"s": "ok", "message": "Fetched", "data": [{"symbol_name": "LAST"}], "summary_data": {"net_pnl": 125.5}})

        result = fetch_realized_pnl_report("APP-100", "secret-token", date(2026, 8, 1), date(2026, 8, 30), requester=requester)
        self.assertTrue(result["supported"])
        self.assertEqual(len(result["data"]), 101)
        self.assertEqual(result["summary_data"]["net_pnl"], 125.5)
        self.assertEqual([call[1]["params"]["page_no"] for call in calls], [1, 2])
        self.assertEqual(calls[0][1]["headers"]["Authorization"], "APP-100:secret-token")

    def test_unavailable_report_capability_has_graceful_result(self):
        result = fetch_realized_pnl_report(
            "APP-100",
            "secret-token",
            date(2026, 8, 1),
            date(2026, 8, 30),
            requester=lambda *args, **kwargs: FakeResponse(404, {"s": "error", "message": "Not found"}),
        )
        self.assertFalse(result["supported"])
        self.assertIn("not available", result["message"])

    def test_provider_error_and_non_json_response_are_explicit(self):
        with self.assertRaisesRegex(RuntimeError, "access token expired"):
            fetch_realized_pnl_report(
                "APP-100",
                "secret-token",
                date(2026, 8, 1),
                date(2026, 8, 30),
                requester=lambda *args, **kwargs: FakeResponse(401, {"s": "error", "message": "access token expired"}),
            )
        with self.assertRaisesRegex(RuntimeError, "non-JSON"):
            fetch_realized_pnl_report(
                "APP-100",
                "secret-token",
                date(2026, 8, 1),
                date(2026, 8, 30),
                requester=lambda *args, **kwargs: FakeResponse(502, json_error=ValueError("html")),
            )


if __name__ == "__main__":
    unittest.main()
