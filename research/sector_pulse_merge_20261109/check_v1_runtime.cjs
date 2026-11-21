const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');

const bundle = process.argv[2];
if (!bundle) throw new Error('Pass a local PineTS browser bundle as the first argument.');
const source = fs.readFileSync('sector-pulse-v1.pine', 'utf8');
const archive = 'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json';
const rows = JSON.parse(fs.readFileSync(archive, 'utf8')).rows.slice(-18000);
const globals = {console, setTimeout, clearTimeout, structuredClone};
const isolatedGlobal = vm.constants?.DONT_CONTEXTIFY;
const runtime = isolatedGlobal === undefined
  ? vm.createContext(globals)
  : vm.createContext(isolatedGlobal);
if (isolatedGlobal !== undefined) Object.assign(runtime, globals);
runtime.self = runtime;

const loadStart = performance.now();
vm.runInContext(fs.readFileSync(bundle, 'utf8'), runtime);
const bundleLoadMs = performance.now() - loadStart;

const symbol = 'NSE:NIFTY50-INDEX';
const frames = new Map();
let fixtureProviderMs = 0;
function aggregate(interval) {
  const groups = new Map();
  for (const [time, open, high, low, close, volume] of rows) {
    const day = Math.floor((time + 19800) / 86400);
    const start = day * 86400 - 19800 + 33300;
    const end = start + 22500;
    if (time < start || time >= end) continue;
    const date = new Date(day * 86400000);
    const width = Number(interval) * 60;
    let key = start;
    if (interval === '1W') key -= ((day + 3) % 7) * 86400;
    else if (interval === '1M') key = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1) / 1000 - 19800 + 33300;
    else if (width) key += Math.floor((time - start) / width) * width;
    const closeTime = (width ? Math.min(end, key + width) : end) * 1000;
    const bar = groups.get(key);
    if (bar) {
      bar.high = Math.max(bar.high, high);
      bar.low = Math.min(bar.low, low);
      bar.close = close;
      bar.closeTime = closeTime;
      bar.volume += volume;
    } else groups.set(key, {openTime: key * 1000, closeTime, open, high, low, close, volume});
  }
  return [...groups.values()];
}

const provider = {
  configure() {},
  async getSymbolInfo() {
    return {tickerid: symbol, ticker: 'NIFTY50-INDEX', prefix: 'NSE', type: 'index',
      timezone: 'Asia/Kolkata', mintick: .05, session: '0915-1530', currency: 'INR'};
  },
  async getMarketData(ticker, timeframe, limit, start, end) {
    assert.ok([symbol, 'NIFTY50-INDEX'].includes(ticker), 'Unexpected instrument: ' + ticker);
    const interval = String(timeframe);
    assert.match(interval, /^(?:\d+|1[DWM])$/);
    const started = performance.now();
    if (!frames.has(interval)) frames.set(interval, aggregate(interval));
    const candles = frames.get(interval).filter(bar =>
      (start == null || bar.openTime >= start) && (end == null || bar.openTime <= end)).slice(-(limit || 5000));
    fixtureProviderMs += performance.now() - started;
    return candles;
  }
};

async function verifyRequestCollections() {
  const probe = `//@version=6
indicator("Request collection probe")
f() =>
    var array<int> records = array.new<int>()
    if barstate.islast
        array.push(records, 42)
    records
local = f()
remote = request.security(syminfo.tickerid, "5", f(), calc_bars_count=10000)
plot(array.size(local), "local size")
plot(na(remote) ? -1 : array.size(remote), "requested size")
plot(request.security(syminfo.tickerid, "5", barstate.islast ? 1 : 0, calc_bars_count=10000), "requested last bar")
`;
  const {plots} = await new runtime.PineTS(provider, symbol, '5', 400).run(probe);
  const last = name => plots[name].data.at(-1).value;
  assert.equal(last('local size'), 1, 'Local array must contain the probe value');
  assert.equal(last('requested last bar'), 1, 'The source request must reach its last bar');
  assert.equal(last('requested size'), 1, 'request.security must return the populated source array');
}

