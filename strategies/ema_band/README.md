# EMA Band (paper-first)

Faithful Pine translation: previous candle must cross the appropriate EMA-21 high/low edge; the following completed candle must confirm direction and open beyond the prior full-range midpoint. Exits occur on a completed close inside the band. Python evaluates completed candles; paper entries fill at the next bar open. Live execution is intentionally absent.

Indian intraday runner constraints: 09:15–15:30 IST data, no new entry after 15:15, square-off about 15:20, no overnight positions. Symbol selection must originate from the fresh FYERS cached master.
