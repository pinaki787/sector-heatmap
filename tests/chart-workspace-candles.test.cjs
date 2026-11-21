const assert = require('node:assert/strict');
const test = require('node:test');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
require('../chart-workspace-studies.js');

const { indicators, mergeLiveCandles, renko } = globalThis.SectorPulseChartStudies;

test('AI Renko Supertrend Pine library matches the standalone script', () => {
  const standalone = readFileSync(resolve(__dirname, '../ai-renko-supertrend.pine'), 'utf8');
  const workspace = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const embedded = workspace.match(/function aiRenkoPineSource\(\)\s*\{\s*return ("(?:[^"\\]|\\.)*")/);
  assert.ok(embedded, 'Find the AI Renko library source in the chart editor');
  const normalize = source => source.replace(/\r\n/g, '\n').trimEnd();
  assert.equal(normalize(JSON.parse(embedded[1])), normalize(standalone));
});

test('Volume average preserves genuine zeros and skips incomplete windows', () => {
  const bars = [6, 0, 3, undefined, 9, 12, 15].map(volume => ({volume}));
  assert.deepEqual(indicators.Volume.run(bars), [[6, 0, 3, null, 9, 12, 15]]);
  const [volume, average] = indicators.Volume.run(bars, [], undefined, undefined,
    {showAverage: true, averageLength: 3});
  assert.deepEqual(volume, [6, 0, 3, null, 9, 12, 15]);
  assert.deepEqual(average, [null, null, 3, null, null, null, 12]);
});

test('Volume Delta tracks intrabar polarity, running extremes, and replay cutoff', () => {
  const intrabars = [
    {time: 0, open: 10, close: 11, volume: 5},
    {time: 1, open: 11, close: 11, volume: 2},
    {time: 2, open: 11, close: 10, volume: 9},
    {time: 3, open: 10, close: 10, volume: 4},
    {time: 4, open: 10, close: 10, volume: 1},
    {time: 5, open: 10, close: 12, volume: 3},
    {time: 6, open: 12, close: 13, volume: 100}
  ];
  const [delta] = indicators.VolumeDelta.run([{time: 0}, {time: 3}, {time: 6}], intrabars,
    bar => bar.time + 3, bar => bar.time + 1, 6);
  assert.deepEqual(delta.candles, [
    {open: 0, high: 7, low: -2, close: -2},
    {open: 0, high: 0, low: -5, close: -2},
    null
  ]);
  const [incomplete] = indicators.VolumeDelta.run([{time: 0}], intrabars.slice(1),
    () => 3, bar => bar.time + 1);
  assert.deepEqual(incomplete.candles, [null]);
});

test('Volume Delta accepts only a fresh, contiguous forming intrabar in the current chart candle', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function formingVolumeDeltaIntrabar(');
  const end = source.indexOf('  function cumulativeDeltaAnchor(', start);
  assert.ok(start >= 0 && end > start);
  const active = new Function(source.slice(start, end) + 'return formingVolumeDeltaIntrabar;')();
  const host = {time: 300, provisional: true};
  const forming = {time: 420, volume: 100};
  const closeHost = bar => bar.time + 300;
  const closeIntrabar = bar => bar.time + 60;
  assert.equal(active(host, forming, {time: 360}, closeHost, closeIntrabar, 450), forming);
  assert.equal(active(host, forming, {time: 300}, closeHost, closeIntrabar, 450), undefined);
  assert.equal(active(host, forming, {time: 360}, closeHost, closeIntrabar, 480), undefined);
  assert.equal(active({...host, provisional: false}, forming, {time: 360}, closeHost, closeIntrabar, 450), undefined);
});

test('Older delta history shares the selected intrabar request and redraws only the active chart', async () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  async function loadOlderVolumeDeltaHistory(');
  const end = source.indexOf('  async function fetchOlderHistory(', start);
  assert.ok(start >= 0 && end > start);
  const run = new Function('activeRequest', `
    const scope = new AbortController().signal;
    const calls = [];
    let redraws = 0;
    const generation = activeRequest, panel = {open: true}, barReplay = false;
    const settings = {interval: '30', studies: [{kind: 'VolumeDelta'}, {kind: 'CumulativeVolumeDelta'}, {kind: 'SMA'}]};
    const indicators = {VolumeDelta: {deltaCandles: true}, CumulativeVolumeDelta: {deltaCandles: true}};
    const olderHistory = new Set(['5']);
    const studyVisible = () => true;
    const volumeDeltaInterval = () => '5';
    const usesTickDelta = () => false;
    const loadReferencedHistoryThrough = async (interval, target) => { calls.push([interval, target]); return true; };
    const redrawKeepingViewport = () => { redraws++; };
    ${source.slice(start, end)}
    return loadOlderVolumeDeltaHistory(420, '30', 1, scope).then(() => ({calls, redraws}));
  `);
  assert.deepEqual(await run(1), {calls: [['5', 420000]], redraws: 1});
  assert.equal((await run(2)).redraws, 0);
});

test('Tick delta combines ordered trade extremes and requires continuous capture coverage', () => {
  const bars = [{time: 0}, {time: 10}, {time: 20, provisional: true}];
  const segments = [{from: 10, through: 24, active: true,
    rows: [[10, 0, 5, -2, 4], [11, 0, 2, -7, -6], [20, 0, 3, -1, 2]]}];
  const [delta] = globalThis.SectorPulseChartStudies.tradeDeltaPlots(bars, segments, bar => bar.time + 10);
  assert.deepEqual(delta.candles, [null, {open: 0, high: 6, low: -3, close: -2},
    {open: 0, high: 3, low: -1, close: 2}]);
  segments[0].active = false;
  const [offline] = globalThis.SectorPulseChartStudies.tradeDeltaPlots(bars, segments, bar => bar.time + 10);
  assert.equal(offline.candles.at(-1), null);
});

test('Cumulative Volume Delta carries OHLC forward, blocks incomplete periods and resets at the anchor', () => {
  const bars = Array.from({length: 6}, (_, time) => ({time, open: 10, close: time === 1 ? 9 : 11,
    volume: [5, 3, undefined, 9, 7, 3][time]}));
  const [delta] = indicators.CumulativeVolumeDelta.run(bars, bars, bar => bar.time + 1,
    bar => bar.time + 1, Infinity, bar => Math.floor(bar.time / 4));
  assert.deepEqual(delta.candles, [
    {open: 0, high: 5, low: 0, close: 5},
    {open: 5, high: 5, low: 2, close: 2},
    null,
    null,
    {open: 0, high: 7, low: 0, close: 7},
    {open: 7, high: 10, low: 7, close: 10}
  ]);
});

test('Relative Volume uses completed prior bars and preserves zeros and missing volume', () => {
  const bars = [10, 20, 0, 20, undefined, 25, 25, 50].map(volume => ({volume}));
  const [plot] = indicators.RelativeVolume.run(bars, [], 2);
  assert.deepEqual(plot, [null, null, 0, 2, null, null, null, 2]);
  const [zeroBaseline] = indicators.RelativeVolume.run([{volume: 0}, {volume: 0}, {volume: 5}], [], 2);
  assert.equal(zeroBaseline.at(-1), null);
});

test('Technical Ratings distinguishes neutral, weak and strong ratings at exact boundaries', () => {
  const indicator = indicators.TechnicalRatings;
  assert.deepEqual([null, -0.51, -0.5, -0.1, 0, 0.1, 0.5, 0.51].map(indicator.ratingCategory),
    [null, -2, -1, 0, 0, 0, 1, 2]);
  const bars = Array.from({length: 250}, (_, i) => {
    const close = 500 - i;
    return {open: close, high: close + 1, low: close - 1, close};
  });
  const ratings = indicator.ratings(bars);
  assert.deepEqual(ratings[0], {All: 0, MAs: 0, Oscillators: 0});
  const {All, MAs, Oscillators} = ratings.at(-1);
  assert.equal(MAs, -13 / 14); // Linear HMA is neutral and missing VWMA is excluded.
  assert.equal(All, (MAs + Oscillators) / 2);
  assert.ok(ratings.every(rating => Object.values(rating).every(value => value >= -1 && value <= 1)));
});

test('Trend Strength Index correlates against bar order and leaves flat windows undefined', () => {
  const [plot] = indicators.TrendStrength.run([1, 2, 3, 2, 1, 1, 1].map(close => ({close})), [], 3);
  assert.deepEqual(plot.slice(0, 5), [null, null, 1, 0, -1]);
  assert.ok(Math.abs(plot[5] + Math.sqrt(3) / 2) < 1e-12);
  assert.equal(plot[6], null);
});

test('Standard Deviation uses the full rolling population and scales the plot', () => {
  const [values] = indicators.StandardDeviation.run([], [1, 2, 3, 4, 5, 5], 5, 1, {deviations: 2});
  assert.deepEqual(values.slice(0, 4), [null, null, null, null]);
  assert.equal(values[4], 2 * Math.sqrt(2));
  assert.ok(Math.abs(values[5] - 2 * Math.sqrt(1.36)) < 1e-12);
});

test('Klinger volume force resets on reversal and preserves bars with missing volume', () => {
  const bars = [[2, 10], [3, 10], [4, 12], [3, 8], [2, null], [3, 6]]
    .map(([close, volume]) => ({high: close + 1, low: close - 1, close, volume}));
  const [klinger, signal] = indicators.Klinger.run(bars);
  const forces = [-1000, -1600, 800, -600];
  const smoothed = (seed, value, period) => seed + (value - seed) * 2 / (period + 1);
  let fast = forces[0];
  let slow = forces[0];
  let trigger = 0;
  assert.equal(klinger[0], null);
  assert.equal(signal[0], null);
  assert.equal(klinger[4], null);
  assert.equal(signal[4], null);
  for (const [index, value] of forces.entries()) {
    const bar = [1, 2, 3, 5][index];
    fast = smoothed(fast, value, 34);
    slow = smoothed(slow, value, 55);
    trigger = smoothed(trigger, fast - slow, 13);
    assert.ok(Math.abs(klinger[bar] - (fast - slow)) < 1e-9);
    assert.ok(Math.abs(signal[bar] - trigger) < 1e-9);
  }
  const flat = Array.from({length: 3}, () => ({high: 1, low: 1, close: 1, volume: 10}));
  assert.deepEqual(indicators.Klinger.run(flat), [[null, 0, 0], [null, 0, 0]]);
});

test('broker confirmation replaces provisional OHLC and ignores a late socket update', () => {
  const first = { time: 300, open: 100, high: 104, low: 99, close: 103, volume: 10 };
  const confirmed = { time: 600, open: 103, high: 107, low: 102, close: 104, volume: 20 };
  const provisional = mergeLiveCandles([first], [], [[600, 103, 108, 101, 107, 12]]);
  assert.equal(provisional.at(-1).provisional, true);

  const nextTick = [900, 104, 109, 103, 106, 2];
  const merged = mergeLiveCandles([first, confirmed], provisional, [
    [600, 103, 110, 101, 109, 15],
    nextTick
  ]);

  assert.deepEqual(merged, [
    first,
    confirmed,
    { time: 900, open: 104, high: 109, low: 103, close: 106, volume: 2, provisional: true }
  ]);
});


test('Renko replaces broker projections at confirmation and ignores late updates to the same candle', () => {
  const previousBrick = { open: 52, close: 54 };
  const first = { time: 300, open: 54, high: 54, low: 54, close: 54, volume: 10 };
  const project = bars => renko(bars, 2, previousBrick).map(brick =>
    [brick.sourceTime, brick.open, brick.close, brick.provisional]);

  const forming = mergeLiveCandles([first], [], [[600, 54, 58, 54, 58, 20]]);
  assert.deepEqual(project(forming), [[600, 54, 56, true], [600, 56, 58, true]]);

  const confirmed = { time: 600, open: 54, high: 58, low: 54, close: 55, volume: 25 };
  const next = [900, 55, 55, 50, 50, 15];
  const rolled = mergeLiveCandles([first, confirmed], forming, [[600, 54, 59, 54, 59, 22], next]);
  assert.deepEqual(project(rolled), [[900, 52, 50, true]]);

  const finished = { time: 900, open: 55, high: 55, low: 50, close: 50, volume: 20 };
  const reconciled = mergeLiveCandles([first, confirmed, finished], rolled, [[900, 55, 55, 46, 46, 17]]);
  assert.deepEqual(project(reconciled), [[900, 52, 50, false]]);
});


test('a retreating socket candle removes close-based Renko projections before confirmation', () => {
  const previousBrick = { open: 52, close: 54 };
  const base = [{ time: 300, open: 54, high: 54, low: 54, close: 54, volume: 10 }];
  const firstTick = mergeLiveCandles(base, [], [[600, 54, 58, 54, 58, 20]]);
  assert.deepEqual(renko(firstTick, 2, previousBrick).map(brick => brick.close), [56, 58]);

  // The recorded high is still 58, but the latest price no longer creates a brick.
  const retreat = mergeLiveCandles(base, firstTick, [[600, 54, 58, 54, 55, 24]]);
  assert.equal(retreat.at(-1).provisional, true);
  assert.deepEqual(renko(retreat, 2, previousBrick), []);

  const reversal = mergeLiveCandles(base, retreat, [[600, 54, 58, 50, 50, 30]]);
  assert.deepEqual(renko(reversal, 2, previousBrick).map(brick =>
    [brick.time, brick.sourceTime, brick.open, brick.close, brick.provisional]),
  [[1, 600, 52, 50, true]]);
});

test('Renko drawing anchors survive history prepends and reject disappearing projections', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('    const firstBrickBySource = new Map();');
  const end = source.indexOf("    const main = document.createElement('div');", start);
  assert.ok(start >= 0 && end > start);
  const resolve = new Function('bars', 'isRenko', 'anchor', `
    const byTime = new Map(bars.map(bar => [bar.time, bar]));
    const indexes = new Map(bars.map((bar, index) => [bar.time, index]));
    ${source.slice(start, end)}
    return drawingBrick(anchor);
  `);
  const sourceTime = 600;
  const first = {time: 80, sourceTime, open: 100, close: 102};
  const second = {time: 81, sourceTime, open: 102, close: 104};
  const projected = {time: 82, sourceTime, open: 104, close: 106, provisional: true};
  const anchor = (bar, brickOffset) => ({time: bar.sourceTime, brickOffset, brickOpen: bar.open, brickClose: bar.close});
  assert.equal(resolve([first, second, projected], true, anchor(first, 0)), first);
  assert.equal(resolve([first, second, projected], true, anchor(second, 1)), second);
  const history = [{time: 100, sourceTime: 300, open: 96, close: 98},
    ...[first, second].map(bar => ({...bar, time: bar.time + 21}))];
  assert.equal(resolve(history, true, anchor(second, 1)), history[2]);
  assert.equal(resolve(history, true, anchor(projected, 2)), undefined);
  assert.equal(resolve(history, true, {time: sourceTime, price: 103}), undefined);
  assert.equal(resolve(history, false, anchor(second, 1)), undefined);
  const repeated = [first, second, {...first, time: 82}, {...second, time: 83}];
  assert.equal(resolve(repeated, true, anchor(second, 2)), repeated[1]);
  assert.equal(resolve(repeated, true, anchor(second, 4)), repeated[3]);
});

