from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from urllib.parse import parse_qs, urlparse
import webbrowser
from .config import ROOT, load_config
from .authentication import authorization_url, exchange_auth_code
from .market_data import FyersLiveFeed
from fyers_apiv3 import fyersModel

def run_server():
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    feed = FyersLiveFeed(token) if token else None
    if feed: feed.start()
    state = {"feed": feed, "renewing": False}
    def renew_when_needed():
        """Run the existing OAuth module only after a Fyers token failure."""
        import sys, time
        while True:
            time.sleep(1)
            active_feed = state["feed"]
            if not active_feed or not active_feed.token_expired or state["renewing"]:
                continue
            print("Fyers token expired; starting the authorization renewal flow.")
            try:
                state["renewing"] = True
                webbrowser.open(authorization_url())
                print("Complete Fyers login/2FA; the dashboard callback will finish renewal.")
            except Exception as error:
                print("Token renewal did not complete:", error)
                with active_feed.lock: active_feed.token_expired = False
                state["renewing"] = False
                continue
    if state["feed"]:
        from threading import Thread
        Thread(target=renew_when_needed, daemon=True, name="fyers-token-supervisor").start()
    def snapshot():
        if state["feed"]: return state["feed"].snapshot()
        return {"mode":"needs_token", "connected":False, "error":"Run renew_fyers_token.bat to authorize Fyers.", "updated_at":datetime.now().astimezone().isoformat(), "sectors":[]}
    def account_summary():
        token = load_config().get("FYERS_ACCESS_TOKEN", "")
        if not token or ":" not in token:
            return {"pnl": 0, "positions": [], "available_funds": None, "week_realized_pnl": None, "month_realized_pnl": None, "connected": False}
        app_id, access_token = token.split(":", 1)
        client = fyersModel.FyersModel(client_id=app_id, token=access_token)
        response = client.positions()
        positions = response.get("netPositions", [])
        funds = client.funds()
        available_funds = sum(float(limit.get("equityAmount", 0) or 0) + float(limit.get("commodityAmount", 0) or 0) for limit in funds.get("fund_limit", []))
        return {"pnl": round(sum(float(item.get("pl", 0) or 0) for item in positions), 2), "positions": positions, "available_funds": round(available_funds, 2), "week_realized_pnl": None, "month_realized_pnl": None, "connected": response.get("s") == "ok" and funds.get("s") == "ok"}
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
        records = [{"symbol": row.get("symbol_name", "—"), "segment": row.get("segment_name", "—"), "buy_qty": row.get("buy_qty", 0), "buy_rate": row.get("buy_rate", 0), "sell_qty": row.get("sell_qty", 0), "sell_rate": row.get("sell_rate", 0), "pnl": row.get("realized_pnl", 0)} for row in report.get("data", [])]
        return {"period": period, "from_date": start.isoformat(), "to_date": today.isoformat(), "records": records, "summary": report.get("summary_data", {}), "connected": report.get("s") == "ok"}
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/auth/start":
                try:
                    state["renewing"] = True
                    body = json.dumps({"url": authorization_url()}).encode()
                    self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                except Exception as error:
                    state["renewing"] = False
                    self.send_error(500, str(error))
                return
            if path == "/callback":
                code = (parse_qs(urlparse(self.path).query).get("auth_code") or [None])[0]
                if not code:
                    self.send_error(400, "Fyers did not return an authorization code"); return
                def finish_renewal():
                    try:
                        exchange_auth_code(code)
                        print("Token renewed; restarting the live heat-map feed.")
                        import sys
                        os.execv(sys.executable, [sys.executable, str(ROOT / "heatmap_server.py")])
                    except Exception as error:
                        print("Token renewal did not complete:", error); state["renewing"] = False
                from threading import Thread
                Thread(target=finish_renewal, daemon=True).start()
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(b"<h2>Fyers authorization received.</h2><p>The dashboard is reconnecting.</p>"); return
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
    port = int(os.getenv("HEATMAP_PORT", "8080"))
    os.chdir(ROOT); print(f"Sector heat map: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
