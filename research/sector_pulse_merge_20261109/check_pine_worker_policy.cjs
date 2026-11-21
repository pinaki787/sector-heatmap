const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {spawn} = require('node:child_process');
const os = require('node:os');

async function verify(bundlePath) {
  const bundle = fs.readFileSync(bundlePath, 'utf8');
  const adapter = process.argv.includes('--combined') ? ''
    : fs.readFileSync(path.join(__dirname, 'pine_replay_worker.js'), 'utf8');
  const worker = bundle + '\n' + adapter + `
    fetch('/unexpected').then(
      () => self.postMessage({networkBlocked:false}),
      () => self.postMessage({networkBlocked:true})
    );
  `;
  let unexpected = 0;
  const server = http.createServer((req, res) => {
    if (req.url === '/worker.js') {
      res.setHeader('Content-Type', 'text/javascript');
      res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-eval'; connect-src 'none'");
      res.end(worker);
    } else if (req.url === '/') {
      res.setHeader('Content-Type', 'text/html');
      res.end(`<!doctype html><body>Running<script>
        const worker = new Worker('/worker.js');
        let blocked, value;
        worker.onmessage = ({data}) => {
          if ('networkBlocked' in data) blocked = data.networkBlocked;
          else if (data.type === 'candles') {
            const now = Date.now();
            worker.postMessage({type:'candles-result', id:data.id,
              rows:[{openTime:now - 300000,closeTime:now,open:42,high:42,low:42,close:42,volume:1}]});
          } else if (data.ok) value = data.plots.Close.data.at(-1).value;
          else document.body.dataset.error = data.error;
          if (blocked !== undefined && value !== undefined) {
            document.body.dataset.result = JSON.stringify({blocked,value});
          }
        };
        worker.postMessage({source:'//@version=6\\nindicator("Policy")\\nplot(close, "Close")',
          timeframe:'5',count:1,symbolInfo:{tickerid:'PAXGUSD',ticker:'PAXGUSD',timezone:'UTC'}});
      </script>`);
    } else {
      if (req.url === '/unexpected') unexpected++;
      res.writeHead(404).end();
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'sp-pine-policy-'));
  try {
    const browser = spawn('google-chrome', ['--headless','--no-sandbox','--disable-gpu',
      '--user-data-dir=' + profile, '--remote-debugging-port=0',
      'http://127.0.0.1:' + server.address().port + '/'], {stdio:'ignore'});
    const pause = () => new Promise(resolve => setTimeout(resolve, 100));
    const activePort = path.join(profile, 'DevToolsActivePort');
    try {
      for (let i = 0; i < 80 && !fs.existsSync(activePort); i++) await pause();
      const port = fs.readFileSync(activePort, 'utf8').split('\n')[0];
      const targets = await fetch('http://127.0.0.1:' + port + '/json/list').then(response => response.json());
      const socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
      await new Promise((resolve, reject) => {socket.onopen = resolve;socket.onerror = reject;});
      try {
        const read = id => new Promise(resolve => {
          const listener = ({data}) => {
            const message = JSON.parse(data);
            if (message.id !== id) return;
            socket.removeEventListener('message', listener);
            resolve(message.result.result.value);
          };
          socket.addEventListener('message', listener);
          socket.send(JSON.stringify({id,method:'Runtime.evaluate',params:{
            expression:'document.body?.dataset.result || document.body?.dataset.error',
            returnByValue:true
          }}));
        });
        let result;
        for (let i = 0; i < 100 && !result; i++) {
          result = await read(i + 1);
          if (!result) await pause();
        }
        assert.equal(result, JSON.stringify({blocked:true,value:42}));
        assert.equal(unexpected, 0);
        console.log('Pine calculated from parent-supplied candles and direct worker fetch was blocked');
      } finally {socket.close();}
    } finally {
      if (browser.exitCode === null && browser.signalCode === null) {
        const closed = new Promise(resolve => browser.once('close', resolve));
        browser.kill();
        await closed;
      }
    }
  } finally {
    server.close();
    fs.rmSync(profile, {recursive:true,force:true});
  }
}
verify(process.argv[2]).catch(error => { console.error(error.message); process.exitCode = 1; });
