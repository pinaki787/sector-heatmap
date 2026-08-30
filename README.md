# NSE Sector Heat Map

For a first-time setup, run the native setup-and-launch entry point from the
project root. It creates `.venv`, installs the fully resolved Python dependency
set from `requirements.lock`, installs the UI packages from `pnpm-lock.yaml` with
pnpm 10.17.1, builds the UI, and starts the dashboard.

| Platform | First setup and launch |
| --- | --- |
| Windows | `setup_and_run.bat` |
| macOS / Linux | `sh setup_and_run.sh` |

Python 3.9+ and Node.js 20.19+ (including `npx`) must already be installed. The
scripts are idempotent: rerunning them reuses `.venv` and the locked dependency
sets. They do not read credentials aloud, place orders, or make any broker trade.
They stop immediately if dependency installation or the UI build fails.
For CI or setup validation without starting the long-running server, set
`HEATMAP_SETUP_ONLY=1` before invoking either script.

For later launches that do not need dependency or UI build validation, use the
lighter launchers:

| Platform | Fast launch |
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

All launchers resolve their own directory, so paths containing spaces are
supported. The POSIX scripts use `/bin/sh` syntax and LF line endings; the Windows
scripts use `cmd.exe` syntax and CRLF checkouts. The dashboard's **Refresh
authentication** control does not invoke a shell or batch file.

`requirements.txt` records the maintainable top-level compatibility ranges.
`requirements.lock` is the setup/release input and pins the complete resolved
Python environment. `client/pnpm-lock.yaml` and the `packageManager` field pin the
UI dependency graph and pnpm release. Update these lock inputs deliberately and
rerun the validations before publishing a release.

### Operating-system and broker boundaries

- The HTTP server binds only to `127.0.0.1`; setup does not expose the dashboard
  to the local network or start any trading action.
- OAuth uses the operating system's default browser and a loopback callback. The
  UI opens login from the user's click and falls back to same-tab navigation when
  a browser blocks the popup. Login, 2FA, callback registration, FYERS service
  availability, and broker/API entitlements remain broker-controlled.
- Token replacement is atomic on Windows, Linux, and macOS. POSIX systems also
  receive mode `0600`; on Windows, private access depends on the user's existing
  NTFS account and directory ACLs because POSIX modes are not authoritative.
- `setup_and_run.bat` targets native `cmd.exe`. `setup_and_run.sh` targets a POSIX
  `/bin/sh` as provided by Linux and macOS. Neither requires PowerShell, Bash,
  WSL, platform-specific browser automation, or a global pnpm installation.

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

### TLS certificate trust

The WebSocket always verifies the FYERS certificate and hostname. It uses an
explicit `WEBSOCKET_CLIENT_CA_BUNDLE` when provided, then a populated Python/system
trust store, and finally the Mozilla CA bundle supplied by `certifi`. This fallback
is needed by some Python.org macOS installations whose OpenSSL trust store is empty;
it is also portable to Windows and Linux. An invalid explicit bundle or an empty
trust store is reported as an error. Certificate verification is never disabled.

When Fyers reports an expired or invalid token, the dashboard detects the authentication error and invokes the same renewal module automatically. Fyers still requires browser login/2FA; once finished, the dashboard replaces itself and reconnects using the fresh token.

## Modules

- `sector_heatmap/config.py` — local configuration and token persistence
- `sector_heatmap/authentication.py` — browser OAuth, local callback, and token exchange
- `sector_heatmap/sectors.py` — sector definitions and Fyers index symbols
- `sector_heatmap/market_data.py` — Fyers WebSocket subscription and live snapshot aggregation
- `sector_heatmap/web.py` — local HTTP API and dashboard server
