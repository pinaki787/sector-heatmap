"""Read-only full-anchor history; execution stays in the existing broker adapter."""
from datetime import datetime,timedelta
from pathlib import Path
from .signals import analysis,epoch,IST


def attach_history(adapter,path,client_reader):
    from strategies.renko_supertrend.chart_history import ChartHistory
    history=ChartHistory(Path(path));history.analyze=analysis
    def candles(config):
        start=datetime.fromtimestamp(epoch(config['engine_anchor_time']),IST).date()
        today=datetime.fromtimestamp(adapter.clock() if hasattr(adapter,'clock') else __import__('time').time(),IST).date()
        result,rows,forming,meta=history.load(client_reader(),config['underlying'],config['timeframe'],'custom',str(start),str(today),config,adapter.host_tick_size(config['underlying']))
        if not meta.get('data_quality',{}).get('analysis_available',True):raise ValueError('Invalid completed OHLC; Engine execution blocked')
        if meta.get('history_error'):raise ValueError('Engine history incomplete: '+meta['history_error'])
        # Preserve the initialization candles (EMA warmup) as well as display rows.
        source=result['rows']
        if not source:raise ValueError('No engine host history')
        adapter.observe(config,source+forming)
        return source+forming
    adapter.candles=candles
    return adapter
