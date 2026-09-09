"""Read-only 5-minute EMA Band backtest; expects FYERS-format OHLC candles."""
from signals import evaluate

def run(bars):
    position = 0; entry = None; trades = []
    for index in range(202, len(bars) - 1):
        signal = evaluate(bars[:index + 1], position)
        next_open = float(bars[index + 1]['open'])
        if signal.exit and position:
            trades.append({'side': position, 'entry': entry, 'exit': next_open, 'pnl': (next_open-entry)*position})
            position = 0; entry = None
        elif signal.side:
            position = 1 if signal.side == 'BUY' else -1; entry = next_open
    return trades
