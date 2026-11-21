# Notification pause/resume and Analysis Handoff images

Prepared on Ubuntu on 20 October 2026. Activation is pending the owner's permission
to restart notification services and start the two new notification-only services.
No dashboard, broker service, trading runner, position, order or trading permission
was changed. No new broker analysis or AI call is performed.

## Owner controls

The existing Sector Pulse Trade Alerts bot provides /notifications and a button
panel. Global and per-category settings separately control Telegram and Gmail for:
- Trade alerts
- Sector images
- Analysis Handoff

Owner-only /pause_telegram, /resume_telegram, /pause_email and /resume_email commands
are also supported. A private callback must match BOTH the configured private chat
and sender ID. Unrelated chats/senders cannot change settings. There are no trading
commands. Explicit owner control replies remain available when alerts are paused.

Preferences live in .private/notifications/preferences.json (0600), with a file lock
and atomic updates. Workers read preferences before each delivery; toggling does
not need service restarts once activated. Global pause overrides category state.
Resume sends NEW updates only: paused backlog is marked SKIPPED, not replayed.
Missing initial preferences mean default on; malformed preferences hold delivery.

The gate is per-channel, so pausing Telegram does not pause Gmail or vice versa.
Pause affects deliveries that have not begun; an already in-flight provider call
may finish. A provider outcome that is unknown remains REVIEW, never silently retried.

## Analysis Handoff

The observer reads owner- and account-scoped COMPLETED ANALYSIS jobs from the actual
workspace persistent-jobs.sqlite3 files, using SQLite read-only mode. It never
constructs JobStore (which would mutate interrupted jobs), reruns an analysis,
contacts an AI provider, submits an order, or refreshes broker authentication.

New completed reports trigger images. This is event-driven, not a periodic rerun
of analysis. Existing reports are suppressed by an activation cutoff. A single
clearly labelled historical saved-report image was used for delivery validation.
An empty/no-eligible-plans result is a valid outcome and is rendered honestly.

Supported results: stock Analysis Handoff card results and index/commodity
MARKET_HANDOFF results. Labels preserve broker, generation time, source data
quality, direction, original eligibility status and analysis-only order authority.
Incomplete/unsupported/broker-mismatched outputs are retained as WITHHELD audit.
No strike, quantity, price, stop, target or execution state is inferred.

New completions older than 15 minutes are withheld. Generation time must agree with
completion within one hour. Images expire after 30 minutes if delivery is pending.
The original dashboard result remains the full source of record. Prices in an
image are saved evidence and require refreshed quotes before any trading action.

Handoff-specific Telegram/Gmail captions and email attachment names are prepared.
PNG and normalized JSON evidence are retained in .private/notifications/sector-cards.
Audit: .private/notifications/handoff-outbox.sqlite3
Controls offset, health and errors: .private/notifications/controls.sqlite3

## Prepared deployment

New units:
- sector-pulse-notification-controls.service
- sector-pulse-handoff-cards.service

After explicit approval: enable handoff_cards in protected config, install/start
those two units, restart ONLY sector-pulse-notifications.service and
sector-pulse-sector-cards.service to load the delivery gate, then publish the owner
control panel. Preserve existing enabled flags and existing pause preferences.

Do not restart/reload dashboard or broker services or alter runners/orders.
Verify each notification heartbeat, owner-only controls and delivery state.

Stop only Handoff images:
  sudo systemctl stop sector-pulse-handoff-cards.service
Stop only the bot controls:
  sudo systemctl stop sector-pulse-notification-controls.service
Existing pause preferences still govern running senders if the controls service stops.

## Validation

32 standard-library tests pass across notification controls/Handoff (11), existing
trade notifications (12) and sector cards (9). Coverage includes private-owner
authorization, category/global independence, persistent preferences, future-only
resume, no sends while paused, broker/owner job isolation, read-only source access,
saved-report rendering, missing output, historical suppression and stable job IDs.
The prepared systemd units validate without errors (unrelated legacy-unit warnings).

  .venv/bin/python -m unittest discover -s tests -p test_notification_controls_handoff.py -v



## Deployed destination separation — 20 October 2026
- User Master email delivery is OWN_ACCOUNT_ONLY with explicit checkbox opt-in. Empty or WAIT-only Analysis Handoff outcomes do not send email.
- Private Telegram channel **Sector Pulse Updates** was created, verified private, and connected to the existing bot with posting permission. No people were invited; the only subscribers are the owner and publisher bot.
- New supported confirmed ENTRY/EXIT events belonging to pinaki87 route to that private channel, with recorded realised P&L where available. This does not generate ongoing unrealised P&L valuations or replay existing positions.
- Shared read-only channel **Sector Pulse Trade Alerts** is now created and connected to the existing bot as posting-only publisher. Market images and Analysis Handoff route there; personal executions and P&L cannot route there. No people were invited; readers must join via the shared channel invite link.
- Telegram destination routing rejects missing/foreign event ownership, invalid or colliding channel IDs, and pre-activation events.
- Notification workers only were reloaded. Dashboard main PID remained unchanged. No runners or orders were changed.
- Remote notification suite: 55 tests passed.

- Shared channel welcome post was confirmed by Telegram. Both channel routes were checked against the live protected configuration. All four observer/control heartbeats are fresh; the dashboard main PID remains unchanged.
- Handoff service permits SQLite coordination files in the three existing saved-job database directories; its SQL connections remain mode=ro. This resolved the read-only mount failure.
