const fs=require('fs'),assert=require('node:assert/strict'),{JSDOM}=require(process.env.RENKO_JSDOM_MODULE||'/tmp/renko-family-dom/node_modules/jsdom');
(async()=>{
for(const broker of ['FYERS','DHAN','DELTA_INDIA'])for(const saved of [false,true]){
const dom=new JSDOM('<html><head></head><body><button data-view="ema-cross"></button><main class="work"></main></body></html>',{url:'https://example.test/?renkoBroker='+broker,runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;
w.setInterval=()=>1;w.ResizeObserver=class{observe(){} disconnect(){}};w.EventSource=class{addEventListener(){} close(){}};
w.DeltaINR={load:async()=>{},format:v=>String(v),note:()=>'',source:()=>'',set:()=>{}};
const fields={'higher-timeframe-enabled':false,'retest-enabled':false,'rsi-level-enabled':false,'rsi-level-enabled-indicator':false,'rsi-bullish-max':66,'volume-enabled':false,'rsi-sma-enabled':false,'structure-family-enabled':true,'zones-family-enabled':true};
if(saved)w.localStorage.setItem('sector-pulse:renko-supertrend-settings-v3'+(broker==='DELTA_INDIA'?':DELTA_INDIA':''),JSON.stringify(fields));
w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>null,route:(s,u)=>u,fetch:async(_s,u)=>({ok:true,json:async()=>u.includes('runner?')?{indicator_family_revision:'indicator-family-masters-v1',indicator_selection_revision:'independent-indicators-v1',runtime_revision:'renko-supertrend-assessment-recovery-v14',running:false,status:'STOPPED',config:{mode:'PAPER'},pnl:{}}:u.includes('settings?')?{settings:{},saved_at:0}:{items:[],matches:[],instruments:[]}})};
w.eval(fs.readFileSync('renko-supertrend.js','utf8'));await w.RenkoSupertrend.mount('renko-supertrend');await new Promise(r=>setTimeout(r,30));
const el=id=>w.document.getElementById('renko-'+id);
for(const id of ['retest-enabled','rsi-level-enabled','rsi-level-enabled-indicator','volume-enabled','rsi-sma-enabled'])assert.equal(el(id).checked,!saved,broker+' '+id);
assert.equal(el('higher-timeframe-enabled').checked,true);assert.equal(el('higher-timeframe-enabled-indicator').checked,true);assert.equal(el('brick-mode').value,'Manual');assert.equal(el('sideways-enabled').checked,true);assert.equal(el('sideways-max-candles').value,'2');assert.equal(el('supertrend-timeframe').value,'5 minutes');
assert.equal(el('rsi-bullish-max').value,saved?'66':'70');assert.equal(el('rsi-bullish-min').value,'60');
for(const id of ['structure-family-enabled','zones-family-enabled'])assert.equal(el(id).checked,saved,broker+' '+id);
assert.equal(el('rsi-bullish-max').disabled,false);assert.equal(el('rsi-level-enabled-indicator').disabled,false);
el('rsi-bullish-max').value='72';el('rsi-level-enabled-indicator').checked=false;
assert.equal(el('rsi-bullish-max').value,'72');assert.equal(el('rsi-level-enabled').checked,!saved);
w.close();console.log(broker,saved?'saved preserved':'new defaults PASS');
}
})().catch(e=>{console.error(e);process.exitCode=1});

