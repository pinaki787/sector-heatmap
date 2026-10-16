# Dhan MCX execution specification evidence

Verified 2026-10-13. These are exchange contract point values; Dhan's API lot is one.
No FYERS instrument data or brokerage is used.

| Family | Rupees per quoted point per Dhan contract |
|---|---:|
| CRUDEOIL / CRUDEOILM | 100 / 10 |
| NATURALGAS / NATGASMINI | 1250 / 250 |
| GOLD / GOLDM | 100 / 10 |
| SILVER / SILVERM | 30 / 5 |
| COPPER / ZINC | 2500 / 5000 |
| MCXBULLDEX | 30 through October 2026; 15 from November 2026 contracts |

The symbol master remains authoritative for security ID, exact expiry date, API lot and tick.
A changed API lot convention is rejected rather than silently doubling valuation.
The strategy's signal host is the selected exact futures month. It does not roll automatically.
Options on commodity futures are associated with the first subsequent same-family futures
expiry. Gold monthly options can share the next bi-monthly futures host. BULLDEX options
reference the index, and must match the futures host expiry rather than a later month.
BULLDEX expires at 17:00; other families use their regular session.
Regular non-agricultural hours are 09:00–23:30 during US DST and 09:00–23:55 otherwise.
Entry protection and carry exits use the preceding open MCX session close less 30 minutes.
The published 2026 morning/evening holiday calendar is applied; unknown calendar years
fail closed until updated. Special Muhurat hours are not assumed.
Calendar: https://www.mcxindia.com/market-operations/trading-surveillance/trading-holidays

## Primary sources

- [Dhan master and API lot convention](https://dhanhq.co/docs/v2/instruments/)
- [Crude oil and mini specifications](https://www.mcxindia.com/products/energy/crude-oil)
- [Natural gas and mini specifications](https://www.mcxindia.com/products/energy/natural-gas)
- [Gold and mini specifications](https://www.mcxindia.com/products/bullion/gold)
- [Silver and mini specifications](https://www.mcxindia.com/products/bullion/silver)
- [Copper May 2026 specification](https://www.mcxindia.com/docs/default-source/about-us/copper-(2500-kilograms)-options-may-2026-contract-onwards.pdf)
- [Zinc May 2026 specification](https://www.mcxindia.com/docs/default-source/about-us/zinc-(5mt)-options-may-2026-contract-onwards.pdf)
- [BULLDEX current and November 2026 specifications](https://www.mcxindia.com/products/index/MCXBULLDEX)

## Estimated regular option charges

Dhan brokerage is Rs20 per executed order. MCX transaction fees are Rs41.80 per lakh of
premium turnover, SEBI Rs10 per crore, seller CTT 0.05%, buyer stamp 0.003%, and GST 18%
on brokerage, exchange and SEBI charges. This estimate excludes exercise/delivery and is
not a contract note. CTT is separate from STT; no equity IPFT is copied into MCX.

- [Dhan pricing](https://dhan.co/pricing/)
- [MCX circular 631/2024, official document mirrored by member](https://www.steelcitynettrade.com/Circulars/Revision%20in%20Transaction%20Fees%20on%20Futures%20and%20Options%20contracts.pdf)
- [MCXCCL CTT](https://www.mcxccl.com/clearing-settlement/commodities-transaction-tax)
- [MCXCCL SEBI and stamp rates](https://www.mcxccl.com/clearing-settlement/faq)