test('Fisher Transform saturates strong trends and delays its trigger by one bar', () => {
  const length = indicators.Fisher.length;
  const rising = Array.from({length: 100}, (_, index) => ({high: index + 2, low: index + 1}));
  const [fisher, trigger] = indicators.Fisher.run(rising, [], length);
  assert.ok(fisher.slice(0, length - 1).every(value => value === null));
  assert.ok(Math.abs(fisher[length - 1] - Math.atanh(0.33)) < 1e-12);
  assert.ok(Math.abs(fisher.at(-1) - Math.log(1999)) < 1e-10);
  assert.deepEqual(trigger.slice(1), fisher.slice(0, -1));

  const flat = rising.map(() => ({high: 20, low: 20}));
  const [neutral] = indicators.Fisher.run(flat, [], length);
  assert.ok(neutral.slice(length - 1).every(value => value === 0));
});


test('FYERS exact cash lookup preserves the general catalog when its first page omits the equity', async () => {
  const {readFileSync} = require('node:fs');
  const vm = require('node:vm');
  const source = readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const body = source.match(/^  async function loadBrokerSymbolResults\([\s\S]*?^  }/m)?.[0];
  assert.ok(body);
  const resolution = {};
  const calls = [];
  const pageButtons = [];
  const element = () => ({
    dataset: {}, children: [],
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); },
    setAttribute() {}
  });
  const results = element(), status = element(), pages = element();
  const fields = new Map([
    ['[data-chart-symbol-results]', results], ['[data-chart-symbol-count]', status],
    ['[data-chart-symbol-pages]', pages], ['input', {value: 'RELIANCE'}],
    ['[data-chart-fyers-segment]', {value: ''}]
  ]);
  const picker = {open: true, querySelector: selector => fields.get(selector), querySelectorAll: () => []};
  const option = {id: 'BSE:RELIANCE26NOV1200CE', symbol: 'RELIANCE option'};
  const exact = {id: 'NSE:RELIANCE-EQ', symbol: 'RELIANCE', description: 'RELIANCE INDUSTRIES LTD'};
  const context = {
    AbortSignal, URLSearchParams, broker: {name: 'FYERS'}, chartPrefix: '',
    fyersSymbolSelection: true, motilalSymbolSelection: false, dhanSymbolSelection: false,
    dhanSearchGeneration: 1, chartSymbol: () => 'NSE:NIFTY50-INDEX',
    document: {createElement: element}, validChartSymbol: () => true,
    matchMedia: () => ({matches: false}),
    addSymbolPageButton: (node, label) => pageButtons.push(label),
    fetch: async url => {
      const q = new URLSearchParams(url.split('?')[1]);
      calls.push([q.get('q'), q.get('segment')]);
      if (q.get('segment')) {
        if (resolution.pending) await resolution.pending;
        if (resolution.failed) throw new Error('Cash catalog timed out');
        return {ok: true, json: async () => ({symbols: [exact], total: 1})};
      }
      return {ok: true, json: async () => ({symbols: resolution.empty ? [] : [option], total: 200})};
    }
  };
  const remember = source.match(/^  function rememberMotilalPineInstrument\([\s\S]*?^  }/m)?.[0];
  assert.ok(remember);
  const load = vm.runInNewContext(remember + '\n' + body + '\nloadBrokerSymbolResults', context);
  const loadPage = offset => load(picker, offset, [], new AbortController(), context.dhanSearchGeneration);
  const visibleSymbols = () => results.children.map(row => row.dataset.chartSelectSymbol);

  await loadPage(0);
  assert.deepEqual(calls, [['RELIANCE', ''], ['NSE:RELIANCE-EQ', 'NSE_CM']]);
  assert.deepEqual(visibleSymbols(), [exact.id, option.id]);
  assert.match(status.textContent, /Exact NSE cash match/);
  assert.ok(pageButtons.includes('Next results'));

  resolution.failed = true;
  await loadPage(0);
  assert.deepEqual(visibleSymbols(), [option.id]);
  await loadPage(1);
  assert.deepEqual(calls.at(-1), ['RELIANCE', ''], 'later pages only request general results');

  resolution.failed = false;
  resolution.empty = true;
  await loadPage(0);
  assert.deepEqual(visibleSymbols(), [exact.id]);
  assert.match(status.textContent, /No other matching instruments/);

  let release;
  resolution.pending = new Promise(resolve => { release = resolve; });
  const superseded = loadPage(0);
  await new Promise(resolve => setImmediate(resolve));
  context.dhanSearchGeneration++;
  release();
  await superseded;
  assert.deepEqual(visibleSymbols(), [], 'a superseded lookup cannot repopulate search results');
});

