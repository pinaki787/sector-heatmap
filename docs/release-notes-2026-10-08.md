# Sector Pulse release — 8 October 2026

Code baseline: `06b7cb7`. The source archive commit and checksum are recorded in its generated manifest; the archive includes the updated guides and packaging script.

- Renko entries require fresh completed one-minute/five-minute Supertrend agreement, including manual entries.
- Optional confirmed market structure and five-minute opposing-zone exits default off.
- Explicit manual override acts once on an active flat run; execution gates and ordinary exits remain active.
- EMA exit timing follows Intrabar entries. Fresh automated entry preflight rejects an already adverse exit EMA.
- Chart markers use recorded fill/EMA evidence; assessments survive routine history revisions. Feed status separates market ticks and runner snapshot age.
- Setup supports saved configuration restore/delete; Delta Continuous activation handles an absent daily cutoff.
- Analysis Handoff proposes and executes a single verified bought ATM Call/Put instead of a spread basket.

See the [user guide](user-functional-guide.md), [technical rules](technical-guide.md), and [deployment guide](deployment-guide.md). Existing saved configurations and runtime exposure must be reviewed before a deliberate restart or Start. Publication and archive creation do not restart the backend, arm runners or submit orders. Strategy research is not proof of profitability.

## Validation

The code baseline passed 293 Renko Python tests, 6 long-option handoff tests and 26 relevant JavaScript tests on macOS. Documentation links/catalog and both portability tests passed for this release. Runtime dependency/timezone readiness passed on the existing macOS environment. A fresh dependency installation/build was not repeated. Windows broker execution and real fills are outside that verification. Installation requires network downloads, the runtime lock, client build, destination broker authentication and any macOS WhatsApp permissions. Credentials, runtime state, journals and bulk market data are excluded from the source archive.

## Build and verify

Run `python3 scripts/package_release.py` after committing the reviewed source. Outputs are under ignored `output/releases/`: source `.tar.gz`, `.sha256` and per-file `.manifest.json`. The builder resolves the exact commit, uses `git archive`, rejects private paths and common credential patterns, and never copies local environment or private state. Verify the SHA256 before extracting; use setup-only and the stopped/exposure-safe update procedure in the deployment guide.
