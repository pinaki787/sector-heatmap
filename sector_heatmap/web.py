from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from urllib.parse import parse_qs, urlparse
import webbrowser
from .config import ROOT, load_config
from .authentication import authorization_url, exchange_auth_code
from .market_data import FyersLiveFeed

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
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
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
            if path == "/api/heatmap":
                body = json.dumps(snapshot()).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            super().do_GET()
        def log_message(self, *args): pass
    port = int(os.getenv("HEATMAP_PORT", "8080"))
    os.chdir(ROOT); print(f"Sector heat map: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
