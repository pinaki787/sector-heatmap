"""Fyers OAuth browser flow and local callback capture."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import threading
import webbrowser
from fyers_apiv3 import fyersModel
from .config import load_config, save_access_token

def create_session(cfg):
    return fyersModel.SessionModel(client_id=cfg["FYERS_APP_ID"], secret_key=cfg["FYERS_SECRET_KEY"], redirect_uri=cfg["FYERS_REDIRECT_URI"], response_type="code", grant_type="authorization_code")

def authorization_url():
    cfg = load_config()
    return create_session(cfg).generate_authcode()

def exchange_auth_code(auth_code):
    cfg = load_config()
    session = create_session(cfg)
    session.set_token(auth_code)
    response = session.generate_token(); token = response.get("access_token")
    if not token: raise RuntimeError("Fyers token exchange failed")
    save_access_token(f"{cfg['FYERS_APP_ID']}:{token}")

def refresh_access_token():
    cfg = load_config()
    required = ("FYERS_APP_ID", "FYERS_SECRET_KEY", "FYERS_REDIRECT_URI")
    missing = [key for key in required if not cfg.get(key)]
    if missing: raise RuntimeError("Missing " + ", ".join(missing) + " in .fyers.env")
    redirect = urlparse(cfg["FYERS_REDIRECT_URI"])
    if redirect.hostname not in ("127.0.0.1", "localhost") or not redirect.port:
        raise RuntimeError("FYERS_REDIRECT_URI must be a registered local callback URL")
    received, done = {}, threading.Event()
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            received["code"] = (query.get("auth_code") or query.get("code") or [None])[0]
            received["error"] = (query.get("error") or [None])[0]
            done.set(); self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<h2>Fyers authorization received.</h2><p>You may close this tab.</p>")
        def log_message(self, *args): pass
    server = HTTPServer((redirect.hostname, redirect.port), Callback)
    session = create_session(cfg)
    print("Opening Fyers login. Complete login and 2FA in the browser.")
    webbrowser.open(session.generate_authcode())
    while not done.is_set(): server.handle_request()
    if received.get("error") or not received.get("code"): raise RuntimeError("Fyers authorization failed")
    exchange_auth_code(received["code"])
    print("Access token saved locally.")
