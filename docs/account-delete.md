# Broker account deletion

Remote source implementation, 27 October 2026. Activation and hosted visual acceptance remain pending.

Accounts renders Delete only when the authenticated server advertises account_delete. The confirmation names label, broker and reference and requires the exact reference. POST /api/workspaces/delete requires existing same-origin/session/CSRF checks; the runtime rechecks user ownership.

Delete archives the full registry registration in deleted_accounts and removes it from the active registry in one transaction. Account folders, private saved settings, trading evidence and journals remain on disk for administrator recovery/audit. This is registration removal, not a broker-account closure or broker-session revocation. No positions or orders are changed. Account references can be reused with a fresh generated workspace ID; archived ports remain reserved so stale URLs cannot reach a replacement account.

Deletion blocks a running dashboard, an in-progress bounce, active/unreadable canonical runner state, and held runner locks. Dhan also uses the shared dashboard, so its shared canonical runner states are conservatively checked and locked. A stopped dashboard is required; this operation never stops one. Reconcile broker exposure before stopping an account dashboard.

Owner process: main heatmap_server.py on 127.0.0.1:8080, cwd /home/trading/sector-heatmap. local_dashboard_auth builds the portal handler in this process. Its Python modules require a specifically authorized main service reload/restart; no such action was performed. JS/CSS are served from disk, but the capability gate keeps Delete hidden under the previous backend.

Validation: .venv/bin/python -m unittest tests.test_workspace_delete tests.test_workspaces (25 passed); node --check workspace-portal.js. Tests use temporary registries only. Hosted JS/CSS contain new code. Desktop/narrow rendered acceptance and authenticated capability verification must follow authorized activation. No production account was deleted.
