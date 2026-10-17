# Server resources

The **Server resources** section uses read-only Linux `/proc`, `ps`, filesystem capacity, and retained sysstat files. It makes no broker requests. Refresh runs every 30 seconds only while the section and browser tab are visible. Server snapshots are cached for 15 seconds, and sysstat history for five minutes.

The `resources` section permission controls access; administrators have access. User Master lists the feature and existing sidebar visibility settings apply. Adding the feature preserves saved choices for all existing sections. A hidden section does not poll. The API independently checks the authenticated user's feature assignment.

CPU work excludes I/O wait and hypervisor steal. All live CPU percentages use all cores as the denominator; process CPU is a lifetime average with one core as 100%. Live memory is total minus available, while sysstat memory follows the installed sysstat definition. Disk capacity has no historical series. Historical CPU values are interval averages, and RAM values are snapshots; neither guarantees the maximum instantaneous usage.

## Deployment status

Deployed to the main Sector Pulse dashboard on 14 October 2026 at 23:58 IST with explicit restart approval. The main `sector-heatmap.service` was restarted; account workers were not restarted. Hosted-only source changes were preserved by comparing the staged base with the running source before installing the five files.

Verified on the signed-in hosted dashboard: live cards, 630 retained history records, range selection, User Master permission and sidebar controls, hide/save/refresh enforcement, and restored visibility. Unauthenticated HTTP API access returns 401. The deployed resource handler was separately exercised against missing and unassigned identities and returns 403. Existing sidebar/Renko visibility choices and recorded runner activation/status/mode flags matched the pre-deployment snapshot. No runners were rearmed.

Server rollback files are in `/home/trading/sector-heatmap/.private/resource-monitor-backups/20261014T182805Z`. Local visual evidence is `outputs/resource-monitor-stage/hosted.png`. The runtime collector remains read-only and has no broker API or order path.

Chart inspection was deployed on 15 October 2026 without a backend restart. Hover selects the nearest recorded point and displays its full date, time including seconds in IST, resource name and percentage. A crosshair marks the selected sample. Charts also support keyboard focus and Left/Right arrows; Escape hides the tooltip. Hosted CPU and memory pointer inspection and keyboard navigation were verified.

## Restart controls

Administrators manage **Restart dashboard** and **Restart selected broker** in
Server resources. Accounts links to that section rather than offering a separate
rolling-bounce control. Non-administrators retain their read-only telemetry view.

Dashboard requests have an idempotency ID and a private durable status file beside
the account registry. A fixed systemd transient timer schedules the main service
restart outside the web process; the service user needs noninteractive permission
to execute that fixed `systemd-run` operation. No client-supplied command or unit
name is accepted. Readiness requires an active service and a changed MainPID.
A timeout reports an unconfirmed outcome and does not submit a second command.

The browser probes every two seconds with a five-second request timeout, including
while telemetry polling is inactive. It persists the operation and timeline in
browser storage, resumes checking on reload, and displays READY, FAILED, or an
unconfirmed outcome. Automatic retries are status requests only. A rejected
request displays the blocker immediately. The existing same-origin, session,
CSRF, administrator and account-ownership checks apply to the command routes.

Broker restarts reuse the existing stopped-state and reconciliation checks.
Dashboard restart checks retained root and account runner state because a main
service configured with `KillMode=control-group` also terminates child workers.
Restarting never stops a strategy first, closes a trade, or rearms a runner.

### Restart controls activation — 17 October 2026

Installed with rollback backup at
`/home/trading/sector-heatmap/.private/restart-control-backups/20261017T091227Z`.
The user authorized activation with a dashboard restart. Final state checks found
no runner requiring an explicit stop; no orders or strategy Starts were sent.
The native FYERS account read was unavailable, so broker-flatness was not claimed.

Hosted verification exercised the actual Restart dashboard button. It
reported SCHEDULED at 14:43:52 IST, WAITING at 14:43:54, and READY at 14:43:58.
Systemd independently confirmed an active replacement MainPID. Controls
re-enabled without another command, browser errors were empty, and reloading the
page restored the complete outcome timeline. Administrator broker choices list
Dhan, Delta India, FYERS and Motilal Oswal. Account-page restart links lead here.

Validation: 40 Python tests (restart persistence/idempotency/guard/permissions,
resource telemetry, broker bounce and workspaces), five browser-code tests
(including lost responses, reload recovery, definitive rejection and admin
visibility), and hosted normal-browser rendering. Archived deployment snapshots
are excluded from the dashboard guard; invalid current runner state fails closed.


### Restart progress indicator

Deployed 17 October 2026 as a browser-only update, without a service restart.
The panel shows an indeterminate progress bar while a restart is pending, the
Request / Restart / Readiness / Complete stages, elapsed time refreshed every
second, status-check count, and the most recent check time/result. Completion is
shown only for READY; failed or unconfirmed requests retain their explicit state.
No estimated completion percentage is invented. Existing two-second probes and
saved outcomes are unchanged. Seven browser-code tests pass, including elapsed
updates, indeterminate/complete progress, failure state and reload recovery.
