# NSE Sector Heat Map

Start the dashboard from the project root. The dashboard and its authentication
callback use only Python and the browser; no platform-specific shell command is
required by the refresh button.

| Platform | Start dashboard |
| --- | --- |
| Windows | `run_live_heatmap.bat` |
| macOS / Linux | `sh run_live_heatmap.sh` |
| Any platform with Python active | `python heatmap_server.py` |

Open `http://127.0.0.1:8080` in a browser. This same local server also handles the Fyers OAuth callback at `/callback`.

### Cross-platform launch

| Platform | Standalone renewal | Start dashboard |
| --- | --- | --- |
| Windows | `renew_fyers_token.bat` | `run_live_heatmap.bat` |
| macOS / Linux | `sh renew_fyers_token.sh` | `sh run_live_heatmap.sh` |

The launchers resolve their own directory and use `.venv` when it exists. They are
convenience wrappers only; the dashboard's **Refresh authentication** control does
not invoke them. On macOS/Linux, create the environment with
`python3 -m venv .venv`; on Windows use `py -3 -m venv .venv`. Install
`fyers-apiv3` once in that environment.

## Connect a live Fyers feed

1. Start the dashboard. It automatically reuses an existing private token from
   `~/.fyers/token.json` and discovers credentials from `FYERS_*` environment
   variables, `FYERS_CONFIG_FILE`, a platform user-config file, or the optional
   project-local `.fyers.env` (in that precedence order).
2. In your Fyers app settings, register the same `FYERS_REDIRECT_URI` used by the
   dashboard. With no override it is `http://127.0.0.1:8080/callback`.
3. Start the dashboard, open `http://127.0.0.1:8080`, and click **Refresh
   authentication**. It opens the Fyers OAuth page; complete login and 2FA there.
4. Fyers returns to `/callback`; the dashboard exchanges the one-time code, stores
   the access token in the private shared cache (and updates a project
   `.fyers.env` only when that file already exists), then restarts its feed.

If the browser blocks the new tab, the dashboard navigates the current tab to Fyers
instead. If setup is incomplete, the broker status displays the missing key or
redirect mismatch instead of failing silently. The redirect URI must use the same
port as `HEATMAP_PORT` (8080 by default) and must be registered exactly in the Fyers
developer console.

The standalone `renew_fyers_token.bat` and `renew_fyers_token.sh` helpers remain
available when the dashboard is stopped. They listen on the registered callback
port themselves, so do not run them while the dashboard is already using that port.

Token files written by the dashboard are updated atomically with private permissions
where the OS supports POSIX modes. The optional project token file is excluded from
Git. The UI displays **Live Fyers feed** only after the WebSocket connects and index
ticks arrive; it never substitutes demo prices.

### Automatic configuration discovery

The first available values are merged, with later sources taking precedence:

1. `~/.fyers/token.json` (shared app ID/access-token cache)
2. platform config: `%APPDATA%\sector-heatmap\fyers.env` on Windows,
   `$XDG_CONFIG_HOME/sector-heatmap/fyers.env` or
   `~/.config/sector-heatmap/fyers.env` on Linux, and
   `~/Library/Application Support/sector-heatmap/fyers.env` on macOS
3. project `.fyers.env`
4. `FYERS_*` environment variables

`FYERS_CONFIG_FILE` and `FYERS_TOKEN_FILE` may point to existing private files.
Aliases `FYERS_CLIENT_ID`/`FYERS_APP_ID` and
`FYERS_SECRET_ID`/`FYERS_SECRET_KEY` are accepted. No credential is entered in the
dashboard or sent to the browser.

An existing valid access token makes startup non-interactive. When FYERS requires a
new authorization, the token supervisor first re-reads all configured sources. If
another supported process has placed a different token in the shared cache, the
dashboard reconnects with it automatically. Otherwise it opens the supported OAuth
URL and reports the required action in the UI. FYERS login and 2FA still require the
account holder's interaction; the dashboard does not attempt to bypass that
broker-enforced security step. FYERS error codes `-8`, `-15`, `-16`, `-17`, HTTP
401, and equivalent token/authentication messages trigger this renewal path.

When Fyers reports an expired or invalid token, the dashboard detects the authentication error and invokes the same renewal module automatically. Fyers still requires browser login/2FA; once finished, the dashboard replaces itself and reconnects using the fresh token.

## Modules

- `sector_heatmap/config.py` — local configuration and token persistence
- `sector_heatmap/authentication.py` — browser OAuth, local callback, and token exchange
- `sector_heatmap/sectors.py` — sector definitions and Fyers index symbols
- `sector_heatmap/market_data.py` — Fyers WebSocket subscription and live snapshot aggregation
- `sector_heatmap/web.py` — local HTTP API and dashboard server
