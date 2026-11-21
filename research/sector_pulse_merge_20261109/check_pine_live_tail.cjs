const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function verify(bundle) {
  const scope = vm.createContext({console, structuredClone, setTimeout, clearTimeout});
  vm.runInContext(fs.readFileSync(bundle, 'utf8'), scope);
  const start = Date.UTC(2026, 9, 23);
  const candle = (index, close, volume) => ({
    openTime: start + index * 300000, closeTime: start + (index + 1) * 300000,
    open: close, high: close, low: close, close, volume
  });
  const original = [candle(0, 10, 1), candle(1, 20, 2), candle(2, 30, 3)];
  let rows = original;
  const provider = {
    configure() {},
    async getSymbolInfo() { return {tickerid:'PAXGUSD', timezone:'UTC'}; },
    async getMarketData(_symbol, _interval, limit, from, to) {
      return rows.filter(row => (from == null || row.openTime >= from) &&
        (to == null || row.openTime <= to)).slice(-(limit || rows.length));
    }
  };
  const source = `//@version=6
indicator("Live tail verification")
var float running = 0
running += close * volume
plot(running, "weighted close")
plot(ta.sma(close, 2), "mean")
`;
  const runtime = new scope.PineTS(provider, 'PAXGUSD', '5', 100);
  const result = await runtime.run(source);
  const last = (ctx, title) => ctx.plots[title].data.at(-1).value;
  assert.equal(last(result, 'weighted close'), 140);
  rows = [...original.slice(0, 2), candle(2, 40, 4)];
  assert.equal(await runtime.updateTail(result), true);
  assert.equal(last(result, 'weighted close'), 210);
  assert.equal(last(result, 'mean'), 30);

  rows = [...original.slice(0, 2), candle(2, 50, 5), candle(3, 60, 6)];
  assert.equal(await runtime.updateTail(result), true);
  const replay = await new scope.PineTS(provider, 'PAXGUSD', '5', 100).run(source);
  for (const name of ['weighted close', 'mean']) {
    assert.equal(last(result, name), last(replay, name), name + ' disagrees with clean replay');
  }
  console.log('Verified forming candle revision and revised candle followed by append');
}
verify(process.argv[2]).catch(error => { console.error(error); process.exitCode = 1; });
