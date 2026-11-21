# Reproduce the NIFTY option study

This folder is offline research. None of its replay commands creates broker clients, changes runners or submits orders. Download helpers make read-only historical-data requests and require a separate credentials path; credentials are not part of this dataset.

Run from the repository root with Python 3.11 or later. The replay uses standard-library modules and the frozen indicator source in `frozen-source/`. Fetching also requires `requests`.

```sh
export PYTHONPATH="$PWD/backtesting/nifty_atm_options/frozen-source:$PWD/backtesting/renko_sideways_entry:$PWD"
python -m unittest discover -s backtesting/nifty_atm_options -p test_replay.py
python backtesting/nifty_atm_options/prepare_signals.py
python backtesting/nifty_atm_options/run_grid.py --workers 2
python backtesting/nifty_atm_options/analyse_results.py
python backtesting/nifty_atm_options/journal_candidates.py
python backtesting/nifty_atm_options/analyse_results.py
python backtesting/nifty_atm_options/audit_results.py
python backtesting/nifty_atm_options/build_report.py
python backtesting/nifty_atm_options/seal_study.py
```

`inputs/underlying.json` and `inputs/config.json` are frozen research inputs. The matching `backtesting/renko_sideways_entry/research.py` supplies the feature wrapper; include it when copying this study. `grid.json` records the inputs and frozen production-module hashes. `reproduction-manifest.json` additionally hashes the feature wrapper, research scripts, inputs and cached response files. Verify those hashes before comparing a rerun.

`cache/` contains credential-free raw option responses. `full-grid/results.json` records every configuration, coverage problems, data quality, chronological split and development-selected candidates. `journals.json` contains fixed-strike trade records and marked equity for the baseline and first five selected candidates. `analysis.json` contains paired comparisons and monthly/call/put breakdowns. `report.md` describes costs and replay limitations.

The durable archive at `data/backtesting/nifty-options-2026/` preserves raw versions and a checksum catalog independently of transient replay outputs. Do not publish raw broker data automatically. The archive and local caches do not contain access tokens or account credentials.

Selection is by development net profit with at least 30 development trades. Validation must not be used to choose a replacement winner and then presented as unseen confirmation. The earlier underlying studies already examined these dates. This is a bounded switch-combination study, not an exhaustive search of numeric strategy parameters. Candle-level trailing and quick-loss range observations are approximations; historical expiry is calendar-inferred rather than broker-certified.
