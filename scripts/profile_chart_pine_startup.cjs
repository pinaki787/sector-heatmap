const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');

const bundle = process.argv[2];
if (!bundle) throw new Error('Pass a local PineTS browser bundle as the first argument.');
const source = fs.readFileSync(process.env.PINE_PROFILE_SOURCE || "sector-pulse-v1.pine", "utf8");

const archive = 'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json';
const rows = JSON.parse(fs.readFileSync(archive, 'utf8')).rows.slice(-18000);
const nativeContext = process.env.PINE_PROFILE_NATIVE_CONTEXT === "1";
const runtime = nativeContext ? globalThis : vm.createContext({console, setTimeout, clearTimeout, structuredClone});
runtime.self = runtime;
if (nativeContext) vm.runInThisContext(fs.readFileSync(bundle, "utf8"));
else vm.runInContext(fs.readFileSync(bundle, "utf8"), runtime);

const symbol = 'NSE:NIFTY50-INDEX';
const frames = new Map();
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
      timezone: 'Asia/Kolkata', mintick: .05, session: 'regular', currency: 'INR'};
  },
  async getMarketData(ticker, timeframe, limit, start, end) {
    assert.ok([symbol, 'NIFTY50-INDEX'].includes(ticker), 'Unexpected instrument: ' + ticker);
    const interval = String(timeframe);
    assert.match(interval, /^(?:\d+|1[DWM])$/);
    if (!frames.has(interval)) frames.set(interval, aggregate(interval));
    return frames.get(interval).filter(bar =>
      (start == null || bar.openTime >= start) && (end == null || bar.openTime <= end)).slice(-(limit || 5000));
  }
};


const timings = [];
const original = provider.getMarketData;
provider.getMarketData = async (...args) => {
  const start = performance.now();
  const result = await original(...args);
  timings.push({interval: args[1], rows: result.length, elapsed_ms: performance.now()-start});
  return result;
};
(async () => {
  const output = {native_context: nativeContext, fixture: archive, source_rows: rows.length, worker_sha256: crypto.createHash("sha256").update(fs.readFileSync(bundle)).digest("hex"), runs: []};
  for (const count of (process.env.PINE_PROFILE_COUNTS || "100,400").split(",").map(Number)) {
    const start = performance.now();
    const indicator = new runtime.PineTSLib.Indicator(source);
    const compiled = performance.now();
    const engine = new runtime.PineTS(provider, symbol, "5", count);
    let context;
    try {context = await engine.run(indicator);} finally {if(process.env.PINE_PROFILE_DUMP) fs.writeFileSync(process.env.PINE_PROFILE_DUMP,String(engine.transpiledCode));}
    const evaluated = performance.now();
    const serialized = JSON.stringify(context.plots);
    output.runs.push({count, declaration_ms: compiled-start, evaluation_ms: evaluated-compiled, serialization_ms: performance.now()-evaluated, payload_bytes: Buffer.byteLength(serialized), plots_sha256: crypto.createHash("sha256").update(serialized).digest("hex"), requests: timings.splice(0)});
  }
  console.log(JSON.stringify(output, null, 2));
})().catch(error => {if(process.env.PINE_PROFILE_CAPTURE_ERROR === "1") console.log(JSON.stringify({status:"ERROR",name:error.name,message:error.message})); else console.error(error); process.exitCode=1;});
