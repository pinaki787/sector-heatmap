function runPineWorker({createWorker, input, loadCandles, signal, timeoutMs = 90000, subscribe, onUpdate, onError}) {
  signal.throwIfAborted();
  const worker = createWorker();
  const scope = new AbortController();
  return new Promise((resolve, reject) => {
    const abort = () => finish(signal.reason);
    const timeout = setTimeout(() => finish(new Error('Pine calculation timed out')), timeoutMs);
    let finished = false;
    let ready = false;
    let unsubscribe;

    function finish(error, plots) {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      signal.removeEventListener('abort', abort);
      worker.onmessage = worker.onerror = null;
      unsubscribe?.();
      scope.abort();
      worker.terminate();
      if (ready) {
        if (error && !signal.aborted) onError?.(error);
      } else if (error) reject(error);
      else resolve(plots);
    }

    signal.addEventListener('abort', abort, {once: true});
    worker.onerror = event => finish(new Error(event.message || 'Pine worker failed'));
    worker.onmessage = async ({data}) => {
      if (data.type === 'candles') {
        try {
          const rows = await loadCandles(data, scope.signal);
          if (!finished) worker.postMessage({type: 'candles-result', id: data.id, rows});
        } catch (error) {
          if (!finished) worker.postMessage({type: 'candles-result', id: data.id, error: error.message});
        }
        return;
      }
      if (data.ok !== true) {
        finish(new Error(data.error || 'Invalid Pine worker result'));
        return;
      }
      if (!subscribe) {
        finish(null, data.plots);
        return;
      }
      if (ready) {
        if (data.type === 'updated') onUpdate?.(data.plots);
        return;
      }
      try {
        unsubscribe = subscribe(({reset = false} = {}) => {
          if (!finished) worker.postMessage({type: 'refresh', reset});
        });
        ready = true;
        clearTimeout(timeout);
        resolve(data.plots);
      } catch (error) {
        finish(error);
      }
    };
    try {
      worker.postMessage(input);
    } catch (error) {
      finish(error);
    }
  });
}

module.exports = {runPineWorker};
