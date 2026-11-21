# Private trade notifications

Prepared in the authoritative Ubuntu checkout on 20 October 2026. This is an
independent observer; it does not import broker execution clients, call trading
APIs, modify runner state, or require dashboard/runner reloads.

## Current status

Credentials for both channels were entered by the owner and verified using the
secure setup helper. A clearly labelled non-trade test was accepted by Gmail SMTP
and Telegram sendMessage. SMTP acceptance is not proof of inbox placement.
The owner explicitly approved activation. Continuous notifications are enabled;
sector-pulse-notifications.service is installed, enabled for boot, and running.
An advancing heartbeat, zero scan errors, and zero service restarts were verified.
No dashboard or trading runner was restarted.

Owner pinaki87 selected BOTH Paper/Live, ALL four owned broker workspaces, EACH
confirmed fill update, the same confirmed Gmail sender/recipient, and their private
Telegram chat. Secret configuration: .private/notifications/config.json (0600).
Do not print this file, copy it to source snapshots, include it in logs, or commit it.

## Fill coverage

The observer reads the ACTUAL account runtime files, including source/.private
for FYERS/Delta and account-scoped Dhan/Motilal strategy folders. Account Renko
Engine state is included. It observes persisted order_history entries with positive
confirmed filled quantity and recorded average price, including partial fills.
Native Delta India Paper trades and Live orders also have adapters. EMA Band and
KAMA Paper journal entries/exits are supported.

Older EMA Band/KAMA Live SUBMITTED logs and manual handoff/parser ticket acceptance
records are NOT execution confirmation. They are excluded. Broker-side fills
outside supported persisted journals, including external/manual executions not
reconciled into an owned journal, are not covered. No order-book polling or broker
reconciliation is performed by this worker. Full all-route Live coverage remains
incomplete until owning routes retain confirmed fill evidence.

Local confirmation time is labelled separately from unavailable exact exchange
fill time. Paper messages explicitly identify simulated fills. Incremental prices
come from differences in cumulative filled notional. Exit P&L uses verified linked
entry fills and contract multiplier; otherwise it is reported unavailable. P&L is
before fees, in the stated native currency when recorded.

## Durability and delivery semantics

SQLite WAL/FULL outbox persists fill checkpoints, events and independent channel
delivery records. Initial baseline suppresses historical trades. Later-discovered
old rows are suppressed using the persisted cutoff. A baseline cannot be repeated
after preparation. A process lock prevents concurrent senders.

Confirmed transport failures retry with exponential backoff capped at one hour.
A sent channel is never resent because the other channel failed. SMTP/Telegram
have no shared transactional exactly-once guarantee. A timeout/disconnect or
process interruption with an uncertain remote outcome becomes REVIEW, rather than
automatically risking a duplicate. Review requires human reconciliation; no
automatic replay is provided. A stable event ID is included in messages.

The observer polls recognized durable files every three seconds. A file that is
overwritten/truncated before observation can lose evidence; trading histories
must be retained. Unsupported/malformed ledgers are recorded in scan status
without disclosing their content.

## Operations (activation requires explicit authorization)

Status, without secrets:
  .venv/bin/python -m sector_heatmap.trade_notifications status

The prepared unit is deploy/sector-pulse-notifications.service. After approval,
atomically set enabled=true in the protected notification config, install the unit
as /etc/systemd/system/sector-pulse-notifications.service, reload systemd unit
metadata, and enable/start ONLY sector-pulse-notifications.service. This is not
permission to restart/reload any dashboard, broker service or trading runner.

Stop only this worker with:
  sudo systemctl stop sector-pulse-notifications.service

Inspect delivery counts and heartbeat using status. REVIEW records and scan errors
must be resolved explicitly. Do not infer trading runner health from notification
worker heartbeat. Do not automatically regenerate/rotate Telegram tokens.

## Validation

12 standard-library unit tests cover accepted/unfilled rejection, partial-fill
deltas, restart deduplication, historical suppression, linked long/short exit P&L,
Paper/Live filtering, complete-fill policy, independent retries, ambiguous-send
recovery, account/backup isolation, Paper journal mappings, concurrent status and
secret-safe transport errors.

  .venv/bin/python -m unittest discover -s tests -p test_trade_notifications.py -v

Delivery test CLI sends a clearly labelled non-trade test to the configured owner:
  .venv/bin/python -m sector_heatmap.trade_notifications test

Use only with owner authorization. Test success means provider acceptance, not
verified mailbox inbox placement. Test messages must never be mistaken for trades.

