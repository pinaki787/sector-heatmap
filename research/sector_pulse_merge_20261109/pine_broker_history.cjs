function brokerHistory({symbol, chartQuery, requestChartHistory, candleEnd, signal, mergeLiveCandles}) {
  const histories = new Map();
  const live = new Map();
  async function load({ticker, interval, start, end, limit}) {
    signal.throwIfAborted();
    if (ticker !== symbol) throw new Error('No selected broker mapping for Pine symbol ' + ticker);
    const resolution = String(interval).replace(/^([DWM])$/, '1$1');
    if (!histories.has(resolution)) {
      const path = '/api/chart-workspace/history?' + chartQuery({interval: resolution}, symbol);
      const pending = requestChartHistory(path, signal).then(reply => {
        signal.throwIfAborted();
        if (reply.symbol !== symbol) throw new Error('Broker history returned a different instrument');
        if (!Array.isArray(reply.rows)) throw new Error('Broker history returned invalid candles');
        return reply.rows.map(([time, open, high, low, close, volume]) =>
          ({time, open, high, low, close, volume}));
      }).catch(error => {
        histories.delete(resolution);
        throw error;
      });
      histories.set(resolution, pending);
    }
    const confirmed = await histories.get(resolution);
    signal.throwIfAborted();
    const update = live.get(resolution);
    const bars = update ? mergeLiveCandles(confirmed, update.previous, update.rows) : confirmed;
    return bars.map(({time, ...candle}) => ({
      ...candle, openTime: time * 1000, closeTime: candleEnd(time, resolution) * 1000
    })).filter(bar =>
      (start == null || bar.openTime >= start) && (end == null || bar.openTime <= end)
    ).slice(-(limit || 5000));
  }
  load.update = ({symbol: instrument, interval, rows, historyChanged, replaceProvisional}) => {
    signal.throwIfAborted();
    if (instrument !== symbol) throw new Error('Broker update returned a different instrument');
    const resolution = String(interval).replace(/^([DWM])$/, '1$1');
    const previous = live.get(resolution);
    const retained = replaceProvisional || !previous ? []
      : mergeLiveCandles([], previous.previous, previous.rows);
    live.set(resolution, {previous: retained, rows});
    if (historyChanged) histories.delete(resolution);
  };
  return load;
}

module.exports = {brokerHistory};
