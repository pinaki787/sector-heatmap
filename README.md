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

For a transferred archive, extract it into an ordinary writable directory. Copy
`.fyers.env.example` to `.fyers.env` and enter the destination terminal's FYERS
application settings, or use one of the user-level configuration locations below.
Copy `.env.example` to `.env` only when runtime switches are needed. Both setup
scripts and both fast launchers read the same two live-order switches; they default
to `0` on a fresh terminal and reject values other than `0` or `1`. Never copy an
access token or another terminal's private `.env` into a transfer archive.

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

## User functional guide

Open the [Renko Support and Strategy user guide](docs/user-functional-guide.md) or its [browser version](docs/user-functional-guide.html) for existing FYERS position management and candlestick volume controls.

## Modules

- `sector_heatmap/config.py` — local configuration and token persistence
- `sector_heatmap/authentication.py` — browser OAuth, local callback, and token exchange
- `sector_heatmap/official_weights.py` — validated loading and provenance for versioned official NSE Indices weights
- `sector_heatmap/data/nse_weights/` — immutable source-as-of snapshots transcribed from official factsheets and constituent files
- `sector_heatmap/sectors.py` — configurable sector, benchmark, and FYERS index symbols joined to official constituents
- `sector_heatmap/market_data.py` — Fyers WebSocket subscription and live snapshot aggregation
- `sector_heatmap/indicators.py` — dependency-free EMA, ATR, RSI, ADX/DMI, breadth, and volume calculations
- `sector_heatmap/analysis.py` — explainable timeframe, RS, momentum, score, ranking, alignment, rotation, and event domain logic
- `sector_heatmap/sector_service.py` — completed-candle cache, FYERS history adapter, bounded snapshot history, and refresh service
- `sector_heatmap/handoff.py` — local analysis-packet construction, risk sizing, and fresh FYERS option-chain proposals
- `sector_heatmap/fyers_execution.py` — FYERS-only, confirmation-gated limit-order preview and reconciliation
- `sector_heatmap/automation.py` — disabled-by-default unattended-policy authoring, fail-closed evaluation, and hash-chained audit log
- `sector_heatmap/web.py` — local HTTP API and dashboard server

## Multi-timeframe sector analysis

The Sector Rotation view analyzes the configured FYERS sector indices on 15m,
1H, Daily, and Weekly completed candles against `NSE:NIFTY50-INDEX`. It supports
Intraday and Swing weighting, explainable trend and relative-strength states,
ranking and rank change, persisted rotation history, multi-timeframe alignment,
filters, sorting, and a sector detail workflow. It is an analytical prioritization
system, not an automatic signal or order-entry feature.

## Analysis handoff and gated FYERS tickets

The **Analysis handoff** view scans completed 15m, 1H, Daily, and Weekly bars for
exact fully bullish or fully bearish sectors and direction-matching contributor
stocks. It builds a local packet for ChatGPT or Codex only after the user selects
the recipient and chooses preview or export. Nothing is transmitted by the
dashboard. Available FYERS funds are omitted unless the user enables them and
separately confirms their inclusion.

Sizing requires a positive stop or invalidation for every selected idea. The
default planning values are ₹100,000 capital, a hard ₹5,000 daily loss limit,
₹2,000 maximum new-idea risk, and a protected ₹1,000 reserve. The server rejects
a daily limit above ₹5,000 and option proposals below 1:1 reward-to-risk.

Order previews are FYERS-only. Preparing a ticket refreshes the token/profile,
nearest expiry and option chain, exact daily symbol-master contracts, bid/ask,
lot and tick size, funds, positions, and order state. It produces DAY limit
orders and an exact, short-lived confirmation phrase. Live submission remains
disabled unless the account holder starts the server with
`SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=1`; setting that flag alone never places an
order. Submission still requires the current typed phrase and a second complete
preflight. State changes produce a replacement preview instead of an order, and
submitted baskets are reconciled without automatic retries. Credit spreads stay
preview-only because the installed FYERS SDK does not expose an exact basket/SPAN
margin check; eligible debit spreads reserve the full protective-leg premium and
send the BUY protection leg first. No alternative broker route is supported in
this dashboard.

