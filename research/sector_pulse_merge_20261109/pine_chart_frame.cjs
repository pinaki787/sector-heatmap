const drawings = ['lines', 'boxes', 'labels', 'linefills', 'polylines', 'tables'];

function displayMask(display) {
  if (display == null || display === 'all') return 15;
  let mask = 0;
  for (const [part, bit] of [['pane', 1], ['price_scale', 2], ['data_window', 4], ['status_line', 8]]) {
    if (typeof display === 'string' && display.includes(part)) mask |= bit;
  }
  return mask;
}

function chartFrame({candles, plots}) {
  const bars = candles.map(({openTime, closeTime, ...ohlcv}) => ({
    ...ohlcv, time: openTime / 1000, closeTime: closeTime / 1000
  }));
  const chartPlots = Object.entries(plots).filter(([name]) => !name.startsWith('__'))
    .map(([id, plot]) => ({
      id,
      title: plot.title,
      options: plot.options,
      display: displayMask(plot.options?.display),
      points: plot.data.flatMap(point => {
        if (!Number.isFinite(point.time)) return [];
        const position = {time: point.time / 1000};
        const color = point.options?.color;
        if (!Number.isFinite(point.value) && plot.options?.style !== 'fill') return [position];
        return [{...position, value: point.value, ...(typeof color === 'string' && {color})}];
      })
    }));
  const objects = Object.fromEntries(drawings.map(kind => {
    const values = plots['__' + kind + '__']?.data.at(-1)?.value ?? [];
    return [kind, values.filter(object => !object._deleted).map(object => {
      if (object.xloc === 'bi') return {...object, xloc: 'bar_index'};
      if (object.xloc !== 'bt') return {...object};
      const drawing = {...object, xloc: 'bar_time'};
      for (const coordinate of ['x', 'x1', 'x2', 'left', 'right']) {
        if (Number.isFinite(drawing[coordinate])) drawing[coordinate] /= 1000;
      }
      return drawing;
    })];
  }));
  return {bars, plots: chartPlots, objects};
}

module.exports = {chartFrame, displayMask};
