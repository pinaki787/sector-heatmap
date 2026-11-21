from pathlib import Path
import json,hashlib
p=Path('.private/chart-order-rollouts/pine-auto-recovery-20261119')
m=json.loads((p/'manifest.json').read_text())
wrapper="""  async function runChartPine(source, signal, onUpdate, isCurrent, onError, onProgress, inputs) {
    return new Promise((resolve, reject) => {
      let initialDone = false, attempts = 0, recovering = false;
      const terminal = error => {
        if (!initialDone) { initialDone = true; reject(error); }
        else if (!signal.aborted && isCurrent()) onError?.(error);
      };
      const recover = async error => {
        if (recovering) return;
        if (signal.aborted || !isCurrent()) { terminal(signal.reason ?? error); return; }
        const delay = pineReferenceRetryDelay(error, attempts);
        if (delay === null) {
          if (attempts >= 4) error.recoveryExhausted = true;
          terminal(error); return;
        }
        recovering = true; attempts++;
        onProgress?.(error.message + ' Retrying automatically in ' + Math.ceil(delay / 1000) + 's.', true);
        try {
          await waitForChartRetry(delay, signal);
          recovering = false;
          if (!isCurrent()) { terminal(Object.assign(new Error('Chart context changed.'), {name: 'AbortError'})); return; }
          void start();
        } catch (cancelled) {
          recovering = false; terminal(cancelled);
        }
      };
      const updated = (...args) => { attempts = 0; onUpdate?.(...args); };
      const start = async () => {
        try {
          const result = await runChartPineOnce(source, signal, onUpdate ? updated : undefined,
            isCurrent, error => { void recover(error); }, onProgress, inputs);
          if (signal.aborted || !isCurrent()) return;
          attempts = 0;
          if (!initialDone) { initialDone = true; resolve(result); }
          else onUpdate?.(result.plots, result.bricks, result.historyStart, result.replayThrough);
        } catch (error) { await recover(error); }
      };
      void start();
    });
  }

"""
for i,e in enumerate(m['sources']):
 path=Path(e['path']);s=path.read_text()
 assert hashlib.sha256(path.read_bytes()).hexdigest()==e['candidate_sha256']
 (p/f'owner-{i}.recovery-v1.backup.js').write_text(s)
 old='  async function runChartPine(source, signal, onUpdate, isCurrent, onError, onProgress, inputs) {'
 assert s.count(old)==1;s=s.replace(old,wrapper+old.replace('runChartPine(', 'runChartPineOnce('))
 s=s.replace("if (error?.authRequired || error?.name === 'AbortError' || attempts >= 4) return null;","if (error?.authRequired || error?.recoveryExhausted || error?.name === 'AbortError' || attempts >= 4) return null;")
 old="""      const progress = message => {
        if (!current() || pineRestoreProgress.get(study) === message) return;
        pineRestoreProgress.set(study, message);
        drawLegend();
      };"""
 new="""      const progress = (message, recovering = false) => {
        if (!current() || pineRestoreProgress.get(study) === message) return;
        if (recovering) pineRestoreStatus.set(study, 'Calculating…');
        pineRestoreProgress.set(study, message);
        drawLegend();
      };"""
 assert s.count(old)==1;s=s.replace(old,new)
 old="""            if (!applied || !current()) return;
            publishWorkerPineResult(applied, {source, symbol, interval, chartPrefix: sourcePrefix, chartType: chartTypeAtApply, plots, bricks, historyStart, replayThrough});"""
 new="""            if (!applied || !current()) return;
            pineRestoreStatus.delete(applied);
            pineRestoreProgress.delete(applied);
            publishWorkerPineResult(applied, {source, symbol, interval, chartPrefix: sourcePrefix, chartType: chartTypeAtApply, plots, bricks, historyStart, replayThrough});"""
 assert s.count(old)==1;s=s.replace(old,new)
 old="""          }, progress => {
            if (current() && !applied) {
              lastProgress = progress;
              if (message.textContent !== progress) message.textContent = progress;
            }
          }, inputOverrides)"""
 new="""          }, (progress, recovering = false) => {
            if (!current()) return;
            if (!applied) {
              lastProgress = progress;
              if (message.textContent !== progress) message.textContent = progress;
            } else if (recovering) {
              pineRestoreStatus.set(applied, progress);
              drawLegend();
            }
          }, inputOverrides)"""
 assert s.count(old)==1;s=s.replace(old,new)
 candidate=p/f'owner-{i}.v2.js';candidate.write_text(s)
 e.update(base_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),candidate=str(candidate),candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
m.update(status='V2_STAGED_FOR_INITIAL_AND_LIVE_RECOVERY')
(p/'manifest.json').write_text(json.dumps(m,indent=2))
