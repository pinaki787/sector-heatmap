"""Chart endpoint authorization and selected-account routing."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from threading import RLock
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from sector_heatmap.chart_trade_stream import DeltaChartTrades
from sector_heatmap.chart_workspace import combine_bars, delta_live_snapshot, fetch_delta_history, fetch_fyers_history, mcx_history_bars, search_dhan_chart_symbols, serve_history, serve_live


class ChartWorkspaceAccessTests(TestCase):


    def test_fyers_forming_seed_requires_native_coverage_from_bucket_open(self):
        start = int(datetime(2026, 11, 16, 3, 45, tzinfo=timezone.utc).timestamp())
        now = datetime.fromtimestamp(start + 35 * 60, timezone.utc)
        candles = [[start, 101, 108, 99, 105, 110], [start + 1800, 105, 109, 104, 107, 25]]
        response = {"s": "ok", "candles": candles}
        with patch("sector_heatmap.fyers_history.history", return_value=response):
            payload = fetch_fyers_history(Mock(), "60", now, after=start - 3600, include_forming=True)
            self.assertEqual(payload["rows"], [])
            self.assertEqual(payload["fyers_forming_seed"], {
                "bar": [start, 101, 109, 99, 107, 135], "sampled_at": int(now.timestamp()),
            })
            response["candles"] = candles[1:]
            missing = fetch_fyers_history(Mock(), "60", now, after=start - 3600, include_forming=True)
            self.assertEqual(missing, {"rows": []})

    def test_fyers_mid_session_quote_supplies_forming_daily_ohlcv(self):
        from sector_heatmap.chart_workspace import FyersChartBars

        bars = FyersChartBars("BSE:LAURUSLABS-A")
        stamp = int(datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc).timestamp())
        session = int(datetime(2026, 11, 15, 18, 30, tzinfo=timezone.utc).timestamp())
        tick = {
            "symbol": bars.symbol, "exch_feed_time": stamp, "last_traded_time": stamp,
            "ltp": 105, "open_price": 101, "high_price": 108, "low_price": 99,
            "vol_traded_today": 12000,
        }
        bars.ingest(tick, now=stamp)
        self.assertFalse(bars.session_covered)
        self.assertEqual(bars.snapshot("1D", True)["rows"], [[session, 101, 108, 99, 105, 12000, session]])
        self.assertEqual(bars.snapshot("1D", False)["rows"], [])
        self.assertEqual(bars.snapshot(30, True)["rows"], [])

        bars.ingest({**tick, "exch_feed_time": stamp + 1, "last_traded_time": stamp - 86400}, now=stamp + 1)
        self.assertEqual(bars.snapshot("1D", True)["rows"], [])
        bars.ingest({**tick, "exch_feed_time": stamp + 2, "high_price": 100}, now=stamp + 2)
        self.assertEqual(bars.snapshot("1D", True)["rows"], [])
        bars.reset_coverage()
        self.assertEqual(bars.snapshot("1D", True)["rows"], [])

    def test_delta_same_timestamp_trades_do_not_cross_seconds_boundary(self):
        stream = DeltaChartTrades()
        stream.reset(5_000_000)
        stream.pending = [
            (9_999_999, 1, 100, 2, 1),
            (9_999_999, 2, 101, 3, -1),
            (10_000_000, 3, 102, 4, 0),
        ]

        completed = stream.snapshot("5S", now=18)["completed"]
        self.assertEqual(completed, [[5, 100, 101, 100, 101, 5], [10, 102, 102, 102, 102, 4]])

        ticks = stream.snapshot("1T", now=18)["completed"]
        self.assertEqual([row[4] for row in ticks], [100, 101, 102])
        times = [row[0] for row in ticks]
        self.assertEqual(times, sorted(set(times)))

    def test_delta_trade_volume_uses_aggressor_side_and_marks_unknown_buckets(self):
        stream = DeltaChartTrades()
        stream.reset(5_000_000)
        stream.ingest({"type": "subscriptions", "channels": [{"name": "trades", "symbols": ["BTCUSD"]}]})
        with patch("sector_heatmap.chart_trade_stream.time.time", return_value=6.3):
            for stamp, price, size, role in (
                (5_100_000, 100, 5, "t"),
                (5_200_000, 101, 8, "m"),
                (5_300_000, 102, 4, "t"),
                (6_100_000, 103, 2, None),
                (6_200_000, 104, 8, "t"),
            ):
                stream.ingest({"type": "trades", "sy": "BTCUSD", "t": stamp, "p": price, "s": size, "r": role})
        frame = stream.snapshot("1S", now=10, delta_width=1)
        self.assertEqual(frame["trade_delta"], {"method": "aggressor_side", "segments": [
            {"from": 5, "through": 7, "active": True, "rows": [[5, 0, 5, -3, 1], [6, None, None, None, None]]},
        ]})
        self.assertEqual(stream.snapshot("1S", now=10)["completed"][0], [5, 100, 102, 100, 102, 17])

    def test_tick_delta_uses_utc_candle_boundaries_with_partial_midnight_bucket(self):
        stream = DeltaChartTrades()
        stream.reset(84_000_000_000)
        stream.connected = True
        stream.pending = [
            (85_000_000_000, 1, 100, 3, 1),
            (86_399_000_000, 2, 101, 2, -1),
            (86_400_000_000, 3, 102, 8, 1),
            (87_000_000_000, 4, 103, 5, -1),
        ]
        frame = stream.snapshot(840, now=87_500, delta_width=840 * 60)
        # Capture started mid-bucket, so only the new UTC-day bucket is represented.
        self.assertEqual(frame["trade_delta"]["segments"][0], {
            "from": 86_400, "through": 87_497, "active": True, "rows": [[86_400, 0, 8, 0, 3]],
        })

    def test_tick_delta_routes_to_the_selected_delta_symbol_and_time_interval(self):
        guard = SimpleNamespace(store=SimpleNamespace(sidebar_visibility=lambda: {"chart-workspace": True}))
        user = {"features": ["chart-workspace"]}
        live = Mock(return_value={"trade_delta": {"method": "aggressor_side", "segments": []}})
        for broker, interval, expected in (("DELTA_INDIA", "30", 200), ("DELTA_INDIA", "1W", 400), ("FYERS", "30", 400)):
            with self.subTest(broker=broker, interval=interval):
                symbol = "BTCUSD" if broker == "DELTA_INDIA" else "NSE:NIFTY50-INDEX"
                handler = SimpleNamespace(workspace_identity=(user, {"broker": broker}), send_json=Mock(),
                    path=f"/api/chart-workspace/live?interval={interval}&symbol={symbol}&trade_delta=1")
                live.reset_mock()
                serve_live(handler, None, guard, None, None, live)
                self.assertEqual(handler.send_json.call_args.args[0], expected)
                if expected == 200:
                    live.assert_called_once_with(30, symbol="BTCUSD", trade_delta=True)
                else:
                    live.assert_not_called()

    def test_custom_seconds_and_tick_intervals_dispatch_only_to_delta_trade_capture(self):
        guard = SimpleNamespace(store=SimpleNamespace(sidebar_visibility=lambda: {"chart-workspace": True}))
        user = {"features": ["chart-workspace"]}
        frame = {"rows": [], "completed": [], "connected": True}
        fyers_feed = Mock()
        for interval in ("1S", "7S", "95S", "299S", "1T", "10T", "100T", "1000T"):
            with self.subTest(interval=interval):
                delta = Mock(return_value=frame)
                handler = SimpleNamespace(
                    workspace_identity=(user, {"broker": "DELTA_INDIA"}),
                    send_json=Mock(),
                    path="/api/chart-workspace/live?" + urlencode({"interval": interval, "symbol": "PAXGUSD"}),
                )
                serve_live(handler, None, guard, None, None, delta)
                delta.assert_called_once_with(interval, symbol="PAXGUSD")
                handler.send_json.assert_called_once_with(200, frame)

                handler.workspace_identity = (user, {"broker": "FYERS"})
                handler.path = "/api/chart-workspace/live?" + urlencode(
                    {"interval": interval, "symbol": "NSE:NIFTY50-INDEX"}
                )
                handler.send_json.reset_mock()
                delta.reset_mock()
                serve_live(handler, None, guard, None, fyers_feed, delta)
                self.assertEqual(handler.send_json.call_args.args[0], 400)
                delta.assert_not_called()
                fyers_feed.chart_bars_for.assert_not_called()

    def test_delta_calendar_older_page_excludes_cursor_and_incomplete_period(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = datetime(2023, 4, 1, tzinfo=timezone.utc)
        daily = []
        for index in range((now - first).days):
            stamp = int((first + timedelta(days=index)).timestamp())
            price = 100 + index
            daily.append(dict(time=stamp, open=price, high=price + 2,
                              low=price - 1, close=price + 1, volume=10))

        def candles(path, params):
            self.assertEqual(path, "/v2/history/candles")
            self.assertEqual(params["resolution"], "1d")
            # The open at the cursor can be returned by the provider's inclusive query.
            return {"result": [row for row in daily if params["start"] <= row["time"] <= params["end"]]}

        delta = SimpleNamespace(clock=lambda: now.timestamp(), _get=candles)
        for interval, boundary, expected_start, expected_days in (
            ("1W", datetime(2025, 12, 29, tzinfo=timezone.utc), datetime(2025, 12, 22, tzinfo=timezone.utc), 7),
            ("1M", datetime(2025, 12, 1, tzinfo=timezone.utc), datetime(2025, 11, 1, tzinfo=timezone.utc), 30),
            ("12M", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc), 366),
        ):
            with self.subTest(interval=interval):
                cursor = int(boundary.timestamp())
                result = fetch_delta_history(delta, interval, before=cursor)
                self.assertIsNone(result["prefix"])
                self.assertTrue(all(row[0] < cursor for row in result["rows"]))
                first_day = (expected_start - first).days
                opening, closing = daily[first_day], daily[first_day + expected_days - 1]
                self.assertEqual(result["rows"][-1], [
                    expected_start.timestamp(), opening["open"], closing["high"], opening["low"],
                    closing["close"], expected_days * 10,
                ])
                with self.assertRaisesRegex(ValueError, "calendar candle boundary"):
                    fetch_delta_history(delta, interval, before=cursor + 86400)
                if interval == "12M":
                    self.assertEqual(len(result["rows"]), 1)  # Partial 2023 must not appear.

    def test_delta_empty_history_is_a_successful_broker_response(self):
        from types import SimpleNamespace

        delta = SimpleNamespace(
            clock=lambda: 1770000000,
            product=lambda symbol, **options: {},
            _get=lambda path, params: {"result": []},
        )
        self.assertEqual(fetch_delta_history(delta, "30", symbol="AAPLBUSD"), [])
        weekly = fetch_delta_history(delta, "1W", symbol="AAPLBUSD")
        self.assertEqual(weekly["rows"], [])

    def test_delta_custom_hour_history_restarts_at_utc_midnight(self):
        midnight = int(datetime(2026, 11, 5, tzinfo=timezone.utc).timestamp())
        hour = 3600
        for hours in (14, 22, 23):
            with self.subTest(hours=hours):
                native = 2 if hours % 2 == 0 else 1
                rows = [
                    dict(time=midnight + offset * hour, open=100 + offset,
                         high=101 + offset + native, low=99 + offset,
                         close=100 + offset + native, volume=native)
                    for offset in range(-24, 24 + native, native)
                ]

                def history(_path, params):
                    return {"result": [
                        row for row in rows if params["start"] <= row["time"] <= params["end"]
                    ]}

                next_day = midnight + 24 * hour
                delta = SimpleNamespace(clock=lambda: next_day + native * hour, _get=history)
                interval = str(hours * 60)
                result = fetch_delta_history(delta, interval, after=midnight)
                self.assertEqual(result["rows"], [
                    [midnight + hours * hour, 100 + hours, 125, 99 + hours, 124, 24 - hours],
                ])
                self.assertTrue(result["utc_daily"])
                self.assertEqual(result["intraday_prefix"][0][0], next_day)

                older = fetch_delta_history(delta, interval, before=midnight + hours * hour)
                self.assertEqual(older[-1][0], midnight)

                forming = {
                    ("BTCUSD", native * hour, row["time"]): {
                        **row, "timestamp": row["time"], "stream_exchange_at": row["time"] + 1,
                    }
                    for row in rows if row["time"] >= midnight + hours * hour
                }
                stream = SimpleNamespace(lock=RLock(), connected=True, generation=1,
                                         forming_bars=forming)
                live = delta_live_snapshot(stream, hours * 60)
                self.assertEqual([row[0] for row in live["rows"]],
                                 [midnight + hours * hour, next_day])
                self.assertEqual(live["native_row"][0], next_day)
                del forming["BTCUSD", native * hour, next_day]
                self.assertEqual([row[0] for row in delta_live_snapshot(stream, hours * 60)["rows"]],
                                 [midnight + hours * hour])

    def test_nse_custom_hour_candles_stop_at_the_regular_session_close(self):
        opening = int(datetime(2026, 11, 13, 3, 45, tzinfo=timezone.utc).timestamp())
        closing = opening + 375 * 60
        bars = [
            [opening + index * 1800, 100 + index, 102 + index,
             99 + index, 101 + index, 10]
            for index in range(13)
        ]

        six_hours = [
            [opening, 100, 113, 99, 112, 120],
            [opening + 360 * 60, 112, 114, 111, 113, 10],
        ]
        self.assertEqual(combine_bars(bars, 360, 30, closing), six_hours)
        self.assertEqual(combine_bars(bars, 360, 30, closing - 1), six_hours[:1])
        for interval in (840, 1320, 1380):
            with self.subTest(interval=interval):
                self.assertEqual(combine_bars(bars, interval, 30, closing),
                                 [[opening, 100, 114, 99, 113, 130]])
                self.assertEqual(combine_bars(bars, interval, 30, closing - 1), [])
                self.assertEqual(combine_bars(bars[:4] + bars[5:], interval, 30, closing), [])

    def test_delta_annual_candle_starts_at_contract_launch_and_rejects_gaps(self):
        launch_day = datetime(2026, 2, 19, tzinfo=timezone.utc)
        launch = launch_day.replace(hour=13).isoformat()
        dates = [launch_day + timedelta(days=offset) for offset in range(4)]
        candles = [
            {"time": day.timestamp(), "open": 10 + offset, "high": 12 + offset,
             "low": 9 + offset, "close": 11 + offset, "volume": 100}
            for offset, day in enumerate(dates)
        ]
        delta = SimpleNamespace(
            product=Mock(return_value={"launch_time": launch}),
            clock=lambda: (dates[-1] + timedelta(days=1, hours=1)).timestamp(),
            _get=Mock(return_value={"result": candles}),
        )

        result = fetch_delta_history(delta, "12M", symbol="PAXGUSD")
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["prefix"], {
            "bar": [int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()),
                    10, 15, 9, 14, 400],
            "through": int(dates[-1].timestamp()),
        })

        delta._get.return_value = {"result": [candles[0], *candles[2:]]}
        self.assertEqual(fetch_delta_history(delta, "12M", symbol="PAXGUSD"),
                         {"rows": [], "prefix": None})

    def test_access_checked_before_selected_adapter_dispatch(self):
        for endpoint in ("history", "live"):
            for admin, assigned, visible, status in (
                (False, False, True, 403),
                (False, True, False, 403),
                (True, True, False, 403),
                (False, True, True, 200),
            ):
                with self.subTest(endpoint=endpoint, admin=admin, assigned=assigned, visible=visible):
                    user = {"admin": admin, "features": ["chart-workspace"] if assigned else []}
                    guard = SimpleNamespace(store=SimpleNamespace(
                        sidebar_visibility=lambda: {"chart-workspace": visible},
                    ))
                    handler = SimpleNamespace(
                        path=f"/api/chart-workspace/{endpoint}?interval=360",
                        workspace_identity=(user, {"broker": "DELTA_INDIA"}),
                        send_json=Mock(),
                    )
                    other = Mock(side_effect=AssertionError("Unexpected broker adapter"))
                    if endpoint == "history":
                        selected = Mock(return_value=[[60, 1, 2, 1, 2, 0]])
                        serve_history(handler, None, guard, other, selected, other)
                    else:
                        selected = Mock(return_value={"provider": "Delta India", "rows": []})
                        serve_live(handler, None, guard, None, None, selected, other)

                    handler.send_json.assert_called_once()
                    code, payload = handler.send_json.call_args.args
                    self.assertEqual(code, status)
                    other.assert_not_called()
                    if status == 200:
                        self.assertEqual(payload["provider"], "Delta India")
                        if endpoint == "history":
                            selected.assert_called_once_with("360", None)
                        else:
                            selected.assert_called_once_with(360)
                    else:
                        selected.assert_not_called()

    def test_dhan_older_calendar_history_uses_an_exclusive_broker_date(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from sector_heatmap.chart_workspace import fetch_dhan_history

        zone = ZoneInfo("Asia/Kolkata")
        now = datetime(2026, 11, 16, tzinfo=zone)
        boundary = datetime(2019, 1, 1, tzinfo=zone)
        stamp = int(datetime(2018, 1, 1, tzinfo=zone).timestamp())
        client = Mock()
        client.request.return_value = {
            "timestamp": [stamp, int(boundary.timestamp())],
            "open": [10, 20], "high": [12, 22], "low": [9, 19],
            "close": [11, 21], "volume": [5, 6],
        }
        rows = fetch_dhan_history(client, "12M", now=now, before=int(boundary.timestamp()))
        self.assertEqual(rows, {"rows": [[stamp, 10, 12, 9, 11, 5]], "prefix": None})
        method, path, payload = client.request.call_args.args
        self.assertEqual((method, path), ("POST", "/charts/historical"))
        self.assertEqual(payload["toDate"], "2019-01-01")
        self.assertEqual(payload["securityId"], "13")
        with self.assertRaisesRegex(ValueError, "calendar candle boundary"):
            fetch_dhan_history(client, "12M", now=now, before=int(boundary.timestamp()) + 86400)

    def test_dhan_older_intraday_history_uses_selected_instrument_and_excludes_cursor(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from sector_heatmap.chart_workspace import fetch_dhan_history

        zone = ZoneInfo("Asia/Kolkata")
        now = datetime(2026, 11, 16, tzinfo=zone)
        boundary = datetime(2023, 11, 16, 10, 15, tzinfo=zone)
        end = int(boundary.timestamp())
        timestamps = list(range(end - 3600, end + 1, 900))
        client = Mock()
        client.request.return_value = {
            "timestamp": timestamps, "open": [10] * 5, "high": [12] * 5,
            "low": [9] * 5, "close": [11] * 5, "volume": [5] * 5,
        }
        rows = fetch_dhan_history(client, "60", now=now, before=end, security_id="1333",
                                  exchange_segment="NSE_EQ", instrument="EQUITY")
        self.assertEqual(rows, [[end - 3600, 10, 12, 9, 11, 20]])
        method, path, payload = client.request.call_args.args
        self.assertEqual((method, path), ("POST", "/charts/intraday"))
        self.assertEqual(payload["toDate"], "2023-11-16 10:15:00")
        self.assertEqual(payload["securityId"], "1333")
        client.reset_mock()
        expired = int(datetime(2021, 11, 16, tzinfo=zone).timestamp())
        self.assertEqual(fetch_dhan_history(client, "60", now=now, before=expired), [])
        client.request.assert_not_called()

    def test_delta_symbol_routes_to_selected_history_and_live_adapters(self):
        guard = SimpleNamespace(store=SimpleNamespace(
            sidebar_visibility=lambda: {"chart-workspace": True},
        ))
        identity = ({"features": ["chart-workspace"]}, {"broker": "DELTA_INDIA"})
        for interval in ("1", "5S", "100T"):
            symbols = ("ETHUSD", "BTCUSD", "INVALID!", "")
            if interval == "1":
                symbols += ("SOLUSD", "C-BTC-100000-251226")
            for symbol in symbols:
                with self.subTest(interval=interval, symbol=symbol):
                    handler = SimpleNamespace(workspace_identity=identity, send_json=Mock())
                    other = Mock(side_effect=AssertionError("Unexpected broker adapter"))
                    history = Mock(return_value=[])
                    live = Mock(return_value={"provider": "Delta India", "symbol": symbol, "rows": []})
                    handler.path = f"/api/chart-workspace/history?interval={interval}&symbol={symbol}"
                    serve_history(handler, None, guard, other, history, other)
                    code, payload = handler.send_json.call_args.args
                    valid = symbol not in ("INVALID!", "")
                    self.assertEqual(code, 200 if valid else 400)
                    if valid and interval == "1":
                        history.assert_called_once_with(interval, None, symbol=symbol)
                    else:
                        history.assert_not_called()
                    if valid:
                        self.assertEqual(payload["symbol"], symbol)

                    handler.send_json.reset_mock()
                    handler.path = f"/api/chart-workspace/live?interval={interval}&symbol={symbol}"
                    serve_live(handler, None, guard, None, None, live, other)
                    code, payload = handler.send_json.call_args.args
                    self.assertEqual(code, 200 if valid else 400)
                    if valid:
                        live.assert_called_once_with(1 if interval == "1" else interval, symbol=symbol)
                        self.assertEqual(payload["symbol"], symbol)
                    else:
                        live.assert_not_called()
                    other.assert_not_called()

    def test_dhan_selected_symbol_routes_to_both_adapters(self):
        guard = SimpleNamespace(store=SimpleNamespace(
            sidebar_visibility=lambda: {"chart-workspace": True},
        ))
        identity = ({"features": ["chart-workspace"]}, {"broker": "DHAN"})
        for symbol, expected in (("NSE_EQ:1333", 200), ("MCX_COMM:1", 200), ("NSE_CURRENCY:42", 200), ("MCX_COMM:bad", 400), ("NSE_EQ:1333&symbol=IDX_I:13", 400)):
            with self.subTest(symbol=symbol):
                handler = SimpleNamespace(workspace_identity=identity, send_json=Mock())
                other = Mock(side_effect=AssertionError("Unexpected broker adapter"))
                history = Mock(return_value=[])
                live = Mock(return_value={"provider": "Dhan", "symbol": symbol, "rows": []})
                handler.path = f"/api/chart-workspace/history?interval=5&symbol={symbol}"
                serve_history(handler, None, guard, other, other, history)
                self.assertEqual(handler.send_json.call_args.args[0], expected)
                handler.send_json.reset_mock()
                handler.path = f"/api/chart-workspace/live?interval=5&symbol={symbol}"
                serve_live(handler, None, guard, None, None, other, live)
                self.assertEqual(handler.send_json.call_args.args[0], expected)
                if expected == 200:
                    history.assert_called_once_with("5", None, symbol=symbol)
                    live.assert_called_once_with(5, symbol=symbol)
                else:
                    history.assert_not_called()
                    live.assert_not_called()
                other.assert_not_called()

    def test_fyers_history_requests_the_selected_native_symbol(self):
        zone = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 11, 13, 10, 0, tzinfo=zone)
        start = int(now.replace(hour=9, minute=15).timestamp())
        candle = [start, 100, 110, 95, 105, 300]
        client = object()
        guard = SimpleNamespace(store=SimpleNamespace(
            sidebar_visibility=lambda: {"chart-workspace": True},
        ))
        other = Mock(side_effect=AssertionError("Unexpected broker adapter"))
        for symbol in ("NSE:RELIANCE-EQ", "BSE:SENSEX-INDEX", "BSE:RELIANCE-A", "BSE:BFL211026`-F", None):
            with self.subTest(symbol=symbol):
                query = "&" + urlencode({"symbol": symbol}) if symbol else ""
                handler = SimpleNamespace(
                    path=f"/api/chart-workspace/history?interval=1{query}",
                    workspace_identity=({"features": ["chart-workspace"]}, {"broker": "FYERS"}),
                    send_json=Mock(),
                )
                with patch("sector_heatmap.fyers_history.history", return_value={
                    "s": "ok", "candles": [candle],
                }) as provider:
                    serve_history(handler, None, guard, lambda interval, after, **options:
                                  fetch_fyers_history(client, interval, now=now, after=after, **options),
                                  other, other)
                expected = symbol or "NSE:NIFTY50-INDEX"
                self.assertTrue(provider.call_args_list)
                for request in provider.call_args_list:
                    self.assertIs(request.args[0], client)
                    self.assertEqual(request.args[1]["symbol"], expected)
                code, payload = handler.send_json.call_args.args
                self.assertEqual(code, 200)
                self.assertEqual(payload["symbol"], expected)
                self.assertEqual(payload["rows"], [candle])
        other.assert_not_called()

    def test_fyers_intraday_history_pages_before_the_selected_bucket(self):
        zone = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 11, 16, 16, tzinfo=zone)
        present = now.replace(hour=9, minute=15)
        prior = present - timedelta(days=3)
        boundary = int(present.timestamp())
        candles = [[int(prior.timestamp()) + index * 1800, 100, 110, 95, 105, 100]
                   for index in range(13)]
        guard = SimpleNamespace(store=SimpleNamespace(
            sidebar_visibility=lambda: {"chart-workspace": True},
        ))
        unexpected = Mock(side_effect=AssertionError("Unexpected broker adapter"))
        for interval in ("360", "840", "1320", "1380"):
            with self.subTest(interval=interval):
                handler = SimpleNamespace(
                    path=f"/api/chart-workspace/history?interval={interval}&before={boundary}&symbol=NSE%3ARELIANCE-EQ",
                    workspace_identity=({"features": ["chart-workspace"]}, {"broker": "FYERS"}),
                    send_json=Mock(),
                )
                def history_page(client, request):
                    self.assertEqual(request["resolution"], "30")
                    self.assertLess(request["range_to"], present.date().isoformat())
                    if request["range_from"] <= prior.date().isoformat() <= request["range_to"]:
                        return {"s": "ok", "candles": candles}
                    return {"s": "no_data"}
                with patch("sector_heatmap.fyers_history.history", side_effect=history_page):
                    serve_history(handler, None, guard, lambda value, after, **options:
                                  fetch_fyers_history(object(), value, now=now, after=after, include_forming=True, **options),
                                  unexpected, unexpected)
                code, payload = handler.send_json.call_args.args
                self.assertEqual(code, 200)
                first = [int(prior.timestamp()), 100, 110, 95, 105, 1200 if interval == "360" else 1300]
                expected = [first, [first[0] + 21600, 100, 110, 95, 105, 100]] if interval == "360" else [first]
                self.assertEqual(payload["rows"], expected)
                self.assertTrue(payload["older_history"])
                self.assertNotIn("fyers_forming_seed", payload)

    def test_fyers_empty_intraday_page_exhausts_history(self):
        now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
        boundary = int(now.replace(hour=3, minute=45).timestamp())
        handler = SimpleNamespace(
            path=f"/api/chart-workspace/history?interval=1380&before={boundary}&symbol=NSE%3ARELIANCE-EQ",
            workspace_identity=({"features": ["chart-workspace"]}, {"broker": "FYERS"}),
            send_json=Mock(),
        )
        guard = SimpleNamespace(store=SimpleNamespace(
            sidebar_visibility=lambda: {"chart-workspace": True},
        ))
        unexpected = Mock(side_effect=AssertionError("Unexpected broker adapter"))
        with patch("sector_heatmap.fyers_history.history", return_value={"s": "no_data"}):
            serve_history(handler, None, guard, lambda value, after, **options:
                          fetch_fyers_history(object(), value, now=now, after=after, include_forming=True, **options),
                          unexpected, unexpected)
        code, payload = handler.send_json.call_args.args
        self.assertEqual(code, 200)
        self.assertEqual(payload["rows"], [])
        self.assertFalse(payload["older_history"])

    def test_fyers_calendar_history_pages_before_the_selected_period(self):
        zone = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 11, 16, 16, tzinfo=zone)
        client = object()
        guard = SimpleNamespace(store=SimpleNamespace(
            sidebar_visibility=lambda: {"chart-workspace": True},
        ))
        unexpected = Mock(side_effect=AssertionError("Unexpected broker adapter"))
        listing = datetime(2017, 1, 1).date()
        def daily_history(actual_client, request):
            self.assertIs(actual_client, client)
            self.assertEqual(request["symbol"], "NSE:NIFTY50-INDEX")
            self.assertEqual(request["resolution"], "D")
            start = datetime.fromisoformat(request["range_from"]).date()
            end = datetime.fromisoformat(request["range_to"]).date()
            days = (end - start).days + 1
            self.assertLessEqual(days, 365)
            rows = []
            for offset in range(days):
                day = start + timedelta(days=offset)
                if day >= listing and day.weekday() < 5:
                    time = int(datetime(day.year, day.month, day.day, tzinfo=zone).timestamp())
                    rows.append([time, 100, 110, 95, 105, 300])
            return {"s": "ok", "candles": rows} if rows else {"s": "no_data"}
        for interval in ("1W", "1M", "12M"):
            with self.subTest(interval=interval), patch("sector_heatmap.fyers_history.history", side_effect=daily_history):
                def page(before=None):
                    query = "&" + urlencode({"before": before}) if before is not None else ""
                    handler = SimpleNamespace(
                        path=f"/api/chart-workspace/history?interval={interval}{query}",
                        workspace_identity=({"features": ["chart-workspace"]}, {"broker": "FYERS"}),
                        send_json=Mock(),
                    )
                    serve_history(handler, None, guard, lambda period, after, **options:
                                  fetch_fyers_history(client, period, now=now, after=after, **options),
                                  unexpected, unexpected)
                    code, payload = handler.send_json.call_args.args
                    self.assertEqual(code, 200)
                    return payload
                first = page()
                self.assertTrue(first["older_history"])
                before = first["rows"][0][0]
                older = page(before)
                self.assertTrue(older["rows"])
                self.assertTrue(all(row[0] < before for row in older["rows"]))
                self.assertIsNone(older["prefix"])
                exhausted = page(int(datetime(2017, 1, 1, tzinfo=zone).timestamp()))
                self.assertEqual(exhausted["rows"], [])
                self.assertFalse(exhausted["older_history"])

    def test_fyers_live_routes_native_cash_symbols_to_selected_feed(self):
        guard = SimpleNamespace(store=SimpleNamespace(
            sidebar_visibility=lambda: {"chart-workspace": True},
        ))
        symbol = "BSE:RELIANCE-A"
        handler = SimpleNamespace(
            path="/api/chart-workspace/live?" + urlencode({"symbol": symbol, "interval": "5"}),
            workspace_identity=({"features": ["chart-workspace"]}, {"broker": "FYERS"}),
            send_json=Mock(),
        )
        feed = Mock(connected=True, token_expired=False)
        selected_bars = feed.chart_bars_for.return_value
        selected_bars.snapshot.return_value = {"rows": []}
        default_bars = Mock()
        other_broker = Mock(side_effect=AssertionError("Unexpected broker adapter"))

        serve_live(handler, None, guard, default_bars, feed, other_broker, other_broker)

        feed.chart_bars_for.assert_called_once_with(symbol)
        selected_bars.snapshot.assert_called_once_with(5, True)
        default_bars.snapshot.assert_not_called()
        handler.send_json.assert_called_once_with(200, {"rows": []})

    def test_dhan_mcx_catalog_excludes_nse_commodity_rows(self):
        now = datetime(2026, 11, 13, tzinfo=timezone.utc)
        master = Mock()
        master.load.return_value = [
            {"SEM_EXM_EXCH_ID": exchange, "SEM_SEGMENT": "M",
             "SEM_SMST_SECURITY_ID": security_id, "SEM_TRADING_SYMBOL": "GOLD",
             "SEM_INSTRUMENT_NAME": "OPTFUT", "SEM_EXPIRY_DATE": "2026-12-01"}
            for exchange, security_id in [("NSE", "12"), ("MCX", "34")]
        ]
        result = search_dhan_chart_symbols(master, "GOLD", now, segment_filter="MCX_COMM")
        self.assertEqual([row["id"] for row in result["symbols"]], ["MCX_COMM:34"])

    def test_dhan_derivative_search_requires_current_expiry(self):
        now = datetime(2026, 11, 13, tzinfo=timezone.utc)
        master = Mock()
        master.load.return_value = [
            {"SEM_EXM_EXCH_ID": "NSE", "SEM_SEGMENT": "D",
             "SEM_SMST_SECURITY_ID": security_id, "SEM_TRADING_SYMBOL": "NIFTY",
             "SEM_INSTRUMENT_NAME": "FUTIDX", "SEM_EXPIRY_DATE": expiry}
            for security_id, expiry in [("1", ""), ("2", "2026-11-12"), ("3", "2026-11-13")]
        ]
        result = search_dhan_chart_symbols(master, "NIFTY", now, segment_filter="NSE_FNO")
        self.assertEqual([row["id"] for row in result["symbols"]], ["NSE_FNO:3"])

    def test_mcx_aggregation_requires_opening_and_contiguous_native_bars(self):
        zone = timezone(timedelta(hours=5, minutes=30))
        opening = int(datetime(2026, 11, 13, 9, tzinfo=zone).timestamp())
        now = opening + 86400
        rows = [[opening + 1800 * i, 100 + i, 104 + i, 98 + i, 101 + i, 10]
                for i in range(12)]
        self.assertEqual(mcx_history_bars(rows, 360, 30, now, None),
                         [[opening, 100, 115, 98, 112, 120]])
        self.assertEqual(mcx_history_bars(rows[1:], 360, 30, now, None), [])
        self.assertEqual(mcx_history_bars(rows[:5] + rows[6:], 360, 30, now, None), [])

    def test_yahoo_custom_hours_reject_incomplete_buckets(self):
        from sector_heatmap.yahoo_chart import history

        stamps = [3600 * index for index in range(18) if index != 8]
        quote = {key: [value] * len(stamps) for key, value in (
            ("open", 10), ("high", 12), ("low", 9), ("close", 11), ("volume", 2),
        )}
        result = {"timestamp": stamps, "indicators": {"quote": [quote]},
                  "meta": {"instrumentType": "CRYPTOCURRENCY"}}
        response = Mock(status_code=200)
        response.json.return_value = {"chart": {"result": [result]}}
        with patch("sector_heatmap.yahoo_chart.requests.get", return_value=response) as request:
            self.assertEqual(history("BTC-USD", "360", now=17 * 3600)["rows"],
                             [[0, 10, 12, 9, 11, 12]])
            self.assertEqual(request.call_args.kwargs["params"]["range"], "1y")
            self.assertEqual(request.call_args.kwargs["params"]["interval"], "60m")
            result["meta"]["instrumentType"] = "EQUITY"
            with self.assertRaisesRegex(ValueError, "regular-session boundaries"):
                history("BRK-B", "360", now=17 * 3600)

    def test_yahoo_long_hours_end_at_regular_session_close(self):
        from sector_heatmap.yahoo_chart import history

        start = 9 * 3600 + 30 * 60
        end = 16 * 3600
        stamps = [start + index * 3600 for index in range(7)]
        quote = {key: [value] * len(stamps) for key, value in (
            ("open", 10), ("high", 12), ("low", 9), ("close", 11), ("volume", 2),
        )}
        result = {"timestamp": stamps, "indicators": {"quote": [quote]},
                  "meta": {"instrumentType": "EQUITY", "tradingPeriods": [[{"start": start, "end": end}]]}}
        response = Mock(status_code=200)
        response.json.return_value = {"chart": {"result": [result]}}
        with patch("sector_heatmap.yahoo_chart.requests.get", return_value=response):
            expected = history("AAPL", "840", now=end)
            self.assertEqual(expected["rows"], [[start, 10, 12, 9, 11, 14]])
            self.assertEqual(expected["close_times"], {start: end})
            self.assertEqual(history("AAPL", "840", now=end - 1)["rows"], [])
            self.assertEqual(history("AAPL", "360", now=end)["close_times"], {start + 6 * 3600: end})

    def test_yahoo_calendar_older_page_excludes_boundary_and_retains_close_times(self):
        from datetime import datetime, timezone
        from sector_heatmap.yahoo_chart import history

        def stamp(month):
            return int(datetime(2020, month, 1, tzinfo=timezone.utc).timestamp())

        quote = {key: [value, value] for key, value in (
            ("open", 10), ("high", 12), ("low", 9), ("close", 11), ("volume", 2),
        )}
        response = Mock(status_code=200)
        response.json.return_value = {"chart": {"result": [{
            "timestamp": [stamp(1), stamp(2)], "indicators": {"quote": [quote]},
            "meta": {"instrumentType": "CRYPTOCURRENCY", "exchangeTimezoneName": "UTC"},
        }]}}
        with patch("sector_heatmap.yahoo_chart.requests.get", return_value=response) as request:
            page = history("BTC-USD", "1M", now=stamp(3), before=stamp(2))
            self.assertEqual(page["rows"], [[stamp(1), 10, 12, 9, 11, 2]])
            self.assertEqual(page["close_times"], {stamp(1): stamp(2)})
            self.assertTrue(page["older_history"])
            params = request.call_args.kwargs["params"]
            self.assertEqual(params["period2"], stamp(2))
            self.assertNotIn("range", params)

            response.status_code = 400
            response.json.return_value = {"chart": {"error": {
                "description": "Data doesn't exist for startDate = 0, endDate = 42",
            }}}
            self.assertFalse(history("BTC-USD", "1M", now=stamp(3), before=stamp(2))["older_history"])
