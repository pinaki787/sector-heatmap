const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('/tmp/sector-parser-test-deps/node_modules/jsdom');
function setup(){
 const d=new JSDOM('<main></main>',{url:'https://example.test',runScripts:'outside-only'}),w=d.window,record={lines:[],candles:[],ranges:[]};
 w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
 w.ResizeObserver=class{observe(){}disconnect(){}};
 w.LightweightCharts={createChart:(node,options)=>({
  addLineSeries:o=>{record.lines.push(o);return {setData(){},createPriceLine(){}};},
  addCandlestickSeries:o=>{record.candles.push(o);return {setData(){},createPriceLine(){}};},
  timeScale:()=>({fitContent(){},setVisibleLogicalRange:r=>record.ranges.push(r),getVisibleLogicalRange:()=>({from:0,to:10}),getVisibleRange:()=>({from:'2025-05-01',to:'2025-09-01'}),subscribeVisibleTimeRangeChange(){},setVisibleRange(){}}),
  subscribeCrosshairMove(){},applyOptions(){},remove(){}
 })};
 const candles=Array.from({length:250},(_,i)=>{const time=new Date(Date.UTC(2025,0,i+1)).toISOString().slice(0,10);return {time,open:100+i/10,high:101+i/10,low:99+i/10,close:100.5+i/10};});
 const chart={candles,weekly_candles:[],weekly_ema20:[],series:{rsi14:[],atr14:[]},last_session:candles.at(-1).time,basis:'Fixture public candles'};
 w.fetch=async()=>({ok:true,json:async()=>({schema:'seasonality/v1',chart})});
 w.eval(fs.readFileSync('holdings-review-tools.js','utf8'));
 return {w,d,record};
}
test('Investment chart has external EMA legend and no EMA text over the price plot',async()=>{
 const {w,d,record}=setup();await w.HoldingsReviewTools.openInvestmentChart('NSE:TEST-EQ');
 assert.equal(w.document.querySelector('#holding-evidence-chart h2').textContent,'NSE:TEST · Candlestick chart');
 assert.equal(w.document.querySelectorAll('.holding-study-key').length,6);
 assert.ok(record.lines.length>=6);for(const options of record.lines){assert.equal(options.lastValueVisible,false);assert.equal(options.title,'');assert.equal(options.priceLineVisible,false);}
 assert.match(w.document.querySelector('[data-candle-readout]').textContent,/Open .*High .*Low .*Close/);
 assert.ok(record.ranges.some(r=>r.from===130&&r.to===258));
 assert.equal(w.document.querySelector('[data-overlay="average_cost"]'),null);
 assert.equal(w.document.querySelector('[data-overlay="candidate_stop"]'),null);d.window.close();
});
test('Holdings chart and seasonality research controls stay in the symbol cell',()=>{
 const {w,d}=setup();const section=w.document.createElement('section');section.innerHTML='<table><tbody id="holdings-rows"><tr><td>Hold</td><td>TEST</td><td>10</td><td></td><td></td><td></td><td></td></tr></tbody></table>';w.document.body.append(section);
 const row={id:'r',symbol:'NSE:TEST-EQ',kind:'DELIVERY_EQUITY',action:'HOLD'};w.HoldingsReviewTools.render(section,{rows:[row],broker:'FYERS',accountId:'owned'});
 const tr=section.querySelector('tr');assert.equal(tr.children[1].querySelector('.holding-research-tools button').textContent,'View chart');assert.equal(tr.querySelector('.holding-actions-cell .holding-chart-button')?.textContent,'Automatic trailing');
 d.window.close();
});
