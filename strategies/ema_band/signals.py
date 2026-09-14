"""Paper-first translation of the uploaded EMA High/Low Band Pine rules."""
from dataclasses import dataclass

@dataclass
class Signal:
    side: str | None
    exit: bool = False

def ema(values, length):
    alpha = 2 / (length + 1); result = []
    for value in values:
        result.append(value if not result else alpha * value + (1 - alpha) * result[-1])
    return result

def evaluate(bars, position=0):
    """Completed-bar-only signal. Caller fills an entry at the following bar open."""
    if len(bars) < 202: return Signal(None)
    highs, lows, closes, opens = ([float(b[k]) for b in bars] for k in ('high','low','close','open'))
    high_band, low_band = ema(highs, 21), ema(lows, 21)
    i = len(bars)-1; prior = i-1
    if position > 0 and low_band[i] <= closes[i] <= high_band[i]: return Signal(None, True)
    if position < 0 and low_band[i] <= closes[i] <= high_band[i]: return Signal(None, True)
    midpoint = (highs[prior] + lows[prior]) / 2
    long = opens[prior] <= high_band[prior] and closes[prior] > high_band[prior] and closes[i] > midpoint
    short = opens[prior] >= low_band[prior] and closes[prior] < low_band[prior] and closes[i] < midpoint
    return Signal('BUY' if position == 0 and long else 'SELL' if position == 0 and short else None)
