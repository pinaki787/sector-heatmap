"""Delta completed-bar entries; exits continue to use cross_direction only."""
from strategies.ema_crossover.signals import rsi_sma_series
import math

def momentum_settings(payload):
    enabled=payload.get("momentum_enabled",False)
    if not isinstance(enabled,bool):raise ValueError("Momentum filter must be enabled or disabled.")
    return dict(momentum_enabled=enabled,momentum_lookback=1)

def momentum_evidence(row,prior):
    values=[row.get("close"),row.get("rsi_ma"),prior.get("rsi_ma"),prior.get("high"),prior.get("low")]
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in values):return None
    slope=row["rsi_ma"]-prior["rsi_ma"]
    return dict(lookback=1,previous_high=prior["high"],previous_low=prior["low"],rsi_ma_slope=slope,bullish=row["close"]>prior["high"] and slope>0,bearish=row["close"]<prior["low"] and slope<0,basis="Completed close beyond previous candle; RSI moving average slope over one candle")

def momentum_allows(cfg,row,direction):
    if not cfg.get("momentum_enabled"):return True
    evidence=row.get("momentum") or {}
    return evidence.get("bullish" if direction=="BULLISH" else "bearish" if direction=="BEARISH" else "invalid") is True



def delta_rsi_series(candles, rsi_length=14, ma_length=14, ma_type='SMA'):
    rows = rsi_sma_series(candles, rsi_length, ma_length, ma_type)
    gain = loss = 0.0
    alpha = 2 / (ma_length + 1)
    for i, row in enumerate(rows):
        row['entry_direction'] = row['cross_direction']
        row['entry_reason'] = 'CROSSOVER' if row['cross_direction'] else None
        row['touch_evidence'] = None
        row['momentum'] = momentum_evidence(row,rows[i-1]) if i else None
        if not i:
            continue
        prior = rows[i - 1]
        if ma_type == 'EMA' and i > rsi_length:
            extremes = {}
            for name in ('low', 'high'):
                delta = row[name] - prior['close']
                g = (gain * (rsi_length - 1) + max(delta, 0)) / rsi_length
                l = (loss * (rsi_length - 1) + max(-delta, 0)) / rsi_length
                rsi = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
                extremes[name] = (rsi, prior['rsi_ma'] + alpha * (rsi - prior['rsi_ma']))
            row['touch_evidence'] = dict(method='CANDLE_EXTREME_DERIVED',
                                         low_rsi=extremes['low'][0], low_ema=extremes['low'][1],
                                         high_rsi=extremes['high'][0], high_ema=extremes['high'][1])
            if not row['entry_direction']:
                if prior['rsi'] > prior['rsi_ma'] and row['rsi'] > row['rsi_ma'] and extremes['low'][0] <= extremes['low'][1]:
                    row['entry_direction'] = 'BULLISH'
                elif prior['rsi'] < prior['rsi_ma'] and row['rsi'] < row['rsi_ma'] and extremes['high'][0] >= extremes['high'][1]:
                    row['entry_direction'] = 'BEARISH'
                if row['entry_direction']:
                    row['entry_reason'] = 'CANDLE_EXTREME_EMA_TOUCH'
        delta = row['close'] - prior['close']
        if i <= rsi_length:
            gain += max(delta, 0) / rsi_length
            loss += max(-delta, 0) / rsi_length
        else:
            gain = (gain * (rsi_length - 1) + max(delta, 0)) / rsi_length
            loss = (loss * (rsi_length - 1) + max(-delta, 0)) / rsi_length
    return rows
