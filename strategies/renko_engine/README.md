# Renko Engine

Current account-bound implementation uses independent Pine rules with the shared durable broker lifecycle. Start runner submits the visible Paper/Live configuration directly; there is no preview button, activation confirmation field or typed phrase step. Internal preparation preserves broker/account validation, capital/risk checks, anchor coverage, ownership locks, fresh signals and reconciliation.

The UI supports the already-running v1 backend by preparing internally during the same Start click. This lets the confirmation panel removal deploy without interrupting active runners. The v2 backend accepts the complete configuration directly, with no public preview endpoint or client revision prerequisite. Existing processes load backend changes at their next normal restart.

Validation: `python -m unittest tests.test_renko_engine tests.test_renko_engine_routes`; `node --test tests/renko-engine.test.cjs`. Tests use fake brokers; no runner was started against a real account for verification.
