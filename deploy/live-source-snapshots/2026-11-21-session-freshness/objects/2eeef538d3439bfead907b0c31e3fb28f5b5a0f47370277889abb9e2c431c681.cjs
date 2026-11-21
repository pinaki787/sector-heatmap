const {JSDOM}=require('jsdom');const fs=require('fs'),assert=require('assert');
const code=fs.readFileSync(require('path').resolve(__dirname,'../renko-supertrend.js'),'utf8');
const symbol='MCX:CRUDEOILM26OCTFUT',key='4a8a4fa8e499c1b20def';
const calls=[],errors=[];
const state={manual_trend_revision:'manual-price-marker-consecutive-v1',running:false,status:'STOPPED',config:{underlying:symbol,timeframe:'5 minutes',mode:'LIVE',lots:2},instrument:symbol,pnl:{},live_available:true,indicator_family_revision:'indicator-family-masters-v1',indicator_selection_revision:'independent-indicators-v1',indicator_destinations_revision:'strategy-indicator-destinations-v2',runtime_revision:'renko-supertrend-assessment-recovery-v14',zone_target_revision:'strong-5m-zone-target-v1',market_structure_revision:'confirmed-host-structure-v1'};
function setup(batch){
const dom=new JSDOM('<!doctype html><html><head></head><body><button data-view="ema-cross"></button><main class="work"></main></body></html>',{url:'https://utrading.pinakicloud.com/'+(batch?'?renkoInstance='+key+'&renkoBatchChart=1&renkoChartSymbol='+encodeURIComponent(symbol):''),runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;w.addEventListener('error',e=>errors.push(String(e.error||e.message)));w.setInterval=()=>1;w.ResizeObserver=class{observe(){}disconnect(){}};w.EventSource=class{addEventListener(){}close(){}};w.PaperCapital={ensure:async()=>{}};w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>null,route:(s,u)=>u,fetch:async(_s,u,opts)=>{
 const body=opts?.body?JSON.parse(opts.body):null;calls.push({batch,url:u,body});
 let d={items:[],instruments:[],matches:[{symbol,underlying:'CRUDEOILM'}]};
 if(u.includes('instances'))d={instances:[{instance_key:key,broker:'FYERS',instrument:symbol,config:state.config,running:false}]};
 else if(u.includes('/runner?'))d=state;
 else if(u.includes('/settings?'))d=body?{saved_at:Date.now()/1000}:{settings:{symbol,mode:'LIVE','supertrend-family-enabled':true,'ema-family-enabled':false,'rsi-family-enabled':false,'adx-family-enabled':false,'brick-mode':'Auto'},saved_at:Date.now()/1000};
 else if(u.includes('/manual-brick?'))d={manual_brick:12.4,reference_atr:359.6,reference_bars:40,rule:{reference_seconds:52200,divisor:29,atr_length:Number(new URL(u,'https://test').searchParams.get('atr_length'))},symbol};
 else if(u.includes('/chart-timeframe?'))d={...state,config:{...state.config,timeframe:body.timeframe,supertrend_timeframe:body.timeframe==='5 minutes'?'15 minutes':'5 minutes'}};
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
const session=main.window.document.getElementById('renko-trading-session-hours');assert.ok(session);assert.equal(session.readOnly,true);assert.equal(session.title,'The trading session interval for a day');
const frame=main.window.document.querySelector('iframe');assert.ok(frame,'main owns chart iframe');Object.defineProperty(frame,'contentWindow',{value:child.window});Object.defineProperty(child.window,'parent',{value:main.window});
main.window.postMessage=data=>main.window.dispatchEvent(new main.window.MessageEvent('message',{origin:main.window.location.origin,source:child.window,data}));child.window.postMessage=data=>child.window.dispatchEvent(new child.window.MessageEvent('message',{origin:main.window.location.origin,source:main.window,data}));
child.window.document.getElementById('renko-timeframe').value='1 minute';
main.window.dispatchEvent(new main.window.MessageEvent('message',{origin:main.window.location.origin,source:child.window,data:{type:'sector-pulse:renko-session-policy',symbol,policy:{master_regular_session:'0915-1530'}}}));
assert.equal(main.window.document.getElementById('renko-trading-session-hours').value,'6.25');
main.window.dispatchEvent(new main.window.MessageEvent('message',{origin:main.window.location.origin,source:child.window,data:{type:'sector-pulse:renko-session-policy',symbol:'BSE:OTHER',policy:{master_regular_session:'0900-2330'}}}));
assert.equal(main.window.document.getElementById('renko-trading-session-hours').value,'6.25');
const period=main.window.document.getElementById('renko-atr-length');
main.window.document.getElementById('renko-brick-mode').value='Manual';period.value='5';period.dispatchEvent(new main.window.Event('change'));
await new Promise(r=>setTimeout(r,40));
assert.ok(calls.some(c=>!c.batch&&c.url.includes('/manual-brick?')&&c.url.includes('atr_length=5')));
period.value='7';period.dispatchEvent(new main.window.Event('change'));await new Promise(r=>setTimeout(r,40));
assert.ok(calls.some(c=>!c.batch&&c.url.includes('/manual-brick?')&&c.url.includes('atr_length=7')));
main.window.document.getElementById('renko-brick-mode').value='Auto';
const doc=main.window.document;assert.equal(doc.getElementById('renko-manual-trend-group').open,false);
const master=doc.getElementById('renko-manual-trend-enabled');assert.equal(master.checked,false);master.checked=true;master.dispatchEvent(new main.window.Event('change'));
for(const [key,value] of [['bullish','100'],['bearish','100'],['closes','3']])doc.getElementById('renko-manual-trend-'+key).value=value;
assert.equal(doc.getElementById('renko-manual-trend-bullish').disabled,false);
// Actual chart change event must update both editors before Start.
const mainHost=main.window.document.getElementById('renko-timeframe'),mainHigher=main.window.document.getElementById('renko-supertrend-timeframe'),childHost=child.window.document.getElementById('renko-timeframe');
for(const [host,higher] of [['5 minutes','15 minutes'],['1 minute','5 minutes'],['5 minutes','15 minutes']]){
 childHost.value=host;childHost.dispatchEvent(new child.window.Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,60));
 assert.equal(mainHost.value,host,JSON.stringify({host,main:mainHost.value,child:childHost.value,mainSymbol:doc.getElementById('renko-symbol').value,childSymbol:child.window.document.getElementById('renko-symbol').value,errors,calls:calls.slice(-8)}));assert.equal(mainHigher.value,higher);assert.equal(child.window.document.getElementById('renko-supertrend-timeframe').value,higher);
}

// Parent editor changes must also reach the real mounted child listener.
const parentSlope=doc.getElementById('renko-supertrend-slope-enabled');
for(const [timeframe,slope,basis] of [['1 minute',true,'RENKO'],['5 minutes',false,'RENKO'],['1 minute',false,'CANDLESTICK']]){
 mainHost.value=timeframe;doc.getElementById('renko-strategy-basis').value=basis;parentSlope.checked=slope;
 mainHost.dispatchEvent(new main.window.Event('change',{bubbles:true}));
 await new Promise(r=>setTimeout(r,60));
 const childDoc=child.window.document;
 assert.equal(childHost.value,timeframe,JSON.stringify({timeframe,parentSymbol:doc.getElementById('renko-symbol').value,childSymbol:child.window.document.getElementById('renko-symbol').value,frames:[...doc.querySelectorAll('iframe')].map(f=>f.src),errors,calls:calls.slice(-5)}));
 assert.equal(doc.getElementById('renko-runner-timeframe').value,timeframe);
 assert.equal(childDoc.getElementById('renko-runner-timeframe').value,timeframe);
 assert.equal(childDoc.getElementById('renko-supertrend-slope-enabled').checked,slope);
 assert.equal(childDoc.getElementById('renko-strategy-basis').value,basis);
 assert.match(childDoc.getElementById('renko-status').textContent,/Loading|unavailable/);
 const chartCall=calls.filter(c=>c.batch&&c.url.includes('/chart?')).at(-1);assert.ok(chartCall);
 const query=new URL(chartCall.url,'https://test').searchParams;
 assert.equal(query.get('timeframe'),timeframe);assert.equal(query.get('strategy_basis'),basis);assert.equal(query.get('supertrend_slope_enabled'),String(slope));
}
// Reject messages from unrelated windows and instruments.
child.window.dispatchEvent(new child.window.MessageEvent('message',{origin:main.window.location.origin,source:{},data:{type:'sector-pulse:renko-chart-display',symbol,selection:{timeframe:'30 minutes'}}}));
assert.equal(childHost.value,'1 minute');
// Live instance inputs remain frozen even when a parent editor message arrives.
state.running=true;state.position={};
child.window.dispatchEvent(new child.window.MessageEvent('message',{origin:main.window.location.origin,source:main.window,data:{type:'sector-pulse:renko-chart-display',symbol,selection:{timeframe:'30 minutes','strategy-basis':'LEGACY','supertrend-slope-enabled':true}}}));
assert.equal(childHost.value,'1 minute');assert.equal(child.window.document.getElementById('renko-strategy-basis').value,'CANDLESTICK');
assert.equal(calls.filter(c=>/\/(start|stop|override|chart-timeframe)\?/.test(c.url)).length,0);
main.window.close();child.window.close();console.log('Mounted editor sync: both directions, slope, basis, active protection and no execution mutations verified');
})().catch(e=>{console.error(e);process.exitCode=1});
