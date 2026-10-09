# Renko automatic recovery

An armed Renko runner has a watchdog checked every five seconds. A missing worker is restarted only while the runner remains armed, retains its process lock, passes its Live gate when applicable, and still belongs to the same broker account. Recovery retains positions, pending intents, consumed signals, management-only permissions, and the active configuration. Its entry eligibility timestamp advances to exclude signals received during the interruption.

An existing worker is never duplicated. After 45 seconds without a step heartbeat, the health status reports `WAITING_FOR_INFLIGHT_WORK`; it wakes the worker and waits for its in-flight work to finish. Recovery attempts have a 30-second cooldown. Account or ownership failures require manual intervention.

FYERS candle history now uses connect/read timeouts of 3/10 seconds. Network failures return to the existing runner retry and chart cache/backoff paths instead of holding a runner/history lock indefinitely. The change does not retry order submissions or change order execution semantics.

Explicit Stop, Stop All, and backend restart remain disarming operations. This watchdog does not restart the server or arm previously stopped Paper/Live runners. Auto recovery starts with the next user-started background runner. Status and recovery counts are included in runner snapshots and shown on the chart.

Validation: watchdog failure/ownership/gate/intent tests, FYERS timeout tests, full Renko regression suite, chart JavaScript tests, and a read-only authenticated Sensex history request.

Read-only FYERS profile, positions, order-book and funds checks also use 3/10-second connect/read timeouts. A failed read blocks execution; it never retries a submission. The watchdog captures private Python thread stacks at most once every two minutes while a living worker is stale, allowing the precise blocking call to be diagnosed. These network timeouts are not an absolute wall-clock deadline for a slowly streaming response.
