const fs = require('node:fs');
const {runPineWorker} = require('./pine_worker_session.cjs');
const {chartFrame} = require('./pine_chart_frame.cjs');
const {attachPinePriceOverlay} = require('./pine_price_overlay.cjs');

const [replayPath, outputPath, bundlePath, fixturePath] = process.argv.slice(2);
if (!replayPath || !outputPath) throw new Error('Pass the replay JSON and a new HTML output path.');
const frame = chartFrame(JSON.parse(fs.readFileSync(replayPath, 'utf8')));
const workerCode = bundlePath && fs.readFileSync(bundlePath, 'utf8') + '\n'
  + fs.readFileSync(require('node:path').join(__dirname, 'pine_replay_worker.js'), 'utf8');
const fixture = fixturePath ? JSON.parse(fs.readFileSync(fixturePath, 'utf8')) : null;
const embed = value => JSON.stringify(value).replace(/</g, '\\u003c');
const library = fs.readFileSync('vendor/lightweight-charts-4.2.3.js', 'utf8');
const page = `<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIFTY 50 · Sector Pulse V1</title>
<style>
body { margin: 0; background: #131722; color: #d1d4dc; font: 14px system-ui; }
header { padding: 14px; border-bottom: 1px solid #2a2e39; }
header button { float: right; background: #242a37; border: 1px solid #434651; border-radius: 4px; color: inherit; }
#data-window { position: absolute; z-index: 5; left: 10px; top: 12px; padding: 10px; max-width: calc(100% - 40px); background: #171b26; border: 1px solid #434651; }
#data-window dl { display: grid; grid-template-columns: minmax(0, 1fr) auto; column-gap: 14px; row-gap: 4px; margin-bottom: 0; }
#data-window dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }

#editor { padding: 8px; }
#editor textarea { display: block; width: min(100%, 850px); box-sizing: border-box; min-height: 130px; }
main { position: relative; width: 100vw; height: calc(100vh - 50px); }
#chart { position: absolute; inset: 0; }
table { z-index: 4; position: absolute; right: 78px; border-collapse: collapse; font-size: 11px; }
td { padding: 3px 5px; text-align: center; }
@media (max-width: 620px) {
  main { height: 60vh; }
  .tables { position: relative; top: 100%; padding: 8px; display: grid; gap: 8px; justify-items: start; }
  table { position: static; font-size: 10px; }
  td { padding: 2px 3px; }
}
</style>
<header>NIFTY 50 · 5m · FYERS <span style="color:#959daf"> · Archived replay · IST</span><button type="button" aria-expanded="false" aria-controls="data-window">Data Window</button></header>
${fixture ? '<details id="editor"><summary>Pine Editor</summary><textarea aria-label="Pine Script" spellcheck="false"></textarea><button type="button">Add to chart</button> <output role="status"></output></details>' : ''}
<main><div id="chart"></div><div class="tables"></div><aside id="data-window" hidden><strong>Data Window</strong> <time></time><dl></dl></aside></main>
<script>${library.replace(/<\/script/gi, '<\\/script')}</script>
<script>
let frame = ${JSON.stringify(frame).replace(/</g, '\\u003c')};
const stage = document.querySelector('main');
const exchangeTime = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
});
const formatTime = time => exchangeTime.format(new Date(time * 1000));
const chart = LightweightCharts.createChart(document.querySelector('#chart'), {
  autoSize: true, layout: {background: {color:'#131722'}, textColor:'#b2b5be'},
  grid: {vertLines: {color:'#222631'}, horzLines: {color:'#222631'}},
  localization: {timeFormatter:formatTime},
  timeScale: {timeVisible:true, rightOffset:6,
    tickMarkFormatter:(time, type) => type >= 3 ? formatTime(time) : null}
});
const candles = chart.addCandlestickSeries({
  upColor:'#26a69a', downColor:'#ef5350', borderVisible:false,
  wickUpColor:'#26a69a', wickDownColor:'#ef5350'
});
const studySeries = [];
function renderSeries() {
  for (const series of studySeries.splice(0)) chart.removeSeries(series);
  candles.setData(frame.bars);
  for (const plot of frame.plots) {
  if (!(plot.display & 3) || plot.options.style === 'fill' ||
      !plot.points.some(point => Number.isFinite(point.value))) continue;
  const series = chart.addLineSeries({color:plot.options.color || '#2962ff',
    lineWidth:plot.options.linewidth || 1, priceLineVisible:false,
    lineVisible:Boolean(plot.display & 1), lastValueVisible:Boolean(plot.display & 2),
    autoscaleInfoProvider:() => null});
  series.setData(plot.points);
  studySeries.push(series);
  }
}
renderSeries();
const scale = chart.timeScale();
const plotValues = () => new Map(frame.plots.map(plot => [plot.id, new Map(plot.points.map(point => [point.time, point.value]))]));
let seriesById = plotValues();
const inspector = document.querySelector('#data-window');
const inspectorButton = document.querySelector('header button');

const price = new Intl.NumberFormat('en-IN', {maximumFractionDigits: 2});
let cursorTime = frame.bars.at(-1)?.time;
function inspect() {
  if (inspector.hidden) return;
  inspector.querySelector('time').textContent = cursorTime === undefined ? '' : formatTime(cursorTime);
  const fields = frame.plots.flatMap(plot => {
    if (!(plot.display & 4) || plot.options.style === 'fill') return [];
    const value = seriesById.get(plot.id)?.get(cursorTime);
    if (!Number.isFinite(value)) return [];
    const term = document.createElement('dt');
    const data = document.createElement('dd');
    term.textContent = plot.title || plot.id;
    data.textContent = price.format(value);
    return [term, data];
  });
  inspector.querySelector('dl').replaceChildren(...fields);
}
inspectorButton.addEventListener('click', () => {
  inspector.hidden = !inspector.hidden;
  inspectorButton.setAttribute('aria-expanded', String(!inspector.hidden));
  inspect();
});
chart.subscribeCrosshairMove(({time}) => {
  cursorTime = time ?? frame.bars.at(-1)?.time;
  inspect();
});
const overlay = (${attachPinePriceOverlay.toString()})({chart, candles, frame});
function renderTables() {
const tables = stage.querySelector('.tables');
tables.replaceChildren();
for (const info of frame.objects.tables) {
  const table = document.createElement('table');
  table.style.top = info.position.startsWith('middle') ? '36%' : '12px';
  table.style.backgroundColor = info.bgcolor || 'transparent';
  if (info.frame_width && info.frame_color) table.style.border = info.frame_width + 'px solid ' + info.frame_color;
  info.cells.forEach((row, rowIndex) => {
    if (!row.some(cell => cell?.text)) return;
    const tr = table.insertRow();
    row.forEach((cell, column) => {
      if (cell?._merged) return;
      const td = tr.insertCell();
      td.textContent = cell?.text || '';
      td.title = cell?.tooltip || '';
      td.style.color = cell?.text_color || '';
      td.style.backgroundColor = cell?.bgcolor || '';
      const merge = (info.merges || []).find(item => item.startRow === rowIndex && item.startCol === column);
      if (merge) {
        td.colSpan = merge.endCol - column + 1;
        td.rowSpan = merge.endRow - rowIndex + 1;
      }
    });
  });
  stage.querySelector(".tables").append(table);
}
}
renderTables();
scale.setVisibleLogicalRange({from:frame.bars.length - 150,to:frame.bars.length + 6});
const fixture = ${embed(fixture)};
if (fixture) {
  const editor = document.querySelector('#editor');
  const textarea = editor.querySelector('textarea');
  const button = editor.querySelector('button');
  const output = editor.querySelector('output');
  textarea.value = fixture.source;
  const workerCode = ${embed(workerCode ?? null)};
  const chartFrame = (() => {
    const drawings = ['lines', 'boxes', 'labels', 'linefills', 'polylines', 'tables'];
    const displayMask = ${require('./pine_chart_frame.cjs').displayMask.toString()};
    return ${chartFrame.toString()};
  })();
  const runPineWorker = ${runPineWorker.toString()};
  button.addEventListener('click', async () => {
    button.disabled = true;
    output.value = 'Calculating…';
    const scope = new AbortController();
    const {frames, source, ...input} = fixture;
    const url = URL.createObjectURL(new Blob([workerCode], {type: 'text/javascript'}));
    try {
      const plots = await runPineWorker({
        createWorker: () => new Worker(url),
        input: {...input, source: textarea.value}, signal: scope.signal,
        async loadCandles({interval, start, end, limit}) {
          const rows = frames[interval];
          if (!rows) throw new Error('No archive candles for ' + interval);
          return rows.filter(row => (start == null || row.openTime >= start)
            && (end == null || row.openTime <= end)).slice(-(limit || 5000));
        }
      });
      frame = chartFrame({candles: frames[input.timeframe].slice(-input.count), plots});
      renderSeries();
      seriesById = plotValues();
      overlay.update(frame);
      renderTables();
      inspect();
      output.value = 'Applied to chart';
    } catch (error) {
      output.value = error.message;
    } finally {
      URL.revokeObjectURL(url);
      button.disabled = false;
    }
  });
}
</script>`;
fs.writeFileSync(outputPath, page, {flag:'wx'});
