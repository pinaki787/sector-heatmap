# External Delta dashboard auto-recovery

The enabled user systemd service runs outside the Delta dashboard and checks its existing account-owner lock and loopback port every10seconds. It never kills a live or hung dashboard. A missing process is relaunched from the existing isolated source only; no provisioning, credential or runner-state rewrites occur.

Recovery is read-only: Delta live-order and parser live-order environment gates are disabled for the recovered process. Saved configuration, orders and owned exposure are retained. Renko constructors keep runners unarmed after process restart. Existing intentionally disconnected accounts stay disconnected. Existing active dashboard processes and their permission gates are unchanged by enabling the supervisor.

Startup/backoff:10,20,40,80,160seconds; maximum5launch attempts per30minutes, then circuit stays open until earlier attempts age out. Another owner, occupied port, registered account changes, malformed control files and active maintenance prevent unsafe duplicate launches. WorkspaceGuard provides the final cross-process owner lock if browser Open races supervisor launch. An alive process with no listening port is reported as PROCESS_ALIVE_NOT_SERVING without terminating possible financial work.

Service:sector-pulse-delta-supervisor.service, enabled for the trading user, lingering enabled to survive logout. Restart=on-failure restarts the external supervisor itself. KillMode=process preserves any recovered dashboard if supervisor maintenance is needed. Current status/events/config are in the Delta account folder as external-supervisor-status.json, external-supervisor-events.jsonl and external-supervisor-config.json.

To disable future recovery without stopping the current dashboard:

```sh
cd /home/trading/sector-heatmap
.venv/bin/python -m sector_heatmap.workspace_supervisor --registry /home/trading/sector-heatmap/.private/dashboard-login/registry.sqlite3 --root /home/trading/sector-heatmap --account a6ef4c9bcecd21d54c4a07e2b9b137a7 --disable
```

Six tests passed, including a real isolated child-process crash/recovery with live gates asserted disabled, duplicate-owner exclusion, backoff, circuit breaker and disconnected-state preservation. Production activation reported RUNNING with zero launch attempts: the existing Delta process was not restarted. Full production crash injection was deliberately avoided; live exposure was not interrupted. After an automatic read-only recovery, restoring live capability requires an explicit operator-approved normal dashboard reload and separate runner Start; the supervisor never performs these.

Hosted supervisor failure verification: killed only the external supervisor main process. systemd restarted it automatically; the production Delta dashboard owner stayed identical, launch-attempt list stayed empty, and fresh RUNNING heartbeats resumed. Evidence:.private/delta-external-supervisor-verification/.
