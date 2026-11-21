# Saved analysis and runner jobs

The hosted dashboard now opens Saved jobs & reports as a full main view, using the existing runner-jobs section identity. Analysis, runner history and current runner controls share the page. Search, account, type and status filters retain owner-scoped access. Pagination merges permitted accounts chronologically by creation timestamp descending, then job ID; progress updates do not reorder old runs. Counts identify loaded history rather than implying a complete current inventory.

Saved output opens in a full-width readable inspector with captured strategy settings, including all three EMAs, human labels, trade observations and provenance. JSON is an optional Download JSON audit action. Returning to the ledger preserves the selected row and focus. Existing runner handlers and stop controls are embedded without starting jobs through navigation.

The existing section permission and sidebar visibility key are reused. Hosted testing hid both navigation and page access, including for the administrator, then restored the exact serialized visibility baseline. No role assignments were changed. Per-feature job API ownership checks remain unchanged.

Desktop and 390 CSS-pixel mobile views were inspected, including the ledger and incomplete saved backtest report. Reports use normal page scrolling, with horizontal scrolling confined to wide trade tables. There are no saved-output modal dialogs or raw JSON report blocks. Newest-first ordering was verified across accounts and older-page loading.

Validation: 27 focused UI tests passed; 25 historical-lot/backtest Python tests passed. The full strategy suite had 490 tests with three failures and one error already reproduced on baseline. The FYERS correction was activated through the approved guarded reload; other broker workers were not restarted. Nine canonical state hashes remained unchanged. Final read-only checks found zero FYERS open positions, zero pending/transit orders and all eight saved Renko runners stopped. No orders were submitted.

The corrected historical report remains INCOMPLETE because authoritative lot metadata applicable to its exact contract and trade date is missing. Quantity-dependent performance is withheld, and the earlier assumed-lot report is SUPERSEDED. See renko-dated-master-lot-sizing.md for evidence and policy.
