"""Stage bounded, scope-safe Pine reference recovery on fresh owner snapshots."""
from pathlib import Path
import hashlib,json
out=Path('.private/chart-order-rollouts/pine-auto-recovery-20261119');out.mkdir(exist_ok=True,parents=True)
owners=json.loads(Path('.private/chart-order-rollouts/fyers-pine-forming-reference-20261119/manifest.json').read_text())['sources']
helper="""  function chartHistoryRetryAfter(response, body, now = Date.now()) {
    const header = response.headers?.get?.('Retry-After');
    const values = [header, body?.retry_after];
    let delay = 0;
    for (const value of values) {
      if (typeof value !== 'string' && typeof value !== 'number') continue;
      if (value === '') continue;
      const seconds = Number(value);
      const candidate = Number.isFinite(seconds) && seconds >= 0
        ? seconds * 1000 : typeof value === 'string' ? Date.parse(value) - now : NaN;
      if (Number.isFinite(candidate) && candidate >= 0) delay = Math.max(delay, candidate);
    }
    return delay || (response.status === 429 ? 60000 : 0);
  }

  function pineReferenceRetryDelay(error, attempts) {
    if (error?.authRequired || error?.name === 'AbortError' || attempts >= 4) return null;
    if (error?.historyTransient !== true && ![429, 502, 503, 504].includes(error?.status)) return null;
    const delay = Math.max([5000, 15000, 30000, 60000][attempts], error.retryAfterMs || 0);
    return Number.isFinite(delay) && delay <= 2147483647 ? delay : null;
  }

  function waitForChartRetry(delay, scope) {
    scope.throwIfAborted();
    return new Promise((resolve, reject) => {
      let timer;
      const abort = () => { clearTimeout(timer); reject(scope.reason); };
      scope.addEventListener('abort', abort, {once: true});
      timer = setTimeout(() => {
        scope.removeEventListener('abort', abort);
        resolve();
      }, delay);
    });
  }

"""
def change(text):
 replacements=[
 ('  async function requestChartHistory(path, scope) {',helper+'  async function requestChartHistory(path, scope) {'),
 ("      await new Promise(resolve => setTimeout(resolve, 1500));","      const delay = Math.max(1500, error.retryAfterMs || (error.status === 429 ? 60000 : 0));\n      if (delay > 10000) throw error;\n      await waitForChartRetry(delay, scope);"),
 ("throw Object.assign(new Error(message), { status: response.status, authRequired });","throw Object.assign(new Error(message), { status: response.status, authRequired, retryAfterMs: chartHistoryRetryAfter(response, body) });"),
 ("if (deadline.aborted && !scope.aborted) throw new Error('Broker data request timed out.');","if (deadline.aborted && !scope.aborted) throw Object.assign(new Error('Broker data request timed out.'), {historyTransient: true});\n      if (!scope.aborted && error instanceof TypeError) error.historyTransient = true;"),
 ('  const pineRestoreRequests = new WeakMap();','  const pineRestoreRequests = new WeakMap();\n  const pineRestoreRetries = new WeakMap();'),
 ("    const request = pineRestoreRequests.get(study);\n    pineRestoreRequests.delete(study);","    const retry = pineRestoreRetries.get(study);\n    clearTimeout(retry?.timer);\n    pineRestoreRetries.delete(study);\n    const request = pineRestoreRequests.get(study);\n    pineRestoreRequests.delete(study);"),
 ("      const request = {scope, chartType, source, controller};","""      const inputKey = JSON.stringify(study.inputs ?? {});
      let retry = pineRestoreRetries.get(study);
      if (!retry || retry.scope !== scope || retry.active !== active || retry.symbol !== symbol
          || retry.interval !== interval || retry.chartType !== chartType || retry.source !== source
          || retry.inputKey !== inputKey) {
        clearTimeout(retry?.timer);
        retry = {scope, active, symbol, interval, chartType, source, inputKey, attempts: 0, timer: null};
        pineRestoreRetries.set(study, retry);
      } else {
        clearTimeout(retry.timer);
        retry.timer = null;
      }
      signal.addEventListener('abort', () => {
        if (pineRestoreRetries.get(study) !== retry) return;
        clearTimeout(retry.timer);
        pineRestoreRetries.delete(study);
      }, {once: true});
      const request = {scope, chartType, source, controller};"""),
 ("      const publish = (plots, bricks, historyStart, replayThrough) => {\n        if (!current()) return;\n        pineRestoreStatus.delete(study);","      const publish = (plots, bricks, historyStart, replayThrough) => {\n        if (!current()) return;\n        clearTimeout(retry.timer);\n        retry.timer = null;\n        retry.attempts = 0;\n        pineRestoreStatus.delete(study);"),
 ("        pineRestoreStatus.set(study, error.message);\n        drawLegend();","""        const delay = pineReferenceRetryDelay(error, retry.attempts);
        if (delay !== null) {
          retry.attempts++;
          retry.timer = setTimeout(() => {
            retry.timer = null;
            if (current()) restoreWorkerPine(scope, study);
          }, delay);
        }
        pineRestoreStatus.set(study, error.message + (delay !== null
          ? ' Retrying automatically in ' + Math.ceil(delay / 1000) + 's.' : ''));
        drawLegend();"""),
 ("      const requestedCandles = new Map();","      const requestedCandles = new Map();\n      const referenceFailures = new Map();"),
 ("          if (data.ok !== true) finish(new Error(data.error || 'Pine calculation failed.'));","""          if (data.ok !== true) {
            const error = new Error(data.error || 'Pine calculation failed.');
            for (const [message, details] of referenceFailures) {
              if (error.message.includes(message)) { Object.assign(error, details); break; }
            }
            finish(error);
          }"""),
 ("          reply = {error: broker.name + ' · ' + intervalLabel(interval) + ' Pine candles · ' + error.message};","""          const message = broker.name + ' · ' + intervalLabel(interval) + ' Pine candles · ' + error.message;
          referenceFailures.set(message, {status: error.status, authRequired: error.authRequired,
            historyTransient: error.historyTransient, retryAfterMs: error.retryAfterMs});
          reply = {error: message};""")]
 replacements.append(('&& study.source === source && !settings.hideStudies && studyVisible(study);','&& study.source === source && chartPrefix === sourcePrefix\n        && JSON.stringify(study.inputs ?? {}) === inputKey && !settings.hideStudies && studyVisible(study);'))
 replacements.append(('retry.active !== active || retry.symbol !== symbol','retry.active !== active || retry.sourcePrefix !== sourcePrefix || retry.symbol !== symbol'))
 replacements.append(('retry = {scope, active, symbol, interval, chartType, source, inputKey, attempts: 0, timer: null};','retry = {scope, active, sourcePrefix, symbol, interval, chartType, source, inputKey, attempts: 0, timer: null};'))
 for old,new in replacements:
  if text.count(old)!=1:raise ValueError(f'Expected one replacement: {old[:80]} count={text.count(old)}')
  text=text.replace(old,new)
 return text
plan={'status':'STAGED_CURRENT_SNAPSHOTS','sources':[]}
for index,entry in enumerate(owners):
 path=Path(entry['path']);text=path.read_text();candidate=out/f'owner-{index}.js'
 candidate.write_text(change(text));(out/f'owner-{index}.backup.js').write_text(text)
 plan['sources'].append({'path':str(path),'base_sha256':hashlib.sha256(text.encode()).hexdigest(),'candidate':str(candidate),'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest()})
(out/'manifest.json').write_text(json.dumps(plan,indent=2));print('staged',len(plan['sources']))
