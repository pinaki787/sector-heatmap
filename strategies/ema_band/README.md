# EMA Band (paper-first)

Faithful Pine translation: a long signal candle must cross EMA-21 High, then the immediately following completed candle must close above that signal candle's full-range midpoint. A short signal candle must cross EMA-21 Low, then the immediately following completed candle must close below its midpoint. Either confirmation may be bullish, bearish, or neutral. Exits occur on a completed close inside the band. Python evaluates completed candles; paper entries fill at the next bar open. Live execution is intentionally absent.

Indian intraday runner constraints: 09:15–15:30 IST data, no new entry after 15:15, square-off about 15:20, no overnight positions. Symbol selection must originate from the fresh FYERS cached master.
