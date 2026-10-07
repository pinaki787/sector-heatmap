# Trailing exit research (no deployment)

Run offline from this folder with Python 3.10+:

```sh
python prepare.py
python research.py
python summarize.py
python uncertainty.py
python case_analysis.py
python case_counterfactuals.py
python -m unittest discover -p test_research.py
```

The HTML report is generated with `python report.py`.

Raw FYERS replies, frozen configuration, source snapshots and SHA256 manifest are retained. `prepare.py` freezes one-minute entry opportunities with the source Renko/EMA/RSI/retest calculations. It uses completed closes and next contiguous opens, keeps baseline EMA10, opposite reversal and session exits, and models the quick-loss re-entry lock with underlying gross loss because historical option after-cost lock data are unavailable. It deliberately imposes no invented daily trade quota: the application's max-trades quota belongs to a user-armed run. This historical study does not reconstruct actual arming/reconnection, eligibility, quota, funding or fills. Entries remain identical across exit candidates.

`research.py` has no API calls or execution paths. It requires contiguous nonzero-volume option candles, with no forward-filled stale prices. It evaluates completed one/five-minute confirmed swing and volatility stops, a sampled-price approximation of the existing tick trail, and five-minute structure plus premium-profit retention. A separate EMA replacement arm is hypothetical only. Historical contract catalog selection is nearest unexpired expiry, nearest strike, lower-strike/symbol tie break; retrospective catalogs do not establish historical listing time. October futures signal candles are held fixed throughout; basis differences versus earlier option deliverable futures are a limitation.

Data collection scripts perform only FYERS history GET/read methods using existing credentials; they do not authenticate, place orders or change settings. `fetch_selected.py` fetches listed contracts through both current and expired history endpoints and reuses sufficiently covering saved replies. Data-only scripts that require the app dependencies should use `/Users/pinaki/trading/sector-heatmap/.venv/bin/python`.

Net premium-point results use an explicitly provisional cost sensitivity (0.1% each turnover plus ₹40 round trip at 200 effective units) and 0/0.5/1/2% adverse price adjustment per side. These are not verified MCX fees or measured spread. Historical lot multipliers remain unverified. Real option trade prices are distinct from executable bid/ask and from underlying-price results. No parameter here is an approved trading recommendation.

## Source release
This folder contains research source and tests only. Obtain the input candles,
contract catalog and frozen configuration separately. Private journal case samples
and bulk market data are intentionally absent. Scripts needing those inputs cannot
run until the user supplies them. No optimal trailing setting was established:
apparent hybrid benefits reversed under intraminute path sensitivities. Never
activate these hypothetical exits from this source release. Collection scripts are
read-only but require separately configured broker credentials and market metadata.
