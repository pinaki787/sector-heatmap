# Sector rotation image delivery

Activated with explicit owner approval on 20 October 2026.

## Delivery

- Same existing private Telegram bot chat and same owner Gmail address as trade alerts.
- Every 30 minutes during NSE regular market hours, using the project trading calendar.
- Intraday mode; reads all 14 sectors from the owner's actual FYERS dashboard history:
  account home/.fyers/sector-heatmap/analysis-history.json.
- The image shows actual composite/relative-strength scores (0-100), rotation states,
  source, market-bar timestamp and image generation timestamp. Scores are not returns.
- No new broker history requests, broker orders, credential entry, dashboard reloads
  or trading runner operations are performed.

Source refresh remains owned by the existing FYERS dashboard analysis process.
The scheduler polls its persisted snapshot; it does not manufacture a fresh timestamp.
During an open session, market bars must be from today and at most 45 minutes old;
analysis observation must be at most 40 minutes old. Unavailable/stale images are
withheld and the job reason retained. Missing sector scores are shown as N/A.
Regular deliveries stop on weekends, holidays and outside regular market hours.
A delayed first card cannot cause another scheduled card less than 30 minutes later.

## Initial verified delivery

20 October is the Dussehra market holiday. An explicitly labelled LAST COMPLETED
SESSION image used real bars from 19 October, 15:15 IST. Telegram sendPhoto confirmed
acceptance. The Gmail message was independently found in the owner's INBOX with
both its inline PNG and downloadable PNG attachment.

Scheduled in-session freshness gates were verified using synthetic tests. Their
next real open-session behavior cannot be observed during today's market holiday.

## Service and audit

sector-pulse-sector-cards.service is independent of sector-pulse-notifications.service.
Only the new image service was started/restarted for this change. Trade-alert worker,
dashboards and trading runners were not restarted.

Protected config sector_cards lives in .private/notifications/config.json.
Durable job IDs, channel delivery records and heartbeat:
  .private/notifications/sector-outbox.sqlite3
Retained PNG and JSON evidence:
  .private/notifications/sector-cards/

Provider failures retry independently. Unknown delivery outcomes become REVIEW,
rather than risk duplicate sends. Pending/retry images expire after 30 minutes.
Stable job IDs prevent restart duplication. Rendering/delivery does not block orders.
Gmail includes plain text, HTML inline PNG, and a downloadable PNG attachment.

Status:
  .venv/bin/python -m sector_heatmap.sector_cards status
Stop this schedule only:
  sudo systemctl stop sector-pulse-sector-cards.service

Dependencies: Pillow installed in the notification-private render-libs directory;
production .venv packages were not modified. Renderer works without an AI API.

## Validation

  .venv/bin/python -m unittest discover -s tests -p test_sector_cards.py -v
  .venv/bin/python -m unittest discover -s tests -p test_trade_notifications.py -v

Tests cover regular-session slots and holidays, bar/analysis freshness, explicit
closed-session initial snapshots, no-data refusal, actual PNG rendering, inline and
attachment MIME structure, source account isolation, persistent job deduplication,
expiry, withheld-job audit and minimum delivery spacing.

Calendar source for the verified holiday:
https://www.nseindia.com/resources/exchange-communication-holidays