The optional unattended policy is a separate approval mode, not a relaxation of
the per-order confirmation flow. It defaults to PAPER and disabled, requires a
full human-readable preview plus an exact acknowledgement before saving, and
  captures symbol/segment/strategy allowlists, completed-candle conditions, risk
and concurrency limits, limit-price protections, trading hours, DTE/liquidity
filters, stops/targets, cooldown, stale-data veto, kill switch, and mandatory
halt-on-uncertain behavior. Profiles are stored privately with a tamper-evident
hash-chained audit log. This release provides policy authoring and fail-closed
evaluation only; it does not include an automatic signal scheduler. An enabled
LIVE profile additionally requires
`SECTOR_PULSE_ENABLE_FYERS_UNATTENDED=1`, and no order can bypass fresh FYERS
preflight or uncertainty halts.

A disabled PAPER draft may cover both fully aligned NSE cash equities and
supported index or stock options. It never pre-authorizes an option contract:
active expiry, exact FYERS chain/master identity, two-sided bid/ask and configured
spread, OI/volume, complete Greeks, valid lot/tick, defined maximum loss, stop or
invalidation, target, and the configured minimum reward:risk must all pass again
on fresh data before a future policy evaluation can allow it.

## Broker invariant

Sector Heatmap is strictly FYERS-only. Market data, completed-candle analysis,
option chains, account reads, ticket previews, confirmation-gated execution, and
future unattended policy evaluation must all use fresh FYERS evidence. New work
must not add a second broker, broker-selection abstraction, fallback quote feed,
or cross-broker execution route. See `BROKER_POLICY.md` for the enforced project
boundary.

The primary endpoints are:

- `GET /api/sector-analysis?mode=intraday|swing`
- `GET /api/sector-analysis/detail?mode=intraday|swing&sector=<sector-id>`
- `GET /api/analysis-handoff/candidates?mode=intraday|swing`
- `POST /api/analysis-handoff/preview`
- `POST /api/analysis-handoff/analyze` — refreshes full-alignment candidates and renders local evidence proposals; it explicitly reports ChatGPT/Codex as unavailable unless a real recipient connection exists
- `POST /api/analysis-handoff/size` — accepts or edits one structure, percent, ATR, or custom invalidation and recomputes stop, target and size from a fresh FYERS quote/tick
- `GET /api/trade-ticket/capabilities`
- `POST /api/trade-ticket/prepare` and `POST /api/trade-ticket/submit`
- `GET /api/automation/profile`, `POST /api/automation/profile/preview`, and
  `POST /api/automation/profile/draft` or `POST /api/automation/profile/save`

See [the implementation design](docs/sector-analysis-design.md) for formulas,
caching, refresh behavior, and current provider limitations.

## Official-weight contributor attribution

The checked-in weight snapshot is sourced from NSE Indices Limited monthly
factsheets and official constituent files. The dashboard shows the source date,
coverage scope, and a factsheet link. It never renormalizes the published
weights. A stock's displayed percentage-point contribution is:

`official weight (%) × unrounded live stock change (%) ÷ 100`

FYERS prices are presentation-rounded only after this calculation. Raw provider
tick timestamps are retained alongside normalized ISO timestamps, and snapshot
time is kept separate from provider time. Attribution remains read-only and does
not expose credentials or create, modify, or place orders.

Public NSE factsheets publish only the ten largest weights. Consequently, a
ten-constituent index can be labelled `OFFICIAL_COMPLETE`; a larger index is
labelled `OFFICIAL_PARTIAL` with both published constituent count and covered
weight. Missing live ticks stay unavailable rather than being estimated. See
[the source and refresh guide](docs/official-weight-attribution.md) for the exact
coverage boundary and monthly update procedure.

### Trade Parser: OpenAI advisory feedback

