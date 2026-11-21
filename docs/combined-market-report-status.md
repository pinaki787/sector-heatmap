# Combined shared market report — 23 October 2026

User authorization: one combined sector analysis, Analysis Handoff and screener report to the existing Sector Pulse Trade Alerts channel every 15 minutes during NSE regular market hours. Private execution/P&L and existing email rules remain separate.

## Installed and active
- sector-pulse-combined-reports.service: enabled and running.
- NSE trading-session/holiday gating; one durable event per account and slot.
- Sector snapshot and latest owned completed Handoff source. Reading Handoff cannot rerun analysis or cause trading.
- Periodic screener analysis reuses the dashboard algorithm in an isolated worker. The last explicitly submitted FYERS screener universe currently contains 134 symbols. Token checks bind the account, and live capability environment flags are off. Chartink membership is not automatically refreshed. Coverage and per-source candle timestamps are explicit.
- Separate shared sector/Handoff Telegram posts are suppressed; their email delivery is unchanged. Combined reports create no email delivery rows.
- Combined Telegram pause/resume and existing global pause controls apply.
- Unknown Telegram outcomes go to REVIEW, with no blind replay.

## Verified
- 37 focused tests across combined reporting, routing isolation, controls and image transport.
- Live read-only broker smoke check completed 2/2 symbols.
- The same 2/2 check passed under the deployed reporting service sandbox.
- Initial Telegram photo accepted as message 70 in the verified shared channel.
- Startup attempt also delivered message 71 with screener explicitly unavailable; its SDK log-path restriction was corrected. Initial-slot overlap suppression is installed for subsequent activations.

## Remaining verification
The first full scheduled scan completed on 23 October 2026: started 12:15:10 IST and completed 12:23:02 IST, with 134/134 unique symbols analyzed. The combined report was accepted by Telegram; receipt details and source-specific timestamps are retained beside the event image. One event and one SENT Telegram delivery row exist for this slot; no email row exists.

No order submission, trading activation, runner changes or dashboard restart was performed for this reporting deployment. Option-premium targets are labeled separately from underlying proposed invalidation.

Full-cycle Telegram acceptance: message 72. Its screener quality label was corrected in place to BROKER EVIDENCE DELAYED; Telegram confirmed the same message ID, so no extra notification was created. Screener candle as-of 12:00 IST; sector as-of 11:45 IST; Handoff latest available as-of 10:15 IST, explicitly stale.