test('alternate-symbol WebSocket snapshots remain isolated and expire at rollover', async () => {
  const {readFileSync} = require('node:fs');
  const vm = require('node:vm');
  const source = readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const extract = name => {
    const match = source.match(new RegExp('^  (?:async )?function ' + name + '\\([\\s\\S]*?^  }', 'm'));
    assert.ok(match, name);
    return match[0];
  };
  const scope = new AbortController().signal;
  const states = new Map(['AAA', 'BBB'].map(symbol => [symbol, {bars: [{time: 600}]}]));
  const calls = [];
  let now = 950;
  let updated = 0;
  let complete;
  const ctx = {
    Date: {now: () => now * 1000},
    requestScope: {signal: scope},
    pineLiveFrames: new Map(),
    chartQuery: ({interval}, symbol) => new URLSearchParams({interval, symbol}),
    brokerJson: async path => {
      const symbol = new URLSearchParams(path.split('?')[1]).get('symbol');
      calls.push(symbol);
      if (complete) await complete.promise;
      const close = symbol === 'AAA' ? 105 : 205;
      return {connected: true, latest_tick: now, rows: [[900, close, close, close, close]]};
    },
    broker: {},
    deltaSymbolSelection: false, fyersSymbolSelection: false, motilalSymbolSelection: false,
    symbolSelection: () => true,
    tradeInterval: () => false,
    calendarInterval: () => false,
    candleEnd: time => time + 300,
    alternateStudySymbol: study => study.symbol,
    studyVisible: () => true,
    calculationInterval: () => undefined,
    studySymbolHistory: symbol => states.get(symbol),
    settings: {studies: [{symbol: 'AAA'}, {symbol: 'AAA'}, {symbol: 'BBB'}]},
    generation: 1,
    panel: {open: true},
    barReplay: false,
    rows: [{time: 900, provisional: true}],
    pendingViewportRedraw: false,
    updateLastPrice: () => { updated++; return true; }
  };
  const refresh = vm.runInNewContext([
    extract('loadPineLiveFrame'), extract('chartTickTimestamp'),
    ...(source.includes('  function alternateStudyLiveCandle(')
      ? [extract('alternateStudyCandleEnd'), extract('alternateStudyLiveCandle'), extract('sameCandle')] : []),
    extract('refreshAlternateStudyBars'),
    'refreshAlternateStudyBars'
  ].join('\n'), ctx);

  await refresh(1, '5', scope);
  assert.deepEqual(calls, ['AAA', 'BBB']);
  assert.equal(states.get('AAA').live.close, 105);
  assert.equal(states.get('BBB').live.close, 205);
  assert.equal(updated, 1);
  await refresh(1, '5', scope);
  assert.equal(calls.length, 2, 'duplicate updates use the WebSocket snapshot cache');

  now = 1200;
  await refresh(1, '5', scope);
  assert.equal(states.get('AAA').live, undefined, 'expired forming candle is discarded');
  assert.equal(states.get('BBB').live, undefined);
  assert.equal(updated, 2);

  now = 1210;
  let release;
  complete = {promise: new Promise(resolve => { release = resolve; })};
  const pending = refresh(1, '5', scope);
  ctx.barReplay = true;
  release();
  await pending;
  assert.equal(updated, 2, 'an in-flight live snapshot does not redraw Bar Replay');
});

test('higher-timeframe studies recover from empty snapshots and discard stale or superseded candles', async () => {
  const { readFileSync } = require('node:fs');
  const vm = require('node:vm');
  const source = readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const extract = name => {
    const match = source.match(new RegExp('^  (?:async )?function ' + name + '\\([\\s\\S]*?^  }', 'm'));
    assert.ok(match, name);
    return match[0];
  };
  const scope = new AbortController().signal;
  const liveStudyBars = new Map();
  const history = new Map([['60', [{ time: 3600 }]]]);
  const rows = [{ time: 7500, provisional: true }];
  let now = 7800;
  let redraws = 0;
  let frame = null;
  const refresh = vm.runInNewContext([
    extract('sameCandle'),
    extract('chartTickTimestamp'),
    extract('deltaFormingFromNative'),
    extract('ratingTableUsesForming'),
    extract('refreshLiveStudyBars'),
    'refreshLiveStudyBars'
  ].join('\n'), {
    Date: { now: () => now * 1000 },
    deltaSymbolSelection: true,
    fyersSymbolSelection: false,
    calendarInterval: () => undefined,
    deltaBucketStart: () => 7200,
    intradayPrefixes: new Map([['60', {native_seconds: 300, intraday_prefix: [[7200, 101, 106, 99, 104, 20]]}]]),
    barReplay: false,
    settings: { studies: [{}] },
    indicators,
    calculationInterval: () => "60",
    studyVisible: () => true,
    studyUsesFormingBar: () => true,
    chartSymbol: () => 'TEST',
    loadPineLiveFrame: async () => frame,
    generation: 1,
    panel: { open: true },
    history,
    candleEnd: time => time + 3600,
    liveStudyBars,
    rows,
    pendingViewportRedraw: false,
    updateLastPrice: () => { redraws++; return true; }
  });

  await refresh(1, '5', scope);
  assert.equal(liveStudyBars.get('60').candle, undefined);
  assert.equal(redraws, 0);

  frame = { connected: true, latest_tick: now, rows: [[7200, 101, 106, 99, 104, 20], null] };
  await refresh(1, '5', scope);
  assert.equal(liveStudyBars.get('60').candle.close, 104);
  assert.equal(redraws, 1);
  await refresh(1, '5', scope);
  assert.equal(redraws, 1);

  frame = { connected: true, latest_tick: now, rows: [], native_row: [7800, 104, 108, 102, 107, 9] };
  await refresh(1, '5', scope);
  assert.equal(liveStudyBars.get('60').candle, undefined, 'rejects a missing native component');
  frame.native_row[0] = 7500;
  await refresh(1, '5', scope);
  assert.equal(liveStudyBars.get('60').candle.close, 107);
  assert.equal(liveStudyBars.get('60').candle.volume, 29);
  assert.equal(redraws, 3);

  now += 60;
  await refresh(1, '5', scope);
  assert.equal(liveStudyBars.get('60').candle, undefined);
  assert.equal(redraws, 4);

  frame.latest_tick = now;
  await refresh(1, '5', scope);
  assert.equal(liveStudyBars.get('60').candle.close, 107);
  history.get('60').push({ time: 7200 });
  await refresh(1, '5', scope);
  assert.equal(liveStudyBars.get('60').candle, undefined);
  assert.equal(redraws, 6);
});


test('reserved higher-timeframe legend readings respect visibility and tolerate removed studies', () => {
  const { readFileSync } = require('node:fs');
  const vm = require('node:vm');
  const source = readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const declarations = source.slice(source.indexOf('  function studyLegendValuesVisible('),
    source.indexOf('  function studyTimeframeLabel('));
  const study = {};
  const settings = { studies: [study] };
  const reserve = vm.runInNewContext(declarations + '\nreserveStudyLegendValue', {
    settings, studyVisible: item => !item.hidden
  });
  const output = {
    dataset: { studyValues: '0' },
    hasAttribute: name => name === 'data-fixed-study-value'
  };
  assert.equal(reserve(output), true);
  for (const [owner, flag] of [[settings, 'hideStudies'], [settings, 'hideStatusStudyValues'],
    [study, 'hideLegendValues'], [study, 'hidden']]) {
    owner[flag] = true;
    assert.equal(reserve(output), false, flag);
    owner[flag] = false;
  }
  settings.studies.pop();
  assert.equal(reserve(output), false);
});

test('FYERS intraday seed joins contiguous socket minutes without exposing partial volume', () => {
  const {readFileSync} = require('node:fs');
  const vm = require('node:vm');
  const source = readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const body = source.slice(source.indexOf('  function fyersFormingLiveBar('), source.indexOf('  function calendarLiveWithPrefix('));
  const seed = {bar:[3600,100,104,99,103,400],sampled_at:3700};
  const combine = vm.runInNewContext(body+'\nfyersFormingLiveBar', {
    fyersFormingSeeds:new Map([['30',seed]]), candleEnd:start=>start+1800
  });
  const frame = {connected:true,latest_tick:3723,fyers_intraday:{coverage_since:3680,
    minutes:[[3660,102,105,100,104,null],[3720,104,106,98,105,null]]}};
  assert.deepEqual(Array.from(combine('30',frame,3724)),[3600,100,106,98,105,null]);
  assert.equal(combine('30',frame,3783),undefined);
  frame.fyers_intraday.coverage_since = 3701;
  assert.equal(combine('30',frame,3724),undefined);
  frame.fyers_intraday.coverage_since = 3680;
  frame.fyers_intraday.minutes.shift();
  assert.equal(combine('30',frame,3724),undefined);
});

test('broker redraws coalesce during wheel zoom and restore the final viewport', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const section = (start, end) => {
    const first = source.indexOf(start);
    const last = source.indexOf(end, first);
    assert.ok(first >= 0 && last > first);
    return source.slice(first, last);
  };
  const viewportFunctions = section('  function chartGestureActive()', '  const studyIntervalGroups');
  const wheelListener = section("    stage.addEventListener('wheel'", '    const finishChartGesture');
  const run = new Function(`
    let chartWheelIdleTimer;
    let pendingViewportRedraw = false;
    let restoredViewAnchor;
    let range = {from: 3, to: 20};
    let candle = 1;
    let nextTimer = 0;
    const timers = new Map();
    const renders = [];
    const settings = {};
    const displayedBars = [{}];
    const activePaneResize = undefined;
    const activeChartPointers = new Set();
    const panel = {open: true, querySelector: () => null};
    const charts = [
      {chartElement: () => ({getClientRects: () => []}),
        timeScale: () => ({getVisibleLogicalRange: () => ({from: -1, to: 0})})},
      {chartElement: () => ({getClientRects: () => [{}]}),
        timeScale: () => ({getVisibleLogicalRange: () => range})}
    ];
    const viewportAnchor = ({from}) => from;
    const rememberManualPriceRange = () => {};
    const draw = () => renders.push({candle, range: settings.range, anchor: restoredViewAnchor});
    const setTimeout = callback => {
      timers.set(++nextTimer, callback);
      return nextTimer;
    };
    const clearTimeout = id => timers.delete(id);
    let wheel;
    const stage = {addEventListener: (_, listener) => { wheel = listener; }};
    ${viewportFunctions}
    ${wheelListener}
    return {
      renders, timers,
      wheel: target => wheel({deltaX: 0, deltaY: 10, target: {closest: () => target}}),
      correct: price => { candle = price; redrawKeepingViewport(); },
      zoom: next => { range = next; },
      settle: () => {
        for (const callback of timers.values()) callback();
        timers.clear();
      }
    };
  `);

  const chart = run();
  chart.wheel(null);
  assert.equal(chart.timers.size, 0);
  chart.wheel(true);
  chart.correct(104);
  const firstDeadline = [...chart.timers.keys()][0];
  chart.wheel(true);
  chart.correct(106);
  assert.equal(chart.timers.has(firstDeadline), false);
  assert.equal(chart.timers.size, 1);
  assert.deepEqual(chart.renders, []);

  const finalRange = {from: 7, to: 14};
  chart.zoom(finalRange);
  chart.settle();
  assert.deepEqual(chart.renders, [{candle: 106, range: finalRange, anchor: 7}]);
});

