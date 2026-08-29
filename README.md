# NSE Sector Heat Map

Start the dashboard from the project root:

```powershell
.\activate_venv.bat
python .\heatmap_server.py
```

Open `http://127.0.0.1:8080` in a browser. This same local server also handles the Fyers OAuth callback at `/callback`.

### Cross-platform launch

| Platform | Renew token | Start dashboard |
| --- | --- | --- |
| Windows | `renew_fyers_token.bat` | `run_live_heatmap.bat` |
| macOS / Linux | `sh renew_fyers_token.sh` | `sh run_live_heatmap.sh` |

The shell launchers resolve their own directory and use `.venv` when it exists. On macOS/Linux, create that environment with `python3 -m venv .venv` and install `fyers-apiv3` once.

## Connect a live Fyers feed

1. Copy `.fyers.env.example` to `.fyers.env` and enter your Fyers app ID and secret key.
2. In your Fyers app settings, register the same `FYERS_REDIRECT_URI` shown in that file.
3. Run `python .\get_fyers_token.py`. It opens Fyers login, waits for the local redirect, exchanges the authorization code, and saves the access token securely in `.fyers.env`.
4. Restart `python .\heatmap_server.py`.

The token file is excluded from Git. The UI displays **Live Fyers feed** only after the WebSocket connects and index ticks arrive; it never substitutes demo prices.

When Fyers reports an expired or invalid token, the dashboard detects the authentication error and invokes the same renewal module automatically. Fyers still requires browser login/2FA; once finished, the dashboard replaces itself and reconnects using the fresh token.

## Modules

- `sector_heatmap/config.py` — local configuration and token persistence
- `sector_heatmap/authentication.py` — browser OAuth, local callback, and token exchange
- `sector_heatmap/sectors.py` — sector definitions and Fyers index symbols
- `sector_heatmap/market_data.py` — Fyers WebSocket subscription and live snapshot aggregation
- `sector_heatmap/web.py` — local HTTP API and dashboard server
