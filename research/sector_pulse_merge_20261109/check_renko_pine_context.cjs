const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function verify() {
  const bundle = fs.readFileSync('.private/chart-pine-worker.js', 'utf8');
  const start = 1700000100000;
  const candle = (index, close) => ({
    openTime: start + index * 300000, closeTime: start + (index + 1) * 300000,
    open: 100, high: 110, low: 95, close, volume: 1
  });
  const candles = [candle(0, 101), candle(1, 104), candle(2, 107)];
  const bricks = [candle(0, 102), candle(0, 103), candle(1, 105), candle(1, 106), candle(2, 108)];
  const requests = [];
  let result;
  const scope = {console, structuredClone, setTimeout, clearTimeout, postMessage(message) {
    if (message.type !== 'candles') {
      result = JSON.parse(JSON.stringify(message));
      return;
    }
    requests.push(message.ticker);
    const rows = message.ticker.endsWith(';renko') ? bricks : candles;
    void scope.onmessage({data: {type: 'candles-result', id: message.id, rows}});
  }};
  scope.self = scope;
  vm.runInNewContext(bundle, scope);
  const source = [
    '//@version=6',
    'indicator("Shared source candle")',
    'plot(bar_index, "Index")',
    'plot(chart.is_renko ? close : na, "Brick")',
    'plotshape(bar_index == 1, title="Second brick")',
    'plot(request.security(ticker.standard(syminfo.tickerid), "5", close), "Broker")'
  ].join('\n');
  await scope.onmessage({data: {source, timeframe: '5', chartType: 'Renko', count: bricks.length, symbolInfo: {
    tickerid: 'BTCUSD', ticker: 'BTCUSD', prefix: 'DELTAIN', timezone: 'UTC', session: '24x7', mintick: 0.5, type: 'crypto'
  }}});
  assert.equal(result?.ok, true, result?.error);
  assert.deepEqual(requests, ['BTCUSD;renko', 'BTCUSD']);
  const plot = title => Object.values(result.plots).find(entry => entry.title === title).data;
  assert.deepEqual(plot('Index').map(point => point.value), [0, 1, 2, 3, 4]);
  assert.deepEqual(plot('Brick').map(point => point.value), [102, 103, 105, 106, 108]);
  assert.deepEqual(plot('Broker').map(point => point.value), [101, 101, 104, 104, 107]);
  assert.equal(new Set(plot('Brick').map(point => point.time)).size, 3);
  assert.deepEqual(plot('Brick').map(point => point.barIndex), [0, 1, 2, 3, 4]);
  assert.equal(plot('Second brick').find(point => point.value === true)?.barIndex, 1);
  console.log('Verified five ordered bricks aligned with three separate broker candles.');
}

verify().catch(error => { console.error(error); process.exitCode = 1; });