test('drawing previews use the saved trend and Fibonacci extensions', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const first = source.indexOf("                if (drawingTool === 'bars-pattern')", source.indexOf('const style = drawingStyleDefaults(drawingTool);'));
  const last = source.indexOf('                context.restore();', first);
  assert.ok(first >= 0 && last > first);
  const extensionGeometry = source.slice(source.indexOf('  const extendableTrendKinds ='),
    source.indexOf('  function arrowMarkerDimensions'));
  const preview = new Function('drawingTool', 'style', `
    ${extensionGeometry}
    const calls = [];
    const context = {
      globalAlpha: 1, save() {}, restore() {}, setLineDash() {},
      beginPath() {}, stroke() {}, fill() {},
      arc: (...point) => calls.push(['midpoint', ...point.slice(0, 3)]),
      moveTo: (...point) => calls.push(['from', ...point]),
      lineTo: (...point) => calls.push(['to', ...point])
    };
    const x = 20, y = 30, cursor = {x: 40, y: 50};
    const mediaSize = {width: 100, height: 80};
    const drawingStart = {price: y};
    const channelEnd = undefined;
    const mainSeries = {priceToCoordinate: value => value};
    const repeatingTimeDrawing = () => false;
    const isFibArcDrawing = () => false;
    const pitchforkKinds = [];
    const priceFib = kind => kind === 'fib';
    const positionDrawing = () => false;
    const retracementRatios = drawing => drawing.ratios;
    const fibLevelPrice = (_, ratio) => ratio * 100;
    const drawAnchoredShape = (_context, kind, ...points) =>
      calls.push([kind, ...points.slice(0, 4), ...(_context.globalAlpha !== 1 ? [_context.globalAlpha] : [])]);
    ${source.slice(first, last)}
    return calls;
  `);
  assert.deepEqual(preview('trend', {trendExtendLeft: true, trendExtendRight: true}),
    [['trend', 0, 10, 100, 110]]);
  assert.deepEqual(preview('extended-line', {}),
    [['trend', 0, 10, 100, 110]]);
  assert.deepEqual(preview('extended-line', {trendExtendLeft: false, trendExtendRight: false}),
    [['trend', 20, 30, 40, 50]]);
  assert.deepEqual(preview('trend', {trendLineOpacity: 30, trendMidpoint: true}),
    [['trend', 20, 30, 40, 50, 0.3], ['midpoint', 30, 40, 3]]);
  assert.deepEqual(preview('trend-angle', {trendExtendRight: true}),
    [['trend', 20, 30, 100, 110]]);
  const segment = new Function(extensionGeometry + '\nreturn trendLineSegment;')();
  assert.deepEqual(segment({kind: 'extended-line', trendExtendRight: false}, 35, 50, 35, 30,
    {width: 100, height: 80}), [35, 0, 35, 50]);
  assert.deepEqual(segment({kind: 'ray'}, 40, 50, 20, 30,
    {width: 100, height: 80}), [40, 50, 0, 10]);
  assert.deepEqual(segment({kind: 'ray'}, 35, 50, 35, 30,
    {width: 100, height: 80}), [35, 50, 35, 0]);
  assert.deepEqual(preview('fib', {extendFibLeft: true, extendFibRight: true, ratios: [0.5]}),
    [['from', 0, 50], ['to', 100, 50]]);
});

test('Command and Control temporarily enable strong magnet or bypass the active magnet', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const first = source.indexOf('    function drawingPrice(event)');
  const last = source.indexOf('    const anchorX', first);
  assert.ok(first >= 0 && last > first);
  const snap = new Function('settings', 'sourceEvent', 'y', `
    const mainSeries = {coordinateToPrice: y => y, priceToCoordinate: value => value};
    const byTime = new Map([[1, {open: 10, high: 20, low: 5, close: 15}]]);
    ${source.slice(first, last)}
    return drawingPrice({point: {y}, time: 1, sourceEvent});
  `);
  for (const modifier of [{metaKey: true}, {ctrlKey: true}]) {
    assert.equal(snap({magnet: false, magnetStrength: 'weak'}, modifier, 100), 20);
    assert.equal(snap({magnet: true, magnetStrength: 'strong'}, modifier, 100), 100);
  }
  assert.equal(snap({magnet: true, magnetStrength: 'weak'}, {}, 100), 100);
  assert.equal(snap({magnet: true, magnetStrength: 'weak'}, {}, 22), 20);
});

test('a stationary drawing preview recalculates on modifier press and release', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const first = source.indexOf('      let previewModifiers;');
  const last = source.indexOf('        const projected =', first);
  assert.ok(first >= 0 && last > first);
  const makePreview = new Function(`
    let refreshDrawingPreviewModifiers;
    let liveCursor, completedMeasurement;
    let move;
    const points = [];
    const main = {addEventListener() {}};
    const chart = {subscribeCrosshairMove: callback => { move = callback; }};
    ${source.slice(first, last)}
        liveCursor = event.point;
        points.push([liveCursor.x, Boolean(event.sourceEvent?.metaKey)]);
      }
    return {move, points, finish: () => { completedMeasurement = {}; }, modify: refreshDrawingPreviewModifiers};
  `);
  const preview = makePreview();
  preview.modify({metaKey: true});
  assert.deepEqual(preview.points, []);
  preview.modify({metaKey: false});
  preview.move({point: {x: 42}});
  preview.modify({metaKey: true});
  preview.modify({metaKey: false});
  const expected = [[42, false], [42, true], [42, false]];
  assert.deepEqual(preview.points, expected);
  preview.finish();
  preview.move({point: {x: 57}});
  preview.modify({metaKey: true});
  assert.deepEqual(preview.points, expected);
});

test('Heikin Ashi confirmation recalculates the next synthetic open from the corrected candle', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function heikinAshiBar(');
  const end = source.indexOf('  const profileHistoryRequests', start);
  assert.ok(start >= 0 && end > start);
  const synthetic = new Function(source.slice(start, end) + 'return heikinAshiBar;')();
  const first = synthetic({time: 300, open: 100, high: 112, low: 96, close: 104});
  assert.deepEqual(first, {time: 300, open: 102, close: 103, high: 112, low: 96});
  const forming = {time: 600, open: 104, high: 116, low: 100, close: 112, provisional: true};
  const confirmed = {...forming, high: 112, close: 104, provisional: false};
  const next = {time: 900, open: 104, high: 106, low: 98, close: 104, volume: 8};
  assert.equal(synthetic(next, synthetic(forming, first)).open, 105.25);
  assert.deepEqual(synthetic(next, synthetic(confirmed, first)),
    {time: 900, open: 103.75, high: 106, low: 98, close: 103, volume: 8});
});

test('locked worker price labels ignore overrides saved before the script locks them', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('          const priceLabels = new Map();');
  const end = source.indexOf('          const createFrame', start);
  assert.ok(start >= 0 && end > start);
  const labels = new Function('entries', 'study', `
    const pineUsesPricePane = () => true;
    const isPinePriceLabel = options => options?.style === 'shape';
    const isPineArrowPlot = () => false;
    ${source.slice(start, end)}
    return priceLabels;
  `);
  const entries = [
    ['locked', {options: {style: 'shape', editable: false}}],
    ['hidden', {options: {style: 'shape'}}],
    ['styled', {options: {style: 'shape'}}]
  ];
  const saved = {hiddenPlots: {0: true, 1: true}, plotColorOverrides: {0: '#ff0000', 2: '#00ff00'}};
  assert.deepEqual([...labels(entries, saved)], [['locked', undefined], ['styled', '#00ff00']]);
});

test('worker markers apply offsets and show_last after matching timestamps to loaded bars', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function pineChartFrame(');
  const end = source.indexOf('  function interpolatedBarCoordinate(', start);
  assert.ok(start >= 0 && end > start);
  const makeFrame = new Function(`
    const pineDrawingKinds = ['labels'];
    const displayMask = () => 15;
    const pineShapeLabelStyles = {};
    const isPineArrowPlot = () => false;
    ${source.slice(start, end)}
    return pineChartFrame;
  `)();
  const candles = [1000, 2000, 3000, 4000].map(openTime => ({openTime, closeTime: openTime + 1000}));
  const plots = {marker: {
    options: {style: 'char', char: 'A', location: 'AboveBar', offset: -1, show_last: 1},
    data: [{time: 3000, barIndex: 0, value: true}, {time: 4000, barIndex: 1, value: true}]
  }};
  const {objects} = makeFrame({candles, plots, priceLabels: new Map([['marker', undefined]])});
  assert.deepEqual(objects.labels.map(({x, text, yloc}) => [x, text, yloc]), [[2, 'A', 'ab']]);
});

test('Renko continues after one box, reverses after two, and uses the selected wick source', () => {
  const box = 10;
  const rising = {open: 90, close: 100};
  const candle = {time: 300, open: 100, high: 110, low: 85, close: 110};
  const ohlc = renko([candle], box, rising, 'ohlc', true);
  const closing = renko([candle], box, rising, 'close', true);
  const geometry = bricks => bricks.map(({open, high, low, close}) => [open, high, low, close]);
  assert.deepEqual(geometry(ohlc), [[100, 110, 85, 110]]);
  assert.deepEqual(geometry(closing), [[100, 110, 100, 110]]);
  assert.deepEqual(geometry(renko([candle], box, rising, 'ohlc', false)), geometry(closing));

  const falling = {open: 110, close: 100};
  const down = {...candle, high: 115, low: 90, close: 90};
  assert.deepEqual(geometry(renko([down], box, falling, 'ohlc', true)), [[100, 115, 90, 90]]);
  assert.deepEqual(renko([{...candle, close: 81}], box, rising), []);
  assert.deepEqual(geometry(renko([{...candle, close: 80}], box, rising)), [[90, 90, 80, 80]]);
});

test('pasted drawing keeps its pane anchor and selection changes only after saving', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function duplicateDrawings(');
  const end = source.indexOf('  function reorderDrawing(', start);
  assert.ok(start >= 0 && end > start);
  const limit = source.match(/^  const drawingLimit = \d+;/m);
  assert.ok(limit);
  const paste = new Function('canSave', `
    ${limit[0]}
    const original = {kind: 'chart-table', tableAnchored: true, viewportX: .4,
      viewportY: .5, cells: [['level']], locked: true};
    const settings = {drawings: [original]};
    const selectedDrawings = new Set([original]);
    let saved, undo, redraws = 0;
    const drawingSnapshot = () => structuredClone(settings.drawings);
    const save = () => {
      if (canSave) saved = drawingSnapshot();
      return canSave;
    };
    const recordDrawingEdit = snapshot => { undo = snapshot; };
    const redrawDrawings = () => { redraws++; };
    const levelMessage = () => {};
    ${source.slice(start, end)}
    duplicateDrawings([original], false, true);
    return {original, drawings: settings.drawings, selected: [...selectedDrawings], saved, undo, redraws};
  `);
  const failed = paste(false);
  assert.deepEqual(failed.drawings, [failed.original]);
  assert.deepEqual(failed.selected, [failed.original]);
  assert.equal(failed.undo, undefined);
  assert.equal(failed.redraws, 0);
  const success = paste(true);
  const copy = {...success.original, locked: false};
  assert.deepEqual(success.saved, [success.original, copy]);
  assert.deepEqual(success.undo, [success.original]);
  assert.deepEqual(success.selected, [copy]);
  assert.notStrictEqual(success.selected[0].cells, success.original.cells);
  assert.equal(success.redraws, 1);
});