async function verify() {
  if (process.env.SECTOR_PULSE_CHECK_REQUEST_COLLECTIONS === '1') {
    await verifyRequestCollections();
    console.log('Verified collection return from request.security');
    return;
  }
  const runStart = performance.now();
  const {plots} = await new runtime.PineTS(provider, symbol, '5', 400).run(source);
  console.log('Offline timing', {
    node: process.version,
    vmContext: isolatedGlobal === undefined ? 'contextified' : 'isolated global',
    bundleLoadMs: Math.round(bundleLoadMs),
    evaluationMs: Math.round(performance.now() - runStart),
    fixtureProviderMs: Math.round(fixtureProviderMs)
  });
  const numeric = name => plots[name].data.filter(point => Number.isFinite(point.value));
  const objects = name => plots[name].data.at(-1).value.filter(object => !object._deleted);
  for (const name of ['LOCKED RED BAR HIGH', 'LOCKED RED BAR LOW', '44%', '50%', '56%',
    '200 SMA High — 2m', '200 SMA Low — 2m', 'AI Renko Supertrend', 'Shakti Midline']) {
    const points = numeric(name);
    assert.ok(points.length, name + ' returned no numeric values');
    console.log(name, points.length);
  }
  for (const name of ['__lines__', '__boxes__', '__labels__', '__tables__']) {
    const values = objects(name);
    assert.ok(values.length, name + ' returned no live objects');
    console.log(name, values.length);
  }
  const byTime = name => new Map(numeric(name).map(point => [point.time, point.value]));
  const highs = byTime('LOCKED RED BAR HIGH');
  const lows = byTime('LOCKED RED BAR LOW');
  for (const ratio of [44, 50, 56]) {
    const levels = numeric(ratio + '%');
    assert.equal(levels.length, highs.size);
    for (const {time, value} of levels) {
      const low = lows.get(time);
      const high = highs.get(time);
      assert.ok(high >= low && Math.abs(value - (low + (high - low) * ratio / 100)) < 1e-8,
        ratio + '% level disagrees with the source range at ' + new Date(time).toISOString());
    }
  }
  const captions = new Set(objects('__tables__').flatMap(table =>
    table.cells.flatMap(row => row.map(cell => cell?.text))));
  for (const text of ['SECTOR PULSE V1', 'Levels · IST', '44%', '50%', '56%', 'Latest red', 'RSI · closed']) {
    assert.ok(captions.has(text), 'Missing table caption: ' + text);
  }
  console.log('Verified Fibonacci values and both V1 table headers');
  const levelsTable = objects('__tables__').find(table => table.cells[0]?.[0]?.text === 'Levels · IST');
  const openingCell = levelsTable.cells.map(row => row[0]).find(cell => /^X /.test(cell?.text ?? ''));
  const fiveMinute = await provider.getMarketData(symbol, '5', 400);
  const lastDay = new Date(fiveMinute.at(-1).openTime + 19800000).toISOString().slice(0, 10);
  const expectedOpening = fiveMinute.find(bar =>
    new Date(bar.openTime + 19800000).toISOString().startsWith(lastDay + 'T09:15:'));
  assert.ok(expectedOpening, 'The archive must include the latest regular opening candle');
  const expectedLabel = 'X 09:15–09:20';
  const openingMatches = openingCell?.text === expectedLabel;
  console.log('X opening candle', {expectedLabel, actualLabel: openingCell?.text ?? null,
    expectedHigh: expectedOpening.high, expectedLow: expectedOpening.low, openingMatches});
  if (process.env.SECTOR_PULSE_REQUIRE_OPENING_PARITY === '1') {
    assert.ok(openingMatches, 'Opening candle mismatch: ' + (openingCell?.text ?? 'unavailable'));
  }

  if (process.env.SECTOR_PULSE_REQUIRE_V1_PARITY === '1') {
    const sessions = levelsTable.cells.map(row => row[0]);
    const currentDay = fiveMinute.filter(bar =>
      new Date(bar.openTime + 19800000).toISOString().slice(0, 10) === lastDay);
    const red = currentDay.find(bar => bar.openTime > expectedOpening.openTime && bar.close < bar.open);
    const midday = currentDay.filter(bar => {
      const clock = new Date(bar.openTime + 19800000).toISOString().slice(11, 16);
      return clock >= '12:30' && clock < '13:00';
    });
    const clockLabel = stamp => new Date(stamp + 19800000).toISOString().slice(11, 16);
    const checkRange = (caption, high, low) => {
      const cell = sessions.find(value => value?.text === caption);
      const match = cell?.tooltip?.match(/H ([\d.]+) · L ([\d.]+)/);
      assert.ok(match, 'Missing range: ' + caption);
      assert.equal(Number(match[1]), high, caption + ' high');
      assert.equal(Number(match[2]), low, caption + ' low');
    };
    assert.ok(red, 'Archive must contain a red candle after the opening candle');
    assert.equal(midday.length, 6, 'Archive must contain all six midday candles');
    checkRange(expectedLabel, expectedOpening.high, expectedOpening.low);
    checkRange('R ' + clockLabel(red.openTime) + '–' + clockLabel(red.closeTime), red.high, red.low);
    checkRange('M 12:30–13:00', Math.max(...midday.map(bar => bar.high)), Math.min(...midday.map(bar => bar.low)));
    for (const side of ['supply', 'demand']) {
      const high = numeric('nearest ' + side + ' high').at(-1);
      const low = numeric('nearest ' + side + ' low').at(-1);
      assert.ok(high && low && high.time === low.time && high.value > low.value, 'Missing ' + side + ' zone');
    }
    console.log('Verified X, R, M against FYERS OHLC and checked supply/demand output');
  }

  if (process.argv[3]) {
    const candles = await provider.getMarketData(symbol, '5', 400);
    fs.writeFileSync(process.argv[3], JSON.stringify({candles, plots}));
  }
  console.log('Supply/demand output counts', Object.fromEntries(
    Object.keys(plots).filter(name => name.startsWith('nearest ')).map(name => [name, numeric(name).length])));
  console.log('Broker intervals requested:', [...frames.keys()].join(', '));
  console.log('V1 source SHA-256:', crypto.createHash('sha256').update(source).digest('hex'));
}
verify().catch(error => { console.error(error.message); process.exitCode = 1; });
