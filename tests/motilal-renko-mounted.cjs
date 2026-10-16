const {JSDOM}=require('/private/tmp/renko-browser-check/node_modules/jsdom');const fs=require('fs'),assert=require('assert');
const code=fs.readFileSync('renko-supertrend.js','utf8');
const symbol='NSE:NIFTY50-INDEX',key='4a8a4fa8e499c1b20def';
global.addEventListener=()=>{};global.location={href:'https://utrading.pinakicloud.com/',origin:'https://utrading.pinakicloud.com'};const {route:nativeRoute}=require('../broker-form-routing.js');const selectedAccount={id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',broker:'MOTILAL_OSWAL'};
const calls=[],errors=[],rejectedRoutes=[];
const state={running:false,status:'STOPPED',config:{underlying:symbol,timeframe:'5 minutes',mode:'LIVE',lots:2},instrument:symbol,pnl:{},live_available:true,indicator_family_revision:'indicator-family-masters-v1',indicator_selection_revision:'independent-indicators-v1',indicator_destinations_revision:'strategy-indicator-destinations-v2',runtime_revision:'renko-supertrend-assessment-recovery-v14',zone_target_revision:'strong-5m-zone-target-v1',market_structure_revision:'confirmed-host-structure-v1'};
function setup(batch){
const dom=new JSDOM('<!doctype html><html><head></head><body><button data-view="ema-cross"></button><main class="work"></main></body></html>',{url:'https://utrading.pinakicloud.com/?renkoBroker=MOTILAL_OSWAL&renkoAccount=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&renkoInstance='+key+(batch?'&renkoBatchChart=1&renkoChartSymbol='+encodeURIComponent(symbol):''),runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;w.addEventListener('error',e=>errors.push(String(e.error||e.message)));w.setInterval=()=>1;w.ResizeObserver=class{observe(){}disconnect(){}};w.EventSource=class{addEventListener(){}close(){}};w.PaperCapital={ensure:async()=>{}};w.BrokerForms={ready:Promise.resolve(),accounts:()=>[{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',broker:'MOTILAL_OSWAL'}],account:()=>({id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',broker:'MOTILAL_OSWAL'}),route:(s,u)=>u,fetch:async(_s,u,opts)=>{
 try{nativeRoute('renko',u,selectedAccount);}catch(e){rejectedRoutes.push(u);throw e;}
 const body=opts?.body?JSON.parse(opts.body):null;calls.push({batch,url:u,body});
 let d={items:[],instruments:[]};
 if(u.includes('instances'))d={instances:[{instance_key:key,broker:'MOTILAL_OSWAL',instrument:symbol,config:state.config,running:false}]};
 else if(u.includes('/runner?'))d=state;
 else if(u.includes('/settings?'))d=body?{saved_at:Date.now()/1000}:{settings:{symbol,mode:'LIVE','supertrend-family-enabled':true,'ema-family-enabled':false,'rsi-family-enabled':false,'adx-family-enabled':false,'brick-mode':'Auto'},saved_at:Date.now()/1000};
 else if(u.includes('/manual-brick?'))d={manual_brick:12.4,reference_atr:359.6,reference_bars:40,rule:{reference_seconds:52200,divisor:29},symbol};
 else if(u.includes('/start?'))d={...state,running:true,status:'WATCHING'};
 return {ok:true,json:async()=>d};
}};w.eval(code);return dom;
}
(async()=>{
const main=setup(false),child=setup(true);await main.window.RenkoSupertrend.mount('renko-supertrend');await child.window.RenkoSupertrend.mount('renko-supertrend');
await new Promise(r=>setTimeout(r,150));
for(const w of [main.window,child.window]){
 const select=w.document.getElementById('renko-symbol');if(![...select.options].some(o=>o.value===symbol))select.add(new w.Option(symbol,symbol));select.value=symbol;
 w.document.getElementById('renko-brick-mode').value='Auto';w.document.getElementById('renko-mode').value='LIVE';
}
for(const name of ['ema','rsi','adx']){main.window.document.getElementById('renko-'+name+'-family-enabled').checked=false;child.window.document.getElementById('renko-'+name+'-family-enabled').checked=true;}
const b=main.window.document.getElementById('renko-chart-toggle');b.disabled=false;await b.onclick();
const submitted=calls.filter(c=>c.url.includes('/start?'));assert.equal(submitted.length,1,JSON.stringify({calls:calls.map(c=>c.url),error:main.window.document.getElementById('renko-action-error').textContent}));
for(const name of ['ema','rsi','adx'])assert.equal(submitted[0].body[name+'_family_enabled'],false);
assert.equal(submitted[0].body.broker,'MOTILAL_OSWAL');assert.equal(submitted[0].body.account_id,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');assert.ok(submitted[0].url.startsWith('/api/renko-motilal/'));assert.equal(submitted[0].body.supertrend_family_enabled,true);assert.equal(submitted[0].body.mode,'LIVE');
assert.equal(main.window.document.getElementById('renko-action-error').textContent,'');assert.deepEqual(rejectedRoutes,[]);assert.ok(calls.every(c=>c.url.startsWith('/api/renko-motilal/')));
console.log('PASS mounted Motilal chart Start: native account endpoint and Supertrend-only LIVE payload verified using mocked transport; zero broker orders');main.window.close();child.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
