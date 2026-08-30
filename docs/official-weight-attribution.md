# Official NSE Indices weight attribution

## Provenance and coverage

The active dataset is
`sector_heatmap/data/nse_weights/2026-07-31.json`, sourced as of 31 July 2026
from NSE Indices Limited. Each sector entry preserves its official index name,
factsheet URL, constituent-file URL, total index constituent count, published
constituents, and weights. The JSON is the runtime source of truth; no proxy
basket or explanatory relative weighting remains in the sector configuration.

The official public factsheets list the ten largest constituent weights. Nifty
IT, Nifty Realty, and Nifty Media each had ten constituents and therefore have
complete public-factsheet coverage in this snapshot. All other configured
indices had more than ten constituents and are explicitly partial. Their top-ten
published weights are used exactly as stated and are not scaled to 100%.

The runtime API reports, per sector:

- `OFFICIAL_COMPLETE` or `OFFICIAL_PARTIAL`;
- source-as-of date and factsheet/constituent URLs;
- published and total constituent counts plus covered weight;
- the number and weight of published constituents with a usable live FYERS tick.

The top three list ranks available constituents by absolute percentage-point
contribution while retaining the sign. It is attribution for the published
coverage, not a claim that partial sectors reconcile exactly to the full index
move. If a sector is added without authoritative weights, it must report an
unavailable status and must not inherit a proxy basket.

## Calculation and timestamps

For each published constituent:

```text
stock_change_pct = (live_price - previous_close) / previous_close * 100
contribution_pp = official_weight_pct * stock_change_pct / 100
```

Both calculations use unrounded floating-point values. Rounding occurs only in
the browser. `provider_tick_timestamp` preserves the raw FYERS value,
`provider_tick_timestamp_iso` is its display-friendly normalization, and
`snapshot_at` records when the API response was assembled. `updated_at` is the
latest available provider tick time, never a fabricated fetch time.

## Safe monthly refresh

1. After the monthly factsheets are published, download each factsheet and
   constituent CSV using the official URLs already recorded in the latest JSON.
   Verify the document's printed source date and index constituent count.
2. Copy the latest JSON to a candidate outside the installed data directory.
   Set `dataset_version` and `source_as_of` to the same new ISO date, transcribe
   the published weights without renormalization, and update official URLs if
   NSE Indices changed them.
3. Validate without modifying the repository:

   ```sh
   python scripts/refresh_official_weights.py /path/to/candidate.json --check-only
   ```

4. Review the diff against both the official factsheet and constituent CSV.
   Pay particular attention to ticker renames, additions/removals, weight totals,
   and whether the complete/partial classification changed.
5. Install atomically as a new immutable version:

   ```sh
   python scripts/refresh_official_weights.py /path/to/candidate.json
   ```

   The updater rejects non-official URL hosts, invalid totals, sector-set drift,
   non-newer dates, and overwrite attempts. It never fetches credentials or
   contacts a broker.
6. Run `python -m unittest discover -s tests`, `npm run self-test`, and the client
   lint/build checks; then restart the read-only dashboard and verify the source
   date, coverage labels, and contributor values in a browser.

This workflow deliberately requires human review of official monthly documents.
NSE Indices offers separately licensed constituent/weight data products; unless
such an authoritative full dataset is explicitly added and versioned, public
top-ten coverage remains labelled partial.
