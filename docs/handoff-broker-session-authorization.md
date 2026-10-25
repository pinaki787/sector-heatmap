# Auto schedule authorization

Enabled schedules saved by their authenticated owner hold a persistent, revocable account grant. Dashboard logout, expiry, or scheduler restart does not remove that grant. The runtime restores only explicit grants for enabled schedules and retains interrupted-work reconciliation without replay.

Ownership and section permissions are checked before background actions. Pause revokes the grant. Broker credentials, account Live permission, daily loss limits, exposure, capital, quote freshness, durable claims and protected-order checks remain required. Broker authentication failures prevent new entries; dashboard login is still required for interactive settings and manual confirmations.

FYERS constituent attribution is read directly through the isolated broker worker using official sector constituents, without a dashboard cookie. No browser sessions or broker credentials are minted or renewed by the scheduler.

The existing explicitly authorized FYERS Auto schedule was migrated on 25 October 2026; disabled accounts were not authorized or rearmed.