test('watchlist quotes prefer fresh stream prices and compare against the prior session', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function watchlistQuotePrices(');
  const end = source.indexOf('  function updateActiveWatchlistQuote(', start);
  assert.ok(start >= 0 && end > start);
  const {watchlistQuotePrices, recordWatchlistFrame} = new Function(`
    const chartTickTimestamp = value => Number.isFinite(value) && value > 0 ? value : undefined;
    ${source.slice(start, end)}
    return {watchlistQuotePrices, recordWatchlistFrame};
  `)();
  const priorClose = [100000, 0, 0, 0, 100];
  const sameDay = [200000, 0, 0, 0, 105];
  const quote = {daily: [priorClose, sameDay]};
  recordWatchlistFrame(quote, {connected: true, latest_tick: 200600, latest_price: 106, rows: [sameDay]});
  recordWatchlistFrame(quote, {connected: true, latest_tick: 200590, latest_price: 103});
  const fresh = watchlistQuotePrices(quote, 200601, 19800);
  assert.equal(fresh.last[4], 106);
  assert.strictEqual(fresh.baseline, priorClose);
  const stale = watchlistQuotePrices(quote, 200661, 19800);
  assert.strictEqual(stale.last, sameDay);
  assert.strictEqual(stale.baseline, priorClose);
  recordWatchlistFrame(quote, {connected: false});
  assert.equal(watchlistQuotePrices(quote, 200602, 19800).live, undefined);
});

test('Renko can replace only the current provisional suffix without changing chart identity', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const classifier = source.slice(source.indexOf('  function sameRenkoBrick('),
    source.indexOf('  function matchingChartBars('));
  const start = source.indexOf('    if (isRenko) {\n      // Shape primitives');
  const end = source.indexOf('    const canReconcilePriceSeries', start);
  assert.ok(classifier && start >= 0 && end > start);
  const replace = new Function('bars', 'next', 'candle', 'workerRuntime', 'canInvalidate', `
    ${classifier}
    const pine = {kind: 'Pine', workerRuntime};
    const settings = {hideStudies: false, studies: [{kind: 'SMA'}, pine]};
    const pineStudies = new Map([[pine, {}]]);
    let invalidated = false;
    const overlay = () => true;
    if (canInvalidate) overlay.invalidateRenkoFrame = () => { invalidated = true; };
    const pineOverlayUpdates = new Map([[pine, overlay]]);
    const size = 1, isRenko = true;
    const drawings = [{kind: 'fib'}, {kind: 'fib-extension'}], shapes = [];
    const priceFib = kind => kind === 'fib' || kind === 'fib-extension';
    const rangeStudies = [], pivotStudies = [], studyNotices = [], recolorStudies = [];
    const studyVisible = () => true, renkoBoxSize = () => size, completedRenkoCandles = () => [], chartTickSize = () => 1;
    const chartRenkoBricks = () => next, matchingChartBars = () => 1, sameCandle = () => false;
    const renkoSourceByTime = new Map(), pendingSyntheticPlots = new Map(), firstBrickBySource = new Map();
    const byTime = new Map(bars.map(brick => [brick.time, brick]));
    const indexes = new Map(bars.map((brick, index) => [brick.time, index]));
    const range = {from: -5, to: 2};
    let restoredRange, data, studyData, brokerPrice, updateLastPrice, pinCleared = false, dataWindowPinned = true, cursorTime = 3;
    let cursorLevel, horizontalShortcutPrice, shortcutDrawingAnchor, movingCrosshair;
    const chart = {timeScale: () => ({getVisibleLogicalRange: () => range, setVisibleLogicalRange: value => { restoredRange = value; }}),
      clearCrosshairPosition() { assertCrosshairReset(); }};
    const charts = [chart];
    const assertCrosshairReset = () => { if (movingCrosshair !== true) throw new Error("Crosshair reset re-entered"); };
    const brokerPriceLine = {applyOptions: ({price}) => { brokerPrice = price; }};
    const mainSeries = {setData: points => { data = points; }};
    const pricePoint = brick => brick.time;
    const studyUpdates = [(bars, last, replaceAll) => { if (replaceAll) studyData = bars.map(brick => brick.time); }];
    const inspectedBarTime = () => 3, clearDataWindowPin = () => { pinCleared = true; dataWindowPinned = false; };
    const inspect = () => {}, updateLatestButton = () => {}, priceHistoryDetail = () => '';
    const refreshAnchoredVwaps = [], refreshVolumeProfiles = () => false, repaintDrawingAnchors = () => {};
    const panel = {querySelector: () => ({})};
    ${source.slice(start, end)}
    const updated = updateLastPrice(candle);
    return {updated, data, studyData, brokerPrice, pinCleared, cursorTime, restoredRange, times: [...byTime.keys()], invalidated};
  `);
  const base = {time: 1, sourceTime: 10};
  const projections = [{time: 2, sourceTime: 20, provisional: true}, {time: 3, sourceTime: 20, provisional: true}];
  const next = [{...base}];
  assert.deepEqual(replace([base, ...projections], next, {time: 20, close: 101.25, provisional: true}), {
    updated: true, data: [1], studyData: [1], brokerPrice: 101.25, pinCleared: true, cursorTime: undefined,
    restoredRange: {from: -5, to: 2}, times: [1], invalidated: false
  });
  assert.equal(replace([base, ...projections], next, {time: 20, provisional: true}, true).updated, false);
  const withWorker = replace([base, ...projections], next, {time: 20, provisional: true}, true, true);
  assert.equal(withWorker.updated, true);
  assert.equal(withWorker.invalidated, true);
  const original = {...projections[1], open: 101, close: 102};
  const changed = {...original, open: 99, close: 98};
  const reusedIndex = replace([base, projections[0], original], [base, projections[0], changed],
    {time: 20, provisional: true});
  assert.equal(reusedIndex.updated, true);
  assert.deepEqual(reusedIndex.times, [1, 2, 3]);
  assert.equal(reusedIndex.pinCleared, true);
  assert.equal(reusedIndex.cursorTime, undefined);

  const sameBrick = replace([base, projections[0], original], [base, {...projections[0], low: 98}, {...original, high: 103}],
    {time: 20, provisional: true});
  assert.equal(sameBrick.updated, true);
  assert.equal(sameBrick.pinCleared, false);
  assert.equal(sameBrick.cursorTime, 3);
  const confirmed = {...projections[0], provisional: false};
  assert.equal(replace([base, confirmed, projections[1]], next, {time: 20, provisional: true}).updated, false);
});

test('Renko restores the cached Pine frame when projected bricks return to their evaluated sequence', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('          if (isRenko) updateOverlay.invalidateRenkoFrame =');
  const end = source.indexOf('          pineOverlayUpdates.set(study, updateOverlay);', start);
  assert.ok(start >= 0 && end > start);
  const run = new Function(`
    const study = {}, isRenko = true, updateOverlay = {};
    const evaluation = {bricks: [{time: 1}, {time: 2}], plots: {}};
    const bars = [...evaluation.bricks];
    const workerPineResults = new Map([[study, evaluation]]);
    const pendingSyntheticPlots = new Map();
    const matchingChartBars = (current, evaluated) => {
      const mismatch = current.findIndex((bar, index) => bar.time !== evaluated[index]?.time);
      return mismatch < 0 ? current.length : mismatch;
    };
    const createFrame = (_evaluation, _bars, matched, _pane, stale) => ({matched, stale});
    let frame;
    const overlay = {update(nextFrame) { frame = nextFrame; }};
    const updatePaneMarkerFrame = undefined;
    const acceptWorkerPlots = () => {};
    ${source.slice(start, end)}
    const snapshot = () => ({frame, pending: pendingSyntheticPlots.get(study), waiting: updateOverlay.awaitingRenkoFrame});
    bars[1] = {time: 3};
    updateOverlay.invalidateRenkoFrame();
    const replacement = snapshot();
    bars[1] = evaluation.bricks[1];
    updateOverlay.invalidateRenkoFrame();
    return {replacement, recovered: snapshot()};
  `);
  assert.deepEqual(run(), {
    replacement: {frame: {matched: 1, stale: true}, pending: 1, waiting: true},
    recovered: {frame: {matched: 2, stale: false}, pending: undefined, waiting: false}
  });
});

test('percentage Renko holds the load close and follows the replay cursor', () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const sizeStart = source.indexOf('  let renkoPercentReference;');
  const sizeEnd = source.indexOf('  function visiblePlotColor(', sizeStart);
  const detailStart = source.indexOf('    function priceHistoryDetail(');
  const detailEnd = source.indexOf("    panel.querySelector('[data-chart-history-detail]').textContent = priceHistoryDetail", detailStart);
  assert.ok(sizeStart >= 0 && sizeEnd > sizeStart && detailStart >= 0 && detailEnd > detailStart);
  const run = new Function('first', 'confirmed', 'bar', 'sizing', `
    let generation = 1, barReplay;
    const window = {SectorPulseRenkoSizing: sizing};
    const settings = {brickMethod: 'percent', brickPercent: 1.25};
    const isKagi = false, isVolumeCandles = false, isHeikinAshi = false, isRenko = true;
    const useAtr = false, usePercent = true, bars = [bar];
    const candleHistoryDetail = () => 'Delta India';
    const formatChartPrice = value => String(value);
    ${source.slice(sizeStart, sizeEnd)}
    const size = renkoBoxSize(settings, [first], 0.5, true);
    ${source.slice(detailStart, detailEnd)}
    const detail = priceHistoryDetail(bar);
    const afterClose = renkoBoxSize(settings, [first, confirmed], 0.5, true);
    barReplay = {};
    const replay = renkoBoxSize(settings, [first, confirmed], 0.5, true);
    barReplay = undefined;
    generation++;
    const afterReload = renkoBoxSize(settings, [first, confirmed], 0.5, true);
    return {size, detail, afterClose, replay, afterReload};
  `);
  const first = {close: 40000};
  const forming = {close: 80000, provisional: true};
  const result = run(first, {...forming, provisional: false}, forming, require('../chart-renko-sizing.js'));
  assert.equal(result.size, 500);
  assert.match(result.detail, /500 pts.*1\.25% of reference close/);
  assert.equal(result.afterClose, 500);
  assert.equal(result.replay, 1000);
  assert.equal(result.afterReload, 1000);
});

