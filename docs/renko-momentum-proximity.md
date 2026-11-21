# Split EMA proximity policy

Source implementation: split-proximity-momentum-v1. Current default: ON for all configured Renko Supertrend instruments and brokers; see the all-broker migration section.
Existing saved/armed configurations retain the original distance rule. Source installation does not activate a running Python worker or opt a saved run into this policy.

Enable EMA proximity at exactly 0.5 completed host ATR and choose Split entry distance. Intrabar entries must be OFF. Draft saving is separate from the next explicit Start. The UI blocks Start with this option until the worker advertises the matching capability.

Retest signals retain the 0.5 ATR cap. Non-retest entries require the first completed qualification of a new directional episode, Supertrend direction agreement, directional EMA alignment and widening, directional RSI slope, a directional candle body, and a close in the outer third of its range. A fresh-price preflight additionally requires continued price/EMA alignment, absolute distance from the live fast EMA no greater than 1.5 completed ATR, and directional advance beyond the signal close no greater than 0.25 completed ATR. Limits are inclusive. Neutral RSI, missing evidence, invalid OHLC, forming candles and a synthesized continuation/rearm do not receive this allowance.

A rejected event cannot become a later continuation entry in the same qualification episode; a new qualification or confirmed retest is required. Existing first-option-quote bounded retries on the same fresh unconsumed event are preserved. Existing exposure ownership, historical-replay prevention, stream freshness, pending intent, cutoff, quota, executable quote and exit protections remain in force. Manual override behavior remains separate. Entry distance does not block owned-position exits.

Trade snapshots capture entry path, actual distance, effective limit, signal close/time and fresh observation time. The chart distinguishes a qualified signal from a matching recorded execution block. Historical chart checks use completed prices; they cannot establish prospective fresh executable behavior.

Research status: the 1.5/0.25 values are candidates, not profitability claims. Compare the unchanged 0.5 baseline, simple 1.0 and 1.5 thresholds, and this split policy with chronological lifecycle replay, actual arming times and per-run quota. Evaluate losers admitted, winners missed, entry delay, MAE and drawdown. Actual contract quotes/spreads, slippage and fees are needed before inferring option profitability.


## All-broker default — 25 October 2026

User approved this profile for every Renko Supertrend instrument across FYERS, Dhan, Motilal Oswal and Delta India. New preview/Start requests default to the flexible ATR policy. Legacy saved drafts and named configurations are migrated once to all-broker-flexible-atr-v1: proximity ON, ATR basis, 0.5 baseline, momentum ON, completed-candle entries. Later explicit baseline opt-outs remain available. Family masters retain precedence. Already captured run configs, positions, pending intents and journals are never migrated or rearmed. Old workers cannot offer an unsupported momentum Start: the existing capability gate stays in place. Backend source installation, worker loading and a user Start remain separately verified facts.

The same normalized bounds apply in native underlying units to Indian indices/equities/commodities and Delta crypto; there is no cross-broker data substitution and no change to premium/collateral/quantity or order routes. Chart query projection carries the momentum selection, so an explicitly selected flexible ATR study follows the same completed-candle rule; prospective execution still requires fresh-price and executable-quote validation.
