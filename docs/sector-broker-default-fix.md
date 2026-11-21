# Sector data default and connection display — 20 October 2026

Cause: Sector Rotation intentionally required an explicit data-account choice inside a Delta workspace. The sidebar followed the active form's empty selection and incorrectly displayed an account-configuration prompt, although owned accounts were discoverable and configured. Reloading exposed this UI state; broker credentials were not lost.

Fix: an unset sector data selector defaults to an eligible FYERS account. Existing valid explicit choices remain unchanged. Dhan and Motilal stay selectable; Delta stays absent from sector choices. Execution forms and workspace ownership do not change. The sidebar reports the authenticated workspace account independently of the sector data account and can resolve context before form routing finishes. Its script initializes after form assets.

Deployment: authoritative root and the administrator's four isolated static source snapshots updated with cache-version changes. No backend process or service reload required or performed for this UI fix. Protected originals are in .private/sector-broker-default-backups.

Verification: 41 Node tests pass, including mounted selector/sidebar tests, private routing, stale-response rejection, saved choices and cross-account constraints. Hosted fresh Delta page defaulted to FYERS; sidebar confirmed Delta India connected. Dhan and Motilal selection updated only sectorAccount while retaining the Delta workspace. Verification tab restored to FYERS.

Separate read-only attachment finding: FYERS broker inventory returned one open MARGIN call, MCX:CRUDEOILM26NOV9650CE, quantity 1, eligible=false, reason 'Already managed by a dashboard strategy.' The corresponding Live manager remained running with a fresh state update. No attachment, takeover, stop, order or management change was performed. No conclusion is drawn about a different, unidentified position.