test('Pine save and revision open use the script editor when a watchlist textarea comes first', async () => {
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const saveStart = source.indexOf("    if (action.action === 'save-script') {");
  const saveEnd = source.indexOf("    if (action.action === 'delete-revision') {", saveStart);
  const openStart = source.indexOf("    if (action.action === 'open-revision' || action.action === 'open-broker-script') {", saveEnd);
  const openEnd = source.indexOf('    if (action.interval)', openStart);
  assert.ok(saveStart >= 0 && saveEnd > saveStart && openStart > saveEnd && openEnd > openStart);
  const exercise = new Function(`
    return (async () => {
      const watchlist = {value: 'NIFTY, BANKNIFTY'};
      const draft = {value: 'plot(close)', focus() {}};
      const revision = {source: 'plot(open)'};
      const status = {textContent: ''};
      const settings = {};
      const saved = [];
      let editedPineStudy, newPineDraft;
      const sharedChartView = false;
      const panel = {querySelector(selector) {
        const fields = {
          textarea: watchlist,
          '.sp-chart-editor textarea': draft,
          '[data-script-revisions]': {value: '0'},
          '[data-script-status]': status
        };
        if (!(selector in fields)) throw new Error('Unexpected selector: ' + selector);
        return fields[selector];
      }};
      const save = () => true;
      const saveScriptRevision = async text => { saved.push(text); };
      const scriptRevisions = () => [revision, {source: draft.value}];
      const updateScriptPosition = () => {};
      const handle = async action => {
        ${source.slice(saveStart, saveEnd)}
        ${source.slice(openStart, openEnd)}
      };
      await handle({action: 'save-script'});
      const savedDraft = settings.draft;
      await handle({action: 'open-revision'});
      return {saved, savedDraft, reopened: draft.value, watchlist: watchlist.value};
    })();
  `);
  assert.deepEqual(await exercise(), {
    saved: ['plot(close)'],
    savedDraft: 'plot(close)',
    reopened: 'plot(open)',
    watchlist: 'NIFTY, BANKNIFTY'
  });
});

