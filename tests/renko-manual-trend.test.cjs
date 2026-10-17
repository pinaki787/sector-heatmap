const {JSDOM}=require('jsdom');const fs=require('fs'),assert=require('assert');
const code=fs.readFileSync(require('path').resolve(__dirname,'../renko-supertrend.js'),'utf8');
const symbol='MCX:CRUDEOILM26OCTFUT',key='manual-trend-fixture';
const calls=[],errors=[];
const state={manual_trend_revision:'manual-price-marker-consecutive-v1',running:false,status:'STOPPED',config:{underlying:symbol,timeframe:'5 minutes',mode:'LIVE',lots:2},instrument:symbol,pnl:{},live_available:true,indicator_family_revision:'indicator-family-masters-v1',indicator_selection_revision:'independent-indicators-v1',indicator_destinations_revision:'strategy-indicator-destinations-v2',runtime_revision:'renko-supertrend-assessment-recovery-v14',zone_target_revision:'strong-5m-zone-target-v1',market_structure_revision:'confirmed-host-structure-v1'};
function setup(batch){
const dom=new JSDOM('<!doctype html><html><head></head><body><button data-view="ema-cross"></button><main class="work"></main></body></html>',{url:'https://utrading.pinakicloud.com/'+(batch?'?renkoInstance='+key+'&renkoBatchChart=1&renkoChartSymbol='+encodeURIComponent(symbol):''),runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;w.localStorage.setItem('sector-pulse:renko-configurations-v1:FYERS',JSON.stringify({schema_version:1,preferred:{},records:[1,2,3].map(saved_at=>({id:'legacy-'+saved_at,name:'Previously saved · '+symbol+' · '+saved_at,symbol,settings:{symbol,mode:'LIVE','brick-mode':'Auto'},saved_at}))}));if(!batch)w.localStorage.setItem('sector-pulse:renko-batch-selection:FYERS',JSON.stringify([{symbol,selected:true}]));w.addEventListener('error',e=>errors.push(String(e.error||e.message)));w.__testIntervals=[];w.__testClock=1000;w.__testStreams=[];Object.defineProperty(w.performance,'now',{value:()=>w.__testClock});w.setInterval=(fn,delay)=>{w.__testIntervals.push({fn,delay});return w.__testIntervals.length;};w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};w.ResizeObserver=class{observe(){}disconnect(){}};w.EventSource=class{constructor(){this.readyState=1;this.listeners={};w.__testStreams.push(this);}addEventListener(name,fn){this.listeners[name]=fn;}close(){this.readyState=2;}};w.PaperCapital={ensure:async()=>{}};w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>null,route:(s,u)=>u,fetch:async(_s,u,opts)=>{
 const body=opts?.body?JSON.parse(opts.body):null;calls.push({batch,url:u,body});
 let d={items:[],instruments:[],matches:[{symbol,underlying:'CRUDEOILM'}]};
 if(u.includes('instances'))d={instances:[{instance_key:key,broker:'FYERS',instrument:symbol,config:state.config,running:false}]};
 else if(u.includes('/runner?'))d=state;
 else if(u.includes('/settings?'))d=body?{saved_at:Date.now()/1000}:{settings:{symbol,mode:'LIVE','supertrend-family-enabled':true,'ema-family-enabled':false,'rsi-family-enabled':false,'adx-family-enabled':false,'brick-mode':'Auto'},saved_at:Date.now()/1000};
 else if(u.includes('/manual-brick?'))d={manual_brick:12.4,reference_atr:359.6,reference_bars:40,rule:{reference_seconds:52200,divisor:29,atr_length:Number(new URL(u,'https://test').searchParams.get('atr_length'))},symbol};
 else if(u.includes('/start?'))d={...state,running:true,status:'WATCHING'};
 return {ok:true,json:async()=>d};
}};w.eval(fs.readFileSync(require('path').resolve(__dirname,'../dashboard-help.js'),'utf8'));w.eval(code);return dom;
}
(async()=>{
const main=setup(false),child=setup(true);await main.window.RenkoSupertrend.mount('renko-supertrend');await child.window.RenkoSupertrend.mount('renko-supertrend');
await new Promise(r=>setTimeout(r,150));

for(const w of [main.window,child.window]){
 w.document.querySelector('[aria-label="Show saved configurations"]').click();assert.equal(w.document.querySelectorAll('#renko-config-options [role=option]').length,1,'mounted legacy migration shows one configuration');assert.ok(w.localStorage.getItem('sector-pulse:renko-configurations-v1:FYERS:before-instrument-consolidation'),'original records backed up');

 const select=w.document.getElementById('renko-symbol');if(![...select.options].some(o=>o.value===symbol))select.add(new w.Option(symbol,symbol));select.value=symbol;
 w.document.getElementById('renko-brick-mode').value='Auto';w.document.getElementById('renko-mode').value='LIVE';
}
main.window.document.getElementById('renko-symbol').dispatchEvent(new main.window.Event('change'));await new Promise(r=>setTimeout(r,30));
const previousStream=main.window.__testStreams.at(-1),streamCount=main.window.__testStreams.length,statusCount=calls.filter(c=>!c.batch&&c.url.includes('/runner?')).length;
main.window.__testClock=31000;const watchdog=main.window.__testIntervals.find(t=>t.fn.name==='recoverSilentStream');assert.ok(watchdog,'silent-stream recovery timer installed');await watchdog.fn();assert.ok(main.window.__testStreams.length>streamCount,JSON.stringify({message:'silent stream replaced',active:main.window.document.getElementById('renko-supertrend').className,hidden:main.window.document.hidden,symbol:main.window.document.getElementById('renko-symbol').value,streams:main.window.__testStreams.length,clock:main.window.performance.now()}));assert.equal(previousStream.readyState,2);assert.ok(calls.filter(c=>!c.batch&&c.url.includes('/runner?')).length>statusCount,'runner status independently refreshed');previousStream.listeners.state({data:'not JSON: obsolete event must be ignored before parsing'});assert.notEqual(main.window.document.getElementById('renko-state').textContent,'STALE_REPLAY');
const noExtra=main.window.__testStreams.length;await watchdog.fn();assert.equal(main.window.__testStreams.length,noExtra,'recovery is throttled');

await main.window.document.getElementById('renko-save-settings').onclick();
for(const name of ['ema','rsi','adx']){main.window.document.getElementById('renko-'+name+'-family-enabled').checked=false;child.window.document.getElementById('renko-'+name+'-family-enabled').checked=true;}
for(const input of main.window.document.querySelectorAll('#renko-supertrend input[id],#renko-supertrend select[id],#renko-supertrend textarea[id]')){if(input.type==='hidden'||input.id.endsWith('-section-choices'))continue;assert.ok(main.window.SectorPulseHelp.parameters[input.id.replace(/^renko-/,'')],'Missing help for '+input.id);}
const runnerFrame=main.window.document.getElementById('renko-runner-timeframe');assert.ok(runnerFrame);for(const value of ['1 minute','5 minutes','15 minutes','30 minutes'])assert.ok([...runnerFrame.options].some(o=>o.value===value));
const quickHelp=main.window.document.getElementById('renko-sideways-max-candles').closest('label').querySelector('.renko-parameter-help');assert.ok(quickHelp);quickHelp.dispatchEvent(new main.window.Event('focus'));const tooltip=main.window.document.getElementById('renko-parameter-tooltip');assert.equal(tooltip.hidden,false);assert.match(tooltip.textContent,/Both entry and exit candles count/);assert.match(tooltip.textContent,/not a forced exit/);quickHelp.dispatchEvent(new main.window.Event('blur'));assert.equal(tooltip.hidden,true);
const session=main.window.document.getElementById('renko-trading-session-hours');assert.ok(session);assert.equal(session.readOnly,true);assert.match(session.title,/broker contract session duration/);
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
const b=child.window.document.getElementById('renko-chart-toggle');b.disabled=false;child.window.document.getElementById('renko-toggle').disabled=false;const startPromise=b.onclick();await new Promise(r=>setTimeout(r,30));const choice=main.window.document.getElementById('renko-configuration-choice');assert.ok(choice,'embedded Start prompts on modified settings');const requestedChoice=process.env.RENKO_CONFIG_CHOICE||'form';[...choice.querySelectorAll('button')].find(b=>b.textContent===({form:'Use form parameters',saved:'Use saved configuration',cancel:'Cancel'}[requestedChoice])).click();await startPromise;
if(requestedChoice==='cancel'){assert.equal(calls.filter(c=>c.url.includes('/start?')).length,0);assert.match(child.window.document.getElementById('renko-action-error').textContent,/cancelled/);main.window.close();child.window.close();return;}
if(requestedChoice==='saved'){const start=calls.find(c=>c.url.includes('/start?')).body;assert.equal(start.manual_trend_enabled,false);assert.equal(start.timeframe,'5 minutes');assert.equal(start.mode,'LIVE');main.window.close();child.window.close();return;}
const submitted=calls.filter(c=>c.url.includes('/start?'));assert.equal(submitted.length,1,JSON.stringify({calls:calls.map(c=>c.url),error:child.window.document.getElementById('renko-action-error').textContent}));
for(const name of ['ema','rsi','adx'])assert.equal(submitted[0].body[name+'_family_enabled'],false);
assert.equal(submitted[0].body.supertrend_family_enabled,true);assert.equal(submitted[0].body.mode,'LIVE');assert.equal(submitted[0].body.timeframe,'1 minute');
assert.equal(child.window.document.getElementById('renko-action-error').textContent,'');
const actual=calls.find(c=>c.batch&&c.url.includes('/start?')).body;assert.equal(actual.manual_trend_enabled,true);assert.equal(actual.manual_trend_closes,3);assert.equal(actual.manual_trend_bullish,100);assert.equal(actual.manual_trend_bearish,100);
console.log('PASS manual trend fields and completed-close count transferred by full mounted Start handler: actual chart Start handler sends Supertrend-only LIVE and selected one-minute timeframe despite five-minute parent through mocked transport; no broker/network/order calls');main.window.close();child.window.close();
})().catch(e=>{console.error(e);process.exitCode=1});
