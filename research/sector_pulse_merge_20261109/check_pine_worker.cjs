const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {Worker} = require('node:worker_threads');

async function verify() {
  const [bundlePath, fixturePath] = process.argv.slice(2);
  const {frames, ...input} = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
  const bundle = fs.readFileSync(bundlePath, 'utf8');
  const adapter = fs.readFileSync(path.join(__dirname, 'pine_replay_worker.js'), 'utf8');
  const bootstrap = `
    const {parentPort} = require('node:worker_threads');
    const vm = require('node:vm');
    const scope = {console, structuredClone, setTimeout, clearTimeout,
      postMessage: message => parentPort.postMessage(message)};
    scope.self = scope;
    vm.runInNewContext(${JSON.stringify(bundle + '\n' + adapter)}, scope);
    parentPort.on('message', data => scope.onmessage({data}));
  `;
  const worker = new Worker(bootstrap, {eval:true});
  const requested = new Set();
  let timer;
  try {
    const plots = await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(new Error('Pine worker timed out')), 90000);
      worker.once('error', reject);
      worker.once('exit', code => reject(new Error('Pine worker exited with code ' + code)));
      worker.on('message', message => {
        if (message.type === 'candles') {
          const {id, interval, start, end, limit} = message;
          const rows = frames[String(interval)];
          if (!rows) {
            worker.postMessage({type:'candles-result', id, error:'Missing fixture interval ' + interval});
            return;
          }
          requested.add(String(interval));
          const window = rows.filter(bar =>
            (start == null || bar.openTime >= start) && (end == null || bar.openTime <= end)
          ).slice(-(limit || 5000));
          worker.postMessage({type:'candles-result', id, rows:window});
        } else if (message.ok) resolve(message.plots);
        else reject(new Error(message.error));
      });
      worker.postMessage(input);
    });
    assert.deepEqual([...requested].sort(), Object.keys(frames).sort());
    const tables = plots.__tables__.data.at(-1).value.filter(table => !table._deleted);
    assert.equal(tables.length, 2);
    const levels = tables.find(table => table.cells[0][0].text === 'Levels · IST');
    const captions = levels.cells.map(row => row[0]?.text);
    for (const caption of ['X 09:15–09:20', 'R 09:20–09:25', 'M 12:30–13:00']) {
      assert.ok(captions.includes(caption), 'Missing ' + caption);
    }
    console.log('Verified on-demand archived FYERS candles across', requested.size, 'intervals and both V1 tables');
  } finally {
    clearTimeout(timer);
    await worker.terminate();
  }
}

verify().catch(error => { console.error(error.message); process.exitCode = 1; });