test('Delta replay extends its dated window once and rejoins recent history at the boundary', async () => {
  const vm = require('node:vm');
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  async function replayPineHistory(');
  const end = source.indexOf('  function pineUsesWorkerFeatures', start);
  const recentStart = 630000;
  const requests = [];
  const load = vm.runInNewContext(source.slice(start, end) + '\nreplayPineHistory', {
    broker: {yahoo: false}, deltaSymbolSelection: true,
    chartQuery: params => new URLSearchParams(params),
    requestChartHistory: async () => ({rows: [[recentStart, 1, 2, 1, 2, 20]], older_history: true}),
    requestOlderChartCandles: async (resolution, before, signal, symbol) => {
      requests.push([resolution, before, symbol]);
      return {candles: new Map(Array.from({length: 900}, (_, i) => {
        const time = before - (i + 1) * 300;
        return [time, {time}];
      }))};
    },
    candleEnd: (time, interval) => time + Number(interval) * 60
  });
  const replay = {scope: new AbortController(), requestedHistory: new Map(),
    bars: [{time: 300000 - 1800}, {time: 390000}, {time: recentStart - 3600}, {time: recentStart}],
    startCount: 1, count: 1, interval: '30'};
  const run = () => load(replay, '5', 'BTCUSD');
  const first = await run();
  assert.equal(first.targetedThrough, 390000);
  assert.equal(first.bars.at(-1).time, 389700);
  replay.count++;
  const [a, b] = await Promise.all([run(), run()]);
  assert.equal(a, b);
  assert.equal(a.targetedThrough, 481800);
  assert.equal(a.bars[0].time, first.bars[0].time);
  replay.count++;
  const joined = await run();
  assert.equal(joined.targetedThrough, 630000);
  assert.equal(joined.bars.at(-1).time, recentStart);
  assert.ok(joined.bars.slice(1).every((bar, index) => bar.time - joined.bars[index].time === 300));
  replay.count++;
  assert.equal(await run(), joined);
  assert.deepEqual(requests, [['5', 390000, 'BTCUSD'], ['5', 481800, 'BTCUSD'], ['5', 630000, 'BTCUSD']]);
});

test('Pine replay pages to its starting candle without revealing unclosed secondary candles', async () => {
  const vm = require('node:vm');
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  async function replayPineHistory(');
  const end = source.indexOf('  function pineUsesWorkerFeatures', start);
  const calls = [];
  const run = vm.runInNewContext(source.slice(start, end) + '\nreplayPineCandles', {
    broker: {yahoo: false}, deltaSymbolSelection: false,
    chartQuery: params => new URLSearchParams(params),
    requestChartHistory: async () => ({
      rows: [[1800, 1, 2, 1, 2, 20]], older_history: true
    }),
    requestOlderChartCandles: async (resolution, before, signal, symbol) => {
      calls.push([resolution, before, symbol]);
      const time = before - 300;
      return {data: {older_history: true}, candles: new Map([[time, {time, close: 2}]])};
    },
    candleEnd: (time, interval) => time + Number(interval) * 60,
    validInterval: () => true, sourceInterval: () => true, tradeInterval: () => false
  });
  const scope = new AbortController();
  const replay = {scope, requestedHistory: new Map(), bars: [{time: 1240}], startCount: 1, interval: '1'};
  const request = {ticker: 'BTCUSD', interval: '5'};
  const first = await run(request, [{time: 1240}], 'BTCUSD', '1', replay, scope.signal);
  assert.deepEqual(calls, [['5', 1800, 'BTCUSD'], ['5', 1500, 'BTCUSD'], ['5', 1200, 'BTCUSD']]);
  assert.deepEqual(Array.from(first, bar => bar.openTime), [900000]);
  const stepped = await run(request, [{time: 1440}], 'BTCUSD', '1', replay, scope.signal);
  assert.deepEqual(Array.from(stepped, bar => bar.openTime), [900000, 1200000]);
  assert.equal(calls.length, 3);
});

test('Pine shares older broker pages by cutoff and stops once the requested date is covered', async () => {
  const vm = require('node:vm');
  const source = require('node:fs').readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  const referencedOlderHistoryRequests =');
  const end = source.indexOf('  async function loadPineCandles', start);
  const history = new Map([['5', [{time: 900}, {time: 1200}]]]);
  const olderHistory = new Set(['5']);
  const chartScope = new AbortController().signal;
  const calls = [];
  const load = vm.runInNewContext(source.slice(start, end) + '\nloadReferencedHistoryThrough', {
    requestScope: {signal: chartScope}, history, olderHistory, broker: {yahoo: false},
    requestOlderChartCandles: async (interval, before, signal) => {
      assert.equal(signal, chartScope);
      calls.push([interval, before]);
      const time = before - 300;
      return {data: {older_history: time > 300}, candles: new Map([[time, {time}]])};
    }
  });
  await Promise.all([load('5', 350000, new AbortController().signal),
    load('5', 350000, new AbortController().signal)]);
  assert.deepEqual(calls, [['5', 900], ['5', 600]]);
  assert.deepEqual([...history.get('5')].map(bar => bar.time), [300, 600, 900, 1200]);
  assert.equal(olderHistory.has('5'), false);
});

test('Delta Pine reuses secondary history unless the original request crossed rollover', async () => {
  const { readFileSync } = require('node:fs');
  const vm = require('node:vm');
  const source = readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const extract = name => {
    const match = source.match(new RegExp('^  (?:async )?function ' + name + '\\([\\s\\S]*?^  }', 'm'));
    assert.ok(match, name);
    return match[0];
  };
  const provider = new vm.Script([
    'const pendingHistory = new WeakMap();',
    extract('loadHistory'),
    extract('loadPineCandles'),
    extract('pineCandleRowsForWindow'),
    extract('pineIntradayWindow'),
    ...['calendarHistoryPrefix', 'calendarPrefixAvailableAt', 'calendarRowsAtSnapshotCutoff']
      .filter(name => source.includes('  function ' + name + '(')).map(extract),
    '({ loadHistory, loadPineCandles, pineIntradayWindow })'
  ].join('\n'));

  const { pineIntradayWindow } = provider.runInNewContext({});
  const sample = Array.from({length: 100}, (_, index) => ({time: (index + 1) * 300}));
  for (const start of [undefined, 0, 300000, 600001, 30000000, 40000000]) {
    for (const end of [undefined, 0, 300000, 2100000, 30000000]) {
      for (const limit of [1, 7, 100]) {
        const expected = sample.filter(bar => (start == null || bar.time * 1000 >= start)
          && (end == null || bar.time * 1000 <= end)).slice(-limit);
        assert.deepEqual(pineIntradayWindow(sample, start, end, limit), expected);
      }
    }
  }

  for (const [requestedAt, expectedRequests] of [[901, 1], [899, 2]]) {
    const signal = new AbortController().signal;
    let now = requestedAt;
    let requests = 0;
    const { loadHistory, loadPineCandles } = provider.runInNewContext({
      Date: { now: () => now * 1000 },
      requestScope: { signal },
      chartSymbol: () => 'BTCUSD',
      settings: { interval: '30' },
      deltaSymbolSelection: true,
      tradeInterval: interval => /[ST]$/.test(interval),
      deltaTradeSymbol: symbol => symbol === 'BTCUSD',
      fyersSymbolSelection: false,
      broker: {},
      history: new Map(),
      pineHistoryChecks: new Map(),
      calendarPrefixes: new Map(),
      rows: [],
      calendarInterval: () => false,
      validInterval: () => true,
      sourceInterval: () => true,
      candleEnd: time => time + 300,
      rememberNcdexSessions() {},
      chartQuery: () => '',
      async requestChartHistory() {
        requests++;
        now = 902;
        return { rows: [[requests === 1 ? 300 : 600, 100, 105, 98, 101, 5]] };
      }
    });

    const captured = await loadHistory('5S', signal);
    assert.equal(captured.length, 0);
    assert.equal(await loadHistory('5S', signal), captured);
    assert.equal(requests, 0);
    await loadHistory('5', signal);
    const candles = await loadPineCandles({ ticker: 'BTCUSD', interval: '5', start: 0 }, signal);
    assert.equal(requests, expectedRequests);
    assert.equal(candles.at(-1).openTime, expectedRequests === 1 ? 300000 : 600000);
  }
});

test('Pine updates compatible plot corrections in place and redraws when plot metadata changes', () => {
  const { readFileSync } = require('node:fs');
  const vm = require('node:vm');
  const source = readFileSync(require.resolve('../chart-workspace.js'), 'utf8');
  const implementation = source.slice(
    source.indexOf('  function pinePlotsChangeAtTail'),
    source.indexOf('  const pineRestoreStatus')
  );
  const study = {};
  const updates = [];
  const pineOverlayUpdates = new WeakMap([[study, (_, tables, drawings, plots, replace) => {
    updates.push({ tables, drawings, plots, replace });
    return true;
  }]]);
  let redraws = 0;
  const displayedBars = [{ time: 100 }, { time: 200 }];
  const publish = vm.runInNewContext(implementation + '\npublishWorkerPineResult', {
    workerPineResults: new WeakMap(),
    pineOverlayUpdates,
    barReplay: null,
    pendingViewportRedraw: false,
    displayedBars,
    redrawKeepingViewport() { redraws++; }
  });
  const evaluation = (first, last, color = '#ff0000') => ({
    source: 'test script',
    symbol: 'BTCUSD',
    interval: '1',
    chartType: 'Candles',
    historyStart: { time: 100, count: 2 },
    plots: { line: { color, data: [{ time: 100000, value: first }, { time: 200000, value: last }] } }
  });

  publish(study, evaluation(1, 2));
  assert.equal(redraws, 1);
  publish(study, evaluation(1, 3));
  publish(study, evaluation(2, 3));
  publish(study, evaluation(2, 3));
  assert.deepEqual(updates, [
    { tables: false, drawings: false, plots: true, replace: false },
    { tables: false, drawings: false, plots: true, replace: true }
  ]);
  assert.equal(redraws, 1);
  displayedBars.push({ time: 300 });
  const appended = evaluation(2, 3);
  appended.historyStart.count = 3;
  appended.plots.line.data.push({ time: 300000, value: 4 });
  publish(study, appended);
  assert.deepEqual(updates.at(-1), { tables: false, drawings: false, plots: true, replace: false });
  assert.equal(redraws, 1);
  publish(study, {
    ...appended,
    plots: { line: { ...appended.plots.line, color: '#0000ff' } }
  });
  assert.equal(redraws, 2);
});

test('An older tab preserves drawing changes from another tab during unrelated saves', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function mergeSavedDrawings(');
  const end = source.indexOf('  function save()', start);
  assert.ok(start >= 0 && end > start);
  const merge = new Function(source.slice(start, end) + 'return mergeSavedDrawings;')();
  const previous = {symbol: 'A', drawings: [], levels: [10]};
  const stored = {
    symbol: 'B', drawings: [{kind: 'ray'}], levels: [20],
    instrumentDrawings: {A: [{kind: 'trend'}]}, instrumentLevels: {A: []},
    horizontalVisibilityBySymbol: {B: {20: {locked: true}}}
  };

  const first = {...previous, interval: '5'};
  merge(first, previous, stored, 'A');
  assert.deepEqual(first.drawings, [{kind: 'trend'}]);
  assert.deepEqual(first.levels, []);
  assert.deepEqual(first.instrumentDrawings.B, [{kind: 'ray'}]);
  assert.deepEqual(first.horizontalVisibilityBySymbol.B, {20: {locked: true}});

  const switched = {symbol: 'B', drawings: [], levels: [], instrumentLevels: {A: [10]}};
  merge(switched, previous, first, 'A');
  assert.deepEqual(switched.drawings, [{kind: 'ray'}]);
  assert.deepEqual(switched.levels, [20]);
  assert.deepEqual(switched.instrumentLevels.A, []);

  const edited = {...previous, levels: [30]};
  merge(edited, previous, first, 'A');
  assert.deepEqual(edited.levels, [30]);
  assert.deepEqual(edited.drawings, [{kind: 'trend'}]);
});

test('BBTrend uses two Bollinger windows, skips warm-up and colors each direction', () => {
  const [trend] = indicators.BBTrend.run([], [1, 2, 5, 4, 1], undefined, undefined,
    {shortLength: 2, longLength: 3, deviation: 2});
  assert.deepEqual(trend.slice(0, 2), [null, null]);
  const shortBasis = (2 + 5) / 2;
  const longBasis = (1 + 2 + 5) / 3;
  const longWidth = 2 * Math.sqrt(((1 - longBasis) ** 2 + (2 - longBasis) ** 2 + (5 - longBasis) ** 2) / 3);
  const expected = 100 * (Math.abs((shortBasis - 3) - (longBasis - longWidth))
    - Math.abs((shortBasis + 3) - (longBasis + longWidth))) / shortBasis;
  assert.ok(Math.abs(trend[2] - expected) < 1e-10);
  assert.ok(trend[3] > 0 && trend[4] < 0);
  assert.equal(trend.colors[2], '#089981');
  assert.equal(trend.colors[4], '#f23645');
});

test('Bollinger BandWidth tracks expansion and contraction on independent rolling windows', () => {
  const [width, expansion, contraction] = indicators.BBWidth.run([], [10, 10, 14, 16, 16, 24], 2, 2,
    {expansionLength: 2, contractionLength: 3});
  assert.equal(width[0], null);
  assert.equal(width[1], 0);
  assert.equal(width[2], 200 / 3);
  assert.deepEqual(expansion, [null, 0, width[2], width[2], width[3], width[5]]);
  assert.deepEqual(contraction, [null, 0, 0, 0, 0, 0]);
});

test('Chart storage keeps one source for an identical Pine draft and applied script', () => {
  const workspace = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = workspace.indexOf('  function compactChartDraft(');
  const end = workspace.indexOf('  function restorePineDraftTarget(', start);
  assert.ok(start >= 0 && end > start);
  const {compactChartDraft, savedChartDraft} = new Function(workspace.slice(start, end)
    + 'return {compactChartDraft, savedChartDraft};')();
  const source = '//@version=6\nindicator("Long script")\n' + '// content\n'.repeat(15000);
  const studies = [{kind: 'SMA'}, {kind: 'Pine', source}];
  const stored = JSON.parse(JSON.stringify(compactChartDraft({studies, draft: source, pineDraftTarget: 1})));
  assert.equal(stored.draft, undefined);
  assert.equal(stored.draftFromStudy, 1);
  assert.equal(stored.pineDraftTarget, 1);
  assert.equal(savedChartDraft(stored), source);
  const edit = source + 'plot(close)';
  const unapplied = compactChartDraft({studies, draft: edit});
  assert.equal(unapplied.draftFromStudy, undefined);
  assert.equal(savedChartDraft(unapplied), edit);
  assert.equal(savedChartDraft({studies, draftFromStudy: 0}), undefined);
});

test('Higher-timeframe crossover labels appear once, on the confirming chart bar', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function alignConfirmedStudyPlots(');
  const end = source.indexOf('\n  }', start) + 4;
  const align = new Function(source.slice(start, end) + 'return alignConfirmedStudyPlots;')();
  const reference = [0, 30, 60].map(time => ({time}));
  const chartBars = [35, 40, 45, 50, 55, 60, 65].map(time => ({time, provisional: time === 55}));
  const result = align([[1, 2, 3], [1, 2, null]], reference, chartBars,
    bar => bar.time + 30, bar => bar.provisional ? bar.time : bar.time + 5, [1]);
  assert.deepEqual(result, [[1, 1, 1, 1, 1, 2, 2], [null, null, null, null, null, null, null]]);
  chartBars[4].provisional = false;
  assert.deepEqual(align([[1, 2, 3], [1, 2, null]], reference, chartBars,
    bar => bar.time + 30, bar => bar.time + 5, [1]),
    [[1, 1, 1, 1, 2, 2, 2], [null, null, null, null, 2, null, null]]);
});

test('An older chart save keeps Pine studies copied after that tab opened', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function preserveCopiedPineStudies(');
  const end = source.indexOf('\n  }', start) + 4;
  const preserve = new Function(source.slice(start, end) + 'return preserveCopiedPineStudies;')();
  const draftStudy = {kind: 'Pine', source: 'Draft'};
  const copied = {kind: 'Pine', source: 'Copied source', sharedCopyId: 'new-copy'};
  const removed = {kind: 'Pine', source: 'Removed source', sharedCopyId: 'old-copy'};
  const previous = {studies: [draftStudy, removed]};
  const view = {studies: [draftStudy], draftFromStudy: 0};
  const stored = {studies: [draftStudy, copied, removed]};
  preserve(view, previous, stored);
  preserve(view, previous, stored);
  assert.deepEqual(view, {studies: [draftStudy, copied], draftFromStudy: 0});
});

test('Pine requests reuse identical candle windows only within the current evaluation', async () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function pineCandleWindowForEvaluation(');
  const end = source.indexOf('\n  }', start) + 4;
  const reuse = new Function(source.slice(start, end) + 'return pineCandleWindowForEvaluation;')();
  const candles = new Map();
  const request = {ticker: 'BTCUSD', interval: 'D', end: 1000, limit: 500};
  let loads = 0;
  const load = async () => ++loads;
  const first = reuse(candles, request, load);
  assert.equal(reuse(candles, {...request, interval: '1D'}, load), first);
  assert.equal(await first, 1);
  assert.equal(await reuse(candles, {...request, limit: 200}, load), 2);
  assert.equal(await reuse(new Map(), request, load), 3);
  const later = {...request, end: 2000};
  await assert.rejects(reuse(candles, later, async () => { throw new Error('unavailable'); }));
  assert.equal(await reuse(candles, later, load), 4);
});

test('Delta cross-symbol replay returns only reference candles closed by the cursor', async () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  async function replayPineCandles(');
  const end = source.indexOf('\n  }', start) + 4;
  const replayCandles = new Function('validInterval', 'sourceInterval', 'tradeInterval',
    'alternatePineReferenceSymbol', 'candleEnd', 'replayCandleEnd', 'replayPineHistory', 'broker',
    source.slice(start, end) + 'return replayPineCandles;')(
    () => true, () => true, () => false, ticker => ticker.replace('DELTAIN:', ''),
    time => time + 300, time => time + 1800, async (replay, interval, symbol) => {
      assert.equal(symbol, 'ETHUSD');
      return {bars: [{time: 0, close: 1900}, {time: 1800, close: 1920}, {time: 3600, close: 1960}]};
    }, {yahoo: false});
  const data = await replayCandles({ticker: 'DELTAIN:ETHUSD', interval: '30'}, [{time: 2400, close: 60000}],
    'BTCUSD', '5', {}, new AbortController().signal);
  assert.deepEqual(data.map(bar => [bar.openTime, bar.closeTime, bar.close, bar.provisional]), [[0, 1800000, 1900, false]]);
});

test('Yahoo Pine references use their own close times and a daily fallback for legacy candles', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function yahooPineReferenceClose(');
  const end = source.indexOf('\n  }', start) + 4;
  const close = new Function(source.slice(start, end) + 'return yahooPineReferenceClose;')();
  assert.equal(close(100000, '1D', {100000: 123400}), 123400);
  assert.equal(close(100000, '1D'), 186400);
  assert.equal(close(100000, '30'), 101800);
  assert.equal(close(100000, '1M', {100000: 200000}), 200000);
});

test('Dhan cross-symbol Pine requests stay in the host equity segment', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function alternatePineReferenceSymbol(');
  const end = source.indexOf('\n  }', start) + 4;
  const resolveReference = new Function('deltaSymbolSelection', 'fyersSymbolSelection', 'dhanSymbolSelection',
    'broker', 'tradeInterval', 'motilalSymbolSelection', source.slice(start, end) + 'return alternatePineReferenceSymbol;')(
    false, false, true, {yahoo: false}, interval => interval.endsWith('S'), false);
  assert.equal(resolveReference('nse_eq:1333', '30', 'NSE_EQ:2885'), 'NSE_EQ:1333');
  assert.equal(resolveReference('BSE_EQ:500180', '1D', 'BSE_EQ:500325'), 'BSE_EQ:500180');
  assert.throws(() => resolveReference('BSE_EQ:500180', '30', 'NSE_EQ:2885'), {code: 'PINE_REFERENCE_UNSUPPORTED'});
  assert.throws(() => resolveReference('NSE_EQ:1333', '5S', 'NSE_EQ:2885'), {code: 'PINE_REFERENCE_UNSUPPORTED'});
});

test('Price Momentum Oscillator uses two custom smoothing factors and a standard EMA signal', () => {
  const inputs = {firstLength: 4, secondLength: 2, signalLength: 3};
  const calculate = values => indicators.PMO.run([], values, undefined, undefined, inputs);
  assert.deepEqual(calculate([100, 110, 110, 99]), [[null, 100, 50, -25], [null, 100, 75, 25]]);
  assert.deepEqual(calculate([100, 100, 100]), [[null, 0, 0], [null, 0, 0]]);
  assert.deepEqual(calculate([0, 100, 110]), [[null, null, 100], [null, null, 100]]);
});

test('Leaving the chart panes resets the hover reading and preserves the Data Window', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('    const plotElements = charts.map(source => source.chartElement());');
  const end = source.indexOf("    panel.addEventListener('pointerover', resetOutsidePlots", start);
  assert.ok(start >= 0 && end > start);
  const run = new Function('assert', `
    const pricePlot = {}, indicatorPlot = {}, legend = {}, toolbar = {};
    let cleared = 0, inspected = 0;
    const charts = [pricePlot, indicatorPlot].map(plot => ({
      chartElement: () => ({contains: target => target === plot}),
      clearCrosshairPosition() { assert.equal(movingCrosshair, true); cleared++; }
    }));
    const indicatorLegend = {contains: target => target === legend, removeEventListener() {}};
    const resetLegendAfterPointer = () => {};
    const inspect = (time, options) => {
      assert.equal(time, undefined);
      assert.equal(options.keepDataWindow, true);
      inspected++;
    };
    let cursorTime = 100, cursorLevel = 20;
    let horizontalShortcutPrice = 20, shortcutDrawingAnchor = {};
    let legendReset, legendWaitingForLeave = false, movingCrosshair = false;
    ${source.slice(start, end)}
    for (const target of [pricePlot, indicatorPlot, legend]) resetOutsidePlots({type: 'pointerover', target});
    assert.equal(cursorTime, 100);
    assert.equal(inspected, 0);
    resetOutsidePlots({type: 'pointerover', target: toolbar});
    assert.equal(cursorTime, undefined);
    assert.equal(cursorLevel, undefined);
    assert.equal(horizontalShortcutPrice, undefined);
    assert.equal(shortcutDrawingAnchor, undefined);
    assert.equal(movingCrosshair, false);
    assert.equal(cleared, 2);
    assert.equal(inspected, 1);
    resetOutsidePlots({type: 'pointerover', target: toolbar});
    assert.equal(inspected, 1);
    legendWaitingForLeave = true;
    resetOutsidePlots({type: 'pointerleave'});
    assert.equal(inspected, 2);
  `);
  run(assert);
});

test('Renko rebuilds only when a broker candle can affect the bricks', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  function renkoSourceGeometryChanged(');
  const end = source.indexOf('  function renkoProjectionReplaced(', start);
  assert.ok(start >= 0 && end > start);
  const rebuild = new Function(source.slice(start, end) + 'return renkoSourceGeometryChanged;')();

  const live = {time: 60, open: 100, high: 105, low: 99, close: 103, volume: 2, provisional: true};
  const higherWick = {...live, high: 106, volume: 3};
  const nextTick = {...live, close: 104, volume: 3};
  const closed = {...live, provisional: false};
  assert.equal(rebuild(live, higherWick, {renkoSource: 'close'}), false);
  assert.equal(rebuild(live, higherWick, {renkoSource: 'ohlc'}), true);
  assert.equal(rebuild(live, {...live, volume: 3}, {renkoSource: 'ohlc'}), false);
  assert.equal(rebuild(live, nextTick, {renkoSource: 'close'}), true);
  assert.equal(rebuild(live, {...live, historyOnly: true}, {}), true);
  assert.equal(rebuild(live, closed, {}), true);
  assert.equal(rebuild(undefined, live, {}), true);
  assert.equal(rebuild(undefined, live, {renkoProjection: false}), false);
  assert.equal(rebuild(live, nextTick, {renkoProjection: false}), false);
  assert.equal(rebuild(live, closed, {renkoProjection: false}), true);
  assert.equal(rebuild(closed, live, {renkoProjection: false}), true);
});

test('Renko ATR sizing reuses completed history and recalculates on changed inputs', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const start = source.indexOf('  const renkoAtrByHistory = new WeakMap();');
  const end = source.indexOf('  function visiblePlotColor(', start);
  assert.ok(start >= 0 && end > start);
  let calculations = 0;
  const atrSize = globalThis.SectorPulseChartStudies.renkoAtrSize;
  const boxSize = new Function('renkoAtrSize', source.slice(start, end) + 'return renkoBoxSize;')((...args) => {
    calculations++;
    return atrSize(...args);
  });
  const config = {brickMethod: 'atr', brickAtrLength: 2};
  const completed = [{open: 10, high: 12, low: 9, close: 11}, {open: 11, high: 13, low: 10, close: 12}];
  for (let i = 0; i < 500; i++) assert.equal(boxSize(config, completed, 1), 3);
  assert.equal(calculations, 1);

  const corrected = [completed[0], {...completed[1], high: 17}];
  assert.equal(boxSize(config, corrected, 1), 5);
  assert.equal(boxSize({...config, brickAtrLength: 1}, corrected, 1), 7);
  assert.equal(boxSize({...config, brickAtrLength: 1}, corrected, 2), 8);
  assert.equal(boxSize({...config, brickAtrLength: 1}, corrected, 2), 8);
  assert.equal(calculations, 4);
  assert.equal(boxSize({brickMethod: 'atr'}, completed, 1), null);
});

