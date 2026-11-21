let started = false;
let runtime;
let context;
let refreshing = false;
let updateRequested = false;
let resetRequested = false;
let runFromHistory;

function publishPlots(type) {
  const plots = JSON.parse(JSON.stringify(context.plots));
  self.postMessage({type, ok: true, plots});
}

async function refresh(reset = false) {
  resetRequested ||= reset;
  updateRequested = true;
  if (!context || refreshing) return;
  refreshing = true;
  try {
    while (updateRequested) {
      updateRequested = false;
      if (resetRequested) {
        resetRequested = false;
        context = await runFromHistory();
        publishPlots('updated');
      } else if (await runtime.updateTail(context)) {
        if (!resetRequested) publishPlots('updated');
      } else {
        self.postMessage({type: 'updated', ok: true});
      }
    }
  } catch (error) {
    self.postMessage({type: 'updated', ok: false, error: error.message});
  } finally {
    refreshing = false;
  }
}
let requestId = 0;
const pending = new Map();

function requestCandles(ticker, interval, limit, start, end) {
  return new Promise((resolve, reject) => {
    const id = ++requestId;
    pending.set(id, {resolve, reject});
    self.postMessage({type: 'candles', id, ticker, interval, limit, start, end});
  });
}
self.onmessage = async ({data}) => {
  if (data.type === 'candles-result') {
    const request = pending.get(data.id);
    if (!request) return;
    pending.delete(data.id);
    if (data.error) request.reject(new Error(data.error));
    else if (Array.isArray(data.rows)) request.resolve(data.rows);
    else request.reject(new Error('Invalid candle response'));
    return;
  }
  if (data.type === 'refresh') return refresh(data.reset === true);
  if (started) return;
  started = true;
  try {
    const {source, symbolInfo, frames, timeframe, count} = data;
    // Markerless PineTS source is interpreted as JavaScript by the runtime.
    const version = typeof source === 'string' && source.match(/^\s*\/\/\s*@version\s*=\s*(\d+)\s*$/im);
    if (!version || ![5, 6].includes(Number(version[1]))) {
      throw new Error('Start the script with //@version=5 or //@version=6.');
    }

    const provider = {
      configure() {},
      async getSymbolInfo() { return symbolInfo; },
      async getMarketData(ticker, interval, limit, start, end) {
        if (![symbolInfo.tickerid, symbolInfo.ticker].includes(ticker)) {
          throw new Error('No replay data for ' + ticker);
        }
        if (!frames) return requestCandles(ticker, interval, limit, start, end);
        const candles = frames[String(interval)];
        if (!candles) throw new Error('No replay candles for interval ' + interval);
        return candles.filter(bar =>
          (start == null || bar.openTime >= start) && (end == null || bar.openTime <= end)
        ).slice(-(limit || 5000));
      }
    };
    runFromHistory = async () => {
      runtime = new self.PineTS(provider, symbolInfo.tickerid, timeframe, count);
      return runtime.run(source);
    };
    context = await runFromHistory();
    if (!resetRequested) publishPlots('ready');
    if (updateRequested) await refresh();
  } catch (error) {
    self.postMessage({ok: false, error: error.message});
  }
};
