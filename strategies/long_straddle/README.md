# Bundled NIFTY and SENSEX long-straddle modules

Reviewed user-owned external module sources copied into the release on 7 October 2026.
Formula/default documentation: [technical guide](../../docs/technical-guide.md).
On an existing installation, explicit script overrides or the existing legacy files
retain precedence. Fresh installations fall back to these bundled scripts. Configure
SECTOR_PULSE_NIFTY_STRADDLE_SCRIPT or SECTOR_PULSE_SENSEX_STRADDLE_SCRIPT to deliberately
select a specific reviewed source. No running process is replaced by changing files.

Direct CLI defaults to Paper; LIVE requires --live and explicit confirmation. The
web bridges have their own deliberate LIVE start confirmation. These subprocesses
are not globally gated by the EMA/KAMA/parser switches. Never assume those switches
protect a separately confirmed straddle LIVE start. No process starts during setup.

NumPy/pandas are installed by requirements.lock. Broker credentials come from the
bridge environment or FYERS token cache. Runtime directory environment variables:
NIFTY_STRADDLE_RUNTIME_DIR / SENSEX_STRADDLE_RUNTIME_DIR. Fresh bridge runtime lives
under .private. Do not include logs, position state or guard files in source archives.
Paired market-order legs are not an atomic broker transaction. Acceptance is not fill
proof; partial-leg execution and process failure require broker reconciliation.
Historical formulas and lot constants do not establish current contract validity.
