# AI Renko instrument runners

Each registered user/broker account can configure and start separate AI Renko
workers for different instruments. The application default capacity is four
active/preparing workers per account (Paper and Live combined). This is an
application guard, not a claim about broker connection limits or server capacity.
Operators may configure AI_RENKO_MAX_RUNNERS_PER_ACCOUNT from 1 through 16.
Broker authentication, rate/stream limits, executable quotes, product permission,
native sizing and capital checks remain mandatory; a stream limit can prevent
another worker becoming ready.

Select the broker account first, then an instrument. Its saved user/account/
instrument settings are restored. Start that instrument explicitly. Select
another instrument to configure its own runner without moving the first one.
“Instrument runners” lists saved instruments with mode and state. Select a row
before using its Start, Stop or Detach controls. Switching timeframes/views within
the same active instrument retains the existing acknowledged reconfiguration
workflow. Changing the instrument of a scoped active worker is rejected; select
the other runner instead.

New/unset FYERS products default to Intraday. Saved explicit products and active
captured configurations are preserved. New cash-equity selections default to
Direct stock with quantity in shares; stock-options selections default to bought
options. Saved explicit per-instrument route choices remain valid. Direct mode
does not send an option-expiry selection. Users must supply their own quantity;
defaults never start a worker.

## State and ownership

- Runner scope is a deterministic hash of the exact selected broker instrument,
  under its registered private account. A route cannot create another owner for
  the same selected instrument. Paper and Live share that instrument's exclusive
  process/execution lock, preventing accidental simultaneous modes.
- Existing account-wide worker configurations retain their original ledger and
  native intent paths. No migration or takeover of a running worker occurs.
  A legacy running worker or unresolved legacy ledger blocks scoped startup.
  The user can finish/stop it through its existing controls, then start scoped
  workers. Historical journals, retained orders and broker holdings are preserved.
- New ledgers live below runtime/instruments/<account>/<scope>/<authenticated key>.
  No browser-supplied filesystem path or ledger key is accepted. Native Delta
  caches are also separated. Settings and signal/history output stay per run.
- Start/recovery selects the exact account and instrument. Preparing claims and
  actual process identity checks survive concurrent requests; a second same-
  instrument worker is rejected. Executor file locks provide a second boundary.
- Before an entry, account coordination checks all relevant registered AI ledgers,
  including detached holdings, partial exits and retiring option legs. The actual
  traded contract is compared, not only the signal underlying. Unknown ownership
  conservatively blocks account entry. Known independent native intents are
  exempted only after exact durable tag, contract, quantity, side and product
  comparison. Manual/unattributed/ambiguous intents remain blocked.
- Entries share cross-process account admission through acknowledgement and durable
  save. Exits bypass this coordination lock so another instrument's entry wait
  cannot delay its exit. Existing native/account/broker exit validation remains.
- When other managed instrument exposure exists, fresh selected-account funds
  must cover its conservative full-value reserves plus the proposed order.
  This can be stricter than leveraged broker margin. Unknown price, multiplier,
  reserve or collateral currency blocks entry. Uncertain submissions keep their
  captured reservation; they are not resubmitted. Native margin checks still run.
  This is not a portfolio stop-loss/daily-loss service or a fill guarantee.
- Stop/Detach requests retain exact account/run/runtime-session proofs and operate
  only on that runner's owned legs. They do not clear another runner's intent or
  square off unrelated broker holdings. Chart markers, current-run P&L and the
  instrument-filtered journal stay bound to the selected runner.

## Verification boundaries

Offline tests cover concurrent executors, two recovered active identities,
duplicate traded-contract rejection, partial/unknown/retained legs, account
isolation, process-level entry serialization, funding reserves, non-blocking exit
coordination, preparing capacity, exact native intent exceptions, selected Stop/
Detach, journal filtering, saved-product precedence and cash-equity routing.
No order or live runner is created for verification. Real simultaneous live fills
and active-position displays require user-started runs and remain distinct from
offline/read-only checks. Dashboard code is loaded only through guarded deployment;
source copying alone is not backend activation.
