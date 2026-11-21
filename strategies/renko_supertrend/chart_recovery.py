"""Recover display calculations only; execution history remains strictly guarded."""
from .runner import analysis, HistoryRevision

def analyze_chart(candles, config, tick, saved=None, retain=5000):
    try:
        return analysis(candles, config, tick, saved=saved, retain=retain), None
    except HistoryRevision as error:
        if not saved or not candles or candles[0]['timestamp'] != saved['anchor']:
            raise
        rebuilt=analysis(candles, config, tick, retain=retain)
        if rebuilt['anchor'] != saved['anchor']:
            raise ValueError('Chart recovery must preserve the original history anchor') from error
        return rebuilt, dict(scope='DISPLAY_ONLY', action='SAME_ANCHOR_REBUILD',
                             anchor=rebuilt['anchor'], reason=str(error))
