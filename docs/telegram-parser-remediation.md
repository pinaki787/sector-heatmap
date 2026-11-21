# Telegram parser remediation — 20 October 2026

## Prepared and verified on authoritative Ubuntu
- Isolated Delta ownership for option tickets and unattended Paper. FYERS retains its own reception/native-ticket context; no cross-broker mutation route.
- Persistent private lifecycle state, bounded event trail, heartbeat, actionable start rejection and separate reception/route/verification stop reasons. Restart never rearms.
- Saved explicit gold-proxy choice and selected Paper exit settings. Proxy disabled by default; XAUUSD is blocked when off. Manual preview and unattended Paper both require the proxy choice.
- Reader restoration validated the legacy Telegram identity against the independently verified notification-owner identity, verified membership in the source channel and restored only the same administrator's Delta workspace. No other account received reader credentials. No old queue, running state or armed state was imported.
- Existing legacy files remain protected recovery evidence; ownership marker prevents a newly loaded legacy context from starting the migrated reader.
- Optional Telethon 1.45.0 installed in the shared virtual environment; dependency check passes.
- Root and owning isolated source snapshots updated; browser script version bumped. UI blocks unattended starts when the server still lacks the new lifecycle capability.
- 94 Telegram tests + 3 Delta Telegram tests + 20 workspace tests + 21 workspace-proxy tests pass (138 total). Node syntax and all isolated source compilation pass.

## Activation boundary
Delta activation completed after the approved account-only reload. FYERS activation is deferred because its Live CRUDEOIL manager still has an open position; no FYERS reload was attempted.
The Delta account dashboard process on port 8101 must be safely reloaded to load the restored subscriber configuration and revised pipeline/guards.
The FYERS account dashboard process on port 8102 must be safely reloaded to load its broker restrictions, status metadata and owned-Delta link.
Do not restart the parent sector-heatmap.service: its control group includes other account dashboards and active runner management.
Check current runners, open positions and pending orders before proposing either approved account reload; retain/recover owned management explicitly.
Reloading is not authorization to start reception, unattended Paper, Live Auto or a trading runner. Those remain stopped until separately authorized.
Static source update is not proof of activated backend behavior.

## Review and recovery
Reviewable source-only patch and protected originals are under .private/telegram-parser-fix-backups, plus .private/telegram-parser-remediation.patch.
All credential/session restoration evidence is owner-only; no credentials are included in the patch.

## Activation verification — 20 October 2026
- Approved Delta-only reload used the existing administrative broker-bounce control and returned READY. Delta owner changed from 205616 to 746619; parent 205601, FYERS 205994 and Dhan 205602 were unchanged.
- Hosted Delta status: workspace DELTA_INDIA; route SUBSCRIBER; configured true; dependency READY; authentication AUTHORIZED; channel VERIFIED. Verification was receive-only and did not start reception.
- Hosted reception running=false, unattended Paper running=false, Live Auto false, lifecycle NOT_STARTED, gold_proxy=false.
- Hosted UI locks Order broker to Delta and shows the proxy checkbox unchecked. No Start action or order submission was performed.
- FYERS blocker: current LIVE MCX:CRUDEOILM26OCTFUT manager running with an open position, accepting_entries=false, pending=false, and state heartbeat about one second old. Restart guard refused its preflight. Its old bounce READY record is historical, not proof of safe current state.
- No safe in-process component reload exists for the FYERS handler closure. Keep its prepared code on disk and defer its account-dashboard reload until current position management can be preserved safely. Do not stop the manager or restart the parent service.
