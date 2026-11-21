# Renko swing breakout entry gate

Remote source implementation, 3 November 2026. The affected FYERS Algo runner was activated after explicit user approval; other broker workers remain untouched. See the activation evidence below. No manual order was submitted.

New Renko configurations capture `swing_breakout_bricks` (default 2; integer 1–100). The setting is saved with instrument preferences and named browser configurations. Existing captured configurations without the key retain their earlier entry rules, including after recovery. A new Start captures the visible setting. The frontend blocks Start against workers without the capability revision.

Swings use completed Renko **closes**, with strict two-left/two-right confirmation. This follows the existing structure confirmation convention while avoiding equal adjacent brick-edge plateaus. The pivot origin and actual confirmation observation are retained. It is unavailable until two later bricks complete. No forming brick advances the recurrence. Historical candle-derived bricks and ordered live-price bricks use the same persisted inner-engine recurrence.

BUY requires consecutive completed closes strictly above the confirmed high; SELL strictly below the confirmed low. Equality or a return inside resets the count. An attempt freezes its reference; newer pivots are used after a reset or after an already-completed attempt. Missing required swing evidence blocks new opted-in entries. Selected indicator gates and exits remain independent. Shared initial, continuation/re-entry and submission authorization paths enforce the gate, including manual override submission. Broker subclasses inherit the shared gate. Preflight checks the current price publication again.

The existing Renko section permissions cover the control; no new card or permission key was introduced. UI displays at most two decimals; recurrence retains full precision. Chart markers and price-axis swing labels use backend evidence. Chart settings and captured runner settings remain distinct.

Validation: focused Python recurrence, execution, broker inheritance, price feed, gap-brick, structure and continuation tests; JavaScript settings/live-source tests; all eight source trees syntax checked. Hosted desktop and 390px control presentation verified. After approved FYERS activation, real hosted swing values, labels, captured settings and fresh entry-gate evidence were verified. Execution rejection paths were tested without sending broker test orders. Other broker workers have not been activated.

## Approved FYERS activation — 3 November 2026

Following explicit user approval, only FYERS Algo account `bf46fc364b610a0dfd338419e133cb41` was reloaded through the existing guarded broker bounce. The affected CRUDEOILM runner was already stopped and flat; fresh broker profile, account identity, positions/orders and WebSocket price evidence passed. The same instance `ebd4221ba77d52b60d29` was started in LIVE, one lot, five minutes, with its previous configuration plus only `swing_breakout_bricks=2`. The preference count is also saved as 2. No unrelated runner was started/stopped and no manual order was submitted. Other broker workers were not reloaded.

New run: `RENKO-RUN-11e7b7ce20904f931ae7`. Fresh actual entry assessment includes the new swing evidence and count=2; the existing EMA100 entry condition blocks the observed setup. The hosted chart displays confirmed high 8979.54 and low 8921.42 and their price-axis labels; hosted settings show captured confirmation=2. At verification it is running, entries enabled, flat, no pending intent and zero new-run trades. State/evidence: `.private/swing-breakout-activation-20261103/result.json`. Shared entry/submission tests establish rejection behavior without placing test orders.
