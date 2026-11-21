# Display history revision recovery

Delta chart requests could repeatedly fail with HTTP 409 when completed broker OHLC candles changed before retained fingerprints. Display calculations now catch HistoryRevision only and rebuild from the identical original anchor. Execution analysis guards and runner state are unchanged. Live chart display recurrence is explicitly reseeded after recovery with a new revision; ordinary refreshes retain accepted live bricks.

Root and all seven account sources updated. Delta only activated using guarded workspace bounce after confirming all three canonical runtime files stopped, flat, without pending orders. Backup: .private/chart-history-recovery-1793936603. Activation evidence: .private/delta-chart-history-activation-1793936630. Forty targeted tests passed, covering strict history guards, recovery, live recurrence, and chart configuration.

Separate current browser evidence: FYERS CRUDEOILM screen reports FYERS Not connected. This authentication issue is independent of the Delta cache recovery.
