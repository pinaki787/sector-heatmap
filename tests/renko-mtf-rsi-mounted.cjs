/* Isolated DOM only: no live browser, network, credentials, runners or orders. */
const {JSDOM}=require('/home/trading/sector-heatmap/.private/test-node/node_modules/jsdom');
const fs=require('node:fs'),assert=require('node:assert/strict');
const code=fs.readFileSync('renko-supertrend.js','utf8');
(async()=>{
 const dom=new JSDOM('<html><head></head><body><button data-view="ema-cross"></button><main class="work"></main></body></html>',{url:'https://example.test/broker-workspace/test/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,calls=[],errors=[];const account={id:'test',broker:'FYERS'};
 const fields={symbol:'NSE:NIFTY50-INDEX',timeframe:'1 minute','brick-mode':'Auto','rsi-family-enabled':true,'rsi-level-mode':'BETWEEN','rsi-bullish-min':62,'rsi-bullish-max':78,'rsi-bearish-min':32,'rsi-bearish-max':38,'rsi-htf-1-enabled':true,'rsi-htf-1-timeframe':'5 minutes','rsi-htf-2-enabled':false,'rsi-htf-2-timeframe':'30 minutes','rsi-htf-3-enabled':true,'rsi-htf-3-timeframe':'1 hour'};
 const state={ema_third_revision:"third-ema-entry-v1",indicator_family_revision:'indicator-family-masters-v1',running:false,status:'STOPPED',config:{underlying:fields.symbol,timeframe:'1 minute',mode:'PAPER'},pnl:{},live_available:false,mtf_rsi_revision:'optional-three-htf-rsi-v2'};
 w.addEventListener('error',e=>errors.push(String(e.error||e.message)));w.AbortSignal=AbortSignal;/* Existing local manual-brick integration is outside this isolated RSI fixture. */w.deriveManualBrick=async()=>{};w.setInterval=()=>1;w.ResizeObserver=class{observe(){}disconnect(){}};w.EventSource=class{addEventListener(){}close(){}};
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[account],account:()=>account,route:(_kind,url)=>url,fetch:async(_kind,url,opts)=>{
  const body=opts?.body?JSON.parse(opts.body):null;calls.push({url,body});let data={items:[],matches:[],instances:[]};
  if(url.includes('/settings'))data=body?{settings:body.settings,saved_at:Date.now()/1000}:{settings:fields,saved_at:Date.now()/1000};
  else if(url.includes('/runner'))data=state;
  else if(url.includes('/journal'))data={trades:[]};
  return {ok:true,json:async()=>data};
 }};
 w.eval(code);await w.RenkoSupertrend.mount('sectors');await new Promise(r=>setTimeout(r,80));
 const el=id=>w.document.getElementById('renko-'+id);assert.ok(el('chart-stack').contains(el('candle-readout')));assert.ok(el('chart').contains(el('candle-readout')));
 for(let i=1;i<=3;i++){assert.ok(el('family-rsi').contains(el('rsi-htf-'+i+'-enabled')));assert.ok(el('rsi-htf-'+i+'-timeframe'));}
 assert.equal(el('rsi-htf-1-enabled').checked,true,JSON.stringify({calls,message:el('runner-message').textContent}));assert.equal(el('rsi-htf-2-enabled').checked,false);assert.equal(el('rsi-htf-3-enabled').checked,true);assert.equal(el('rsi-htf-1-timeframe').value,'5 minutes');
 assert.match(el('rsi-htf-active').textContent,/Higher-timeframe RSI OFF/);
 el('rsi-htf-2-enabled').checked=true;el('rsi-htf-2-enabled').dispatchEvent(new w.Event('change',{bubbles:true}));
 assert.equal(el('rsi-htf-1-bullish-min').value,'62');assert.equal(el('rsi-htf-3-bearish-max').value,'38');
 el('rsi-htf-2-bullish-min').value='67';el('rsi-htf-2-bullish-min').dispatchEvent(new w.Event('change',{bubbles:true}));
 assert.equal(el('rsi-htf-1-bullish-min').value,'62');assert.equal(el('rsi-bullish-min').value,'62');
 el('rsi-htf-2-timeframe').value='15 minutes';el('config-name').value='Optional RSI confirmation';
 await el('save-settings').onclick();
 const save=calls.findLast(c=>c.url.includes('/settings')&&c.body);
 assert.ok(save);assert.equal(save.body.settings['rsi-htf-2-bullish-min'],'67');assert.equal(save.body.settings['rsi-htf-2-enabled'],true);assert.equal(save.body.settings['rsi-htf-2-timeframe'],'15 minutes');
 assert.equal(state.config.rsi_htf_2_enabled,undefined);
 assert.equal(el("ema-third-enabled").checked,true);assert.equal(el("ema-third-length").value,"100");assert.equal(save.body.settings["ema-third-enabled"],true);assert.equal(save.body.settings["ema-third-length"],"100");
 const stored=w.localStorage.getItem('sector-pulse:renko-supertrend-settings-v3');assert.ok(stored);assert.equal(JSON.parse(stored)['rsi-htf-3-enabled'],true);
 assert.deepEqual(errors,[]);assert.equal(calls.some(c=>/\/(start|stop|adopt|override-entry)(?:\?|$)/.test(c.url)),false);
 console.log('Mounted three optional slots; saved choices restored; draft and runner remain separate; no lifecycle calls');dom.window.close();
})().catch(error=>{console.error(error);process.exit(1)});
