from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from urllib.parse import parse_qs, urlparse
import webbrowser
from .config import ROOT, load_config
from .authentication import authorization_url, exchange_auth_code
from .market_data import FyersLiveFeed, is_token_error
from fyers_apiv3 import fyersModel

def run_server():
    port = int(os.getenv("HEATMAP_PORT", "8080"))
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    feed = FyersLiveFeed(token) if token else None
    if feed: feed.start()
    state = {"feed": feed, "renewing": False, "auth_error": None, "next_auth_attempt": 0.0}

    def replace_feed(token):
        replacement = FyersLiveFeed(token)
        replacement.start()
        state["feed"] = replacement
        state["auth_error"] = None

    def mark_auth_failure(*responses):
        if not any(is_token_error(response) for response in responses):
            return
        state["auth_error"] = "Fyers authentication expired; browser reauthentication is required."
        active_feed = state["feed"]
        if active_feed:
            with active_feed.lock:
                active_feed.token_expired = True

    def renew_when_needed():
        """Reuse a newly cached token first, then start supported browser OAuth."""
        import time
        while True:
            time.sleep(1)
            active_feed = state["feed"]
            needs_auth = active_feed is None or active_feed.token_expired
            if not needs_auth or state["renewing"] or time.monotonic() < state["next_auth_attempt"]:
                continue
            latest_token = load_config().get("FYERS_ACCESS_TOKEN", "")
            if latest_token and (active_feed is None or latest_token != active_feed.access_token):
                print("New Fyers token found in the private cache; reconnecting the feed.")
                replace_feed(latest_token)
                continue
            print("Fyers token unavailable or expired; starting browser authorization.")
            try:
                state["renewing"] = True
                url = authorization_url(expected_port=port)
                if not webbrowser.open(url):
                    raise RuntimeError("Could not open the system browser; use Refresh authentication in the dashboard")
                state["auth_error"] = "Complete Fyers login and 2FA in the browser."
                print("Complete Fyers login/2FA; the dashboard callback will finish renewal.")
            except Exception as error:
                print("Token renewal did not complete:", error)
                state["auth_error"] = str(error)
                state["next_auth_attempt"] = time.monotonic() + 60
                state["renewing"] = False
                continue
    from threading import Thread
    Thread(target=renew_when_needed, daemon=True, name="fyers-token-supervisor").start()
    def snapshot():
        if state["feed"]:
            result = state["feed"].snapshot()
            if state["auth_error"]:
                result["error"] = state["auth_error"]
            return result
        return {"mode":"needs_token", "connected":False, "error":state["auth_error"] or "No reusable Fyers token was found. Reauthentication will start automatically.", "updated_at":datetime.now().astimezone().isoformat(), "sectors":[]}
    def account_summary():
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            return {"pnl": 0, "positions": [], "available_funds": None, "week_realized_pnl": None, "month_realized_pnl": None, "connected": False, "error": state["auth_error"] or "No reusable Fyers token was found."}
        app_id, access_token = token.split(":", 1)
        client = fyersModel.FyersModel(client_id=app_id, token=access_token)
        response = client.positions()
        positions = response.get("netPositions", [])
        funds = client.funds()
        mark_auth_failure(response, funds)
        available_funds = sum(float(limit.get("equityAmount", 0) or 0) + float(limit.get("commodityAmount", 0) or 0) for limit in funds.get("fund_limit", []))
        connected = response.get("s") == "ok" and funds.get("s") == "ok"
        return {"pnl": round(sum(float(item.get("pl", 0) or 0) for item in positions), 2), "positions": positions, "available_funds": round(available_funds, 2), "week_realized_pnl": None, "month_realized_pnl": None, "connected": connected, "error": None if connected else state["auth_error"]}
    def realized_pnl(period):
        today = datetime.now().date()
        if period == "daily": start = today
        elif period == "weekly": start = today - timedelta(days=today.weekday())
        elif period == "monthly": start = today.replace(day=1)
        else: start = today.replace(month=4, day=1) if today.month >= 4 else today.replace(year=today.year - 1, month=4, day=1)
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token: return {"period": period, "records": [], "summary": {"gross_pnl": 0, "charges": 0, "net_pnl": 0}, "connected": False}
        app_id, access_token = token.split(":", 1)
        report = fyersModel.FyersModel(client_id=app_id, token=access_token).realised_profit_history({"from_date": start.isoformat(), "to_date": today.isoformat()})
        mark_auth_failure(report)
        records = [{"symbol": row.get("symbol_name", "—"), "segment": row.get("segment_name", "—"), "buy_qty": row.get("buy_qty", 0), "buy_rate": row.get("buy_rate", 0), "sell_qty": row.get("sell_qty", 0), "sell_rate": row.get("sell_rate", 0), "pnl": row.get("realized_pnl", 0)} for row in report.get("data", [])]
        return {"period": period, "from_date": start.isoformat(), "to_date": today.isoformat(), "records": records, "summary": report.get("summary_data", {}), "connected": report.get("s") == "ok"}
    class Handler(SimpleHTTPRequestHandler):
        def send_json(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/auth/start":
                try:
                    url = authorization_url(expected_port=port)
                    state["renewing"] = True
                    state["auth_error"] = "Complete Fyers login and 2FA in the browser."
                    self.send_json(200, {"url": url})
                except Exception as error:
                    state["renewing"] = False
                    state["auth_error"] = str(error)
                    self.send_json(500, {"error": str(error)})
                return
            if path == "/callback":
                code = (parse_qs(urlparse(self.path).query).get("auth_code") or [None])[0]
                if not code:
                    self.send_error(400, "Fyers did not return an authorization code"); return
                try:
                    exchange_auth_code(code)
                except Exception as error:
                    state["renewing"] = False
                    self.send_error(502, str(error)); return
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(b'<meta http-equiv="refresh" content="2;url=/"><h2>Fyers authorization received.</h2><p>The dashboard is reconnecting.</p>')
                def restart_server():
                    import sys, time
                    time.sleep(0.25)
                    print("Token renewed; restarting the live heat-map feed.")
                    os.execv(sys.executable, [sys.executable, str(ROOT / "heatmap_server.py")])
                from threading import Thread
                Thread(target=restart_server, daemon=True, name="fyers-server-restart").start()
                return
            if path == "/api/realized-pnl":
                try:
                    period = (parse_qs(urlparse(self.path).query).get("period") or ["annual"])[0]
                    if period not in {"annual", "monthly", "weekly", "daily"}: period = "annual"
                    body = json.dumps(realized_pnl(period)).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception as error:
                    self.send_error(502, str(error))
                return
            if path == "/api/account":
                try:
                    body = json.dumps(account_summary()).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception as error:
                    self.send_error(502, str(error))
                return
            if path == "/api/heatmap":
                body = json.dumps(snapshot()).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            super().do_GET()
        def log_message(self, *args): pass
    os.chdir(ROOT); print(f"Sector heat map: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