Submitting a parser ticket dispatches the existing FYERS request first. A separate
background request gathers completed FYERS evidence and requests OpenAI analysis.
There is no AI checkbox, no analysis on Parse, and no AI verdict, error, timeout or
connection check in the broker submission path. Existing broker validations still
apply. Green **PASS** and red **FAIL** are advisory assessments of the intraday and
1–5-trading-day swing plans; **UNAVAILABLE** and **SKIPPED** are neutral, not failures
of the trade. Plans and stops in the feedback never modify broker orders.

The server reads `OPENAI_API_KEY` and optional `OPENAI_MODEL` from the environment
or ignored `.env.local`; the default model is `gpt-4.1-mini`. Never put the key in
browser code. The OpenAI request uses `store: false` and contains only the extracted
price plan, contract and market evidence, not broker credentials, funds, positions,
account identity or the original pasted message. OpenAI API usage may incur charges.
The new static-file handler denies hidden files, including `.env.local`.

Analysis includes completed 5-minute, hourly and daily candles (today's daily bar is
excluded), structure, conditional levels, stops, reward/risk, volume, a session VWAP
proxy when complete opening data exists, and sector comparison where official
constituent mapping is unambiguous. Conflicting candles are rejected. Missing or
stale essential instrument/underlying candles suppress that horizon's verdict.
Volume-at-price data is unavailable and is not represented as a volume profile.
Some newly listed options lack sufficient daily history for a swing assessment.

After Python changes, a controlled server restart is required; refreshing the page
alone updates only JavaScript. Preserve the launch environment and reconcile active
runners before restarting. No live order is needed to test the AI integration:

- `python3 -m unittest discover -s tests -p test_trade_advisory.py`
- `node --test tests/trade_parser_advisory.test.cjs`
- `.venv/bin/python scripts/preview_trade_advisory.py` serves a GET-only UI fixture on port 8097.
- `.venv/bin/python scripts/check_trade_advisory.py` explicitly performs read-only
  FYERS parsing/history and an OpenAI request against a sample DMART plan; it never submits an order.

API format: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Release portability (7 October 2026)

All four launchers read explicit FYERS, KAMA and trade-parser live switches from
`.env` or the caller environment, validate 0/1, and default to 0. Private credential
imports do not authorize starting strategies. Inspect copied `.env` switches before
launching on another host. Setup-only builds never start the dashboard.

`HEATMAP_SETUP_ONLY=1 sh setup_and_run.sh` installs the pinned Python runtime,
builds the UI and runs `scripts/check_setup.py`. Windows uses the equivalent
`set HEATMAP_SETUP_ONLY=1` followed by `setup_and_run.bat`. macOS setup builds the
read-only Swift WhatsApp helper when `swiftc` is available. Grant Accessibility and
Screen Recording permissions manually. Native WhatsApp polling is unavailable on
Windows/Linux; manual parsing and Telegram polling do not require that helper.

Journal XLSX exports now use the project-installed Python runtime and openpyxl,
with recorded trades/orders and a lossless chunked raw snapshot; no Codex runtime
is required. Exports are static evidence, not proof of order fills or profitability.
Nested JSON remains evidence rather than computed performance. Timezone data is
installed for Windows; cross-process ownership locks use the OS on each platform.

Offline research sources remain research-only. Install their separate optional
requirements with `HEATMAP_INSTALL_RESEARCH=1` during setup or
`.venv/bin/python -m pip install -r requirements-research.txt`. Research dependencies
are bounded but not fully pinned; they are not part of the production runtime lock.
Generated candles, results, journals and deployment snapshots are excluded from
source releases. Research code may require separately obtained market data.

A private credential overlay is for local transfer only. It must never be added to
Git or uploaded with a source archive. Keep directories private (0700), files and
archives 0600. Import only the selected configuration/key files; never import active
runner state, ownership locks or polling databases. FYERS access tokens expire and
may require browser login/2FA on the destination. Broker IP policies and native OS
permissions must be configured on that host. No launcher starts a saved strategy
as part of installation validation.