test('A forming calendar candle retains its broker history until the next native session arrives', () => {
  const source = readFileSync(resolve(__dirname, '../chart-workspace.js'), 'utf8');
  const mergeStart = source.indexOf('  function calendarLiveWithPrefix(');
  const mergeEnd = source.indexOf('  function renderLiveRows(', mergeStart);
  const statusStart = source.indexOf('  function provisionalStatus(');
  const statusEnd = source.indexOf('  function renkoBrickStatus(', statusStart);
  assert.ok(mergeStart >= 0 && mergeEnd > mergeStart && statusStart >= 0 && statusEnd > statusStart);
  const run = new Function('assert', `
    const broker = {nse: false};
    const settings = {interval: '12M'};
    const prefix = {bar: [0, 105, 112, 90, 102, 1500], through: 86400};
    const calendarPrefixes = new Map([['12M', prefix]]);
    const calendarInterval = value => value.endsWith('M');
    const chartTime = time => String(time);
    const tradeInterval = () => false;
    ${source.slice(mergeStart, mergeEnd)}
    ${source.slice(statusStart, statusEnd)}
    const bar = {time: 0, provisional: true, historyOnly: true};
    assert.match(provisionalStatus(bar), /Broker history through 86400/);
    assert.equal(calendarLiveWithPrefix([[0, 103, 116, 95, 110, 20, 259200]], prefix), undefined);
    assert.deepEqual(calendarLiveWithPrefix([[0, 103, 116, 95, 110, 20, 172800]], prefix),
      [0, 105, 116, 90, 110, 1520]);
    assert.match(provisionalStatus({...bar, historyOnly: false}), /WebSocket bar pending/);
  `);
  run(assert);
});

test('MFI ignores equal typical prices despite binary rounding at broker boundaries', () => {
  const {pairs} = JSON.parse(readFileSync(resolve(__dirname, 'fixtures/mfi-equal-price-boundaries.json'), 'utf8'));
  for (const bars of pairs) {
    assert.deepEqual(indicators.MFI.run(bars, [], 1)[0], [null, null]);
  }
});

test('MFI zero-flow windows remain unavailable after a large expired flow', () => {
  const bars = [
    {open: 1, high: 1, low: 1, close: 1, volume: 1},
    {open: 2.1, high: 2.1, low: 2.1, close: 2.1, volume: 999999999.1},
    {open: 3.2, high: 3.2, low: 3.2, close: 3.2, volume: 0.1},
    {open: 3.2, high: 3.2, low: 3.2, close: 3.2, volume: 0},
    {open: 3.2, high: 3.2, low: 3.2, close: 3.2, volume: 0}
  ];
  assert.deepEqual(indicators.MFI.run(bars, [], 1)[0], [null, 100, 100, null, null]);
  assert.deepEqual(indicators.MFI.run(bars, [], 2)[0], [null, null, 100, 100, null]);
});
