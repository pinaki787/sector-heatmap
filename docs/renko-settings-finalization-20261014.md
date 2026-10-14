# Dhan/FYERS settings rollout and preset cleanup

Manual trend filter and prior selected-ATR sizing are loaded in Dhan as well as FYERS. Dhan routing and account handling were preserved. Ninety-two Dhan-specific checks passed; the manual trend tests passed against the deployed Dhan source. Dhan was checked stopped/flat with zero broker positions/orders before its earlier worker reload.

The browser restore now preserves a newer saved Live/Paper choice for a stopped runner instead of restoring its old execution snapshot. Preference mode restoration is independent of chart-refresh generations and does not override a user edit during loading. An active runner retains its actual execution mode. Mounted-page checks use mocked readiness/transport and assert settings transfer, not actual Live activation.

Saved named Renko presets and browser drafts for Dhan and FYERS were archived and cleared in the current browser. Delta presets were excluded. A Restore last cleared presets button restores the browser archive without changing the runner. Server draft files were separately copied, verified, and removed: 5 Dhan and 13 FYERS. Durable runner state, configurations used by active trades, instrument registrations, journals, credentials and broker connections were preserved. Preset cleanup does not delete the stopped instrument registrations listed under Active & saved strategies.

After the user instructed no runner restarts, no further backend reload or runner lifecycle action was performed. FYERS was observed managing an open position during cleanup; runner IDs, running flags and active configurations were unchanged by file cleanup. Both saved-name lists were verified empty in the hosted UI.

Optional continuation backend is rebased and tested in private staging but remains unloaded. Its control stays unavailable pending a permitted backend reload. Do not report that activation complete. The separate canonical per-instrument persistence redesign and detailed admin broker-debug wiring remain outside this rollout and unfinished.
