const {JSDOM}=require('jsdom');const fs=require('fs'),assert=require('assert');
const code=fs.readFileSync(require('path').resolve(__dirname,'../renko-supertrend.js'),'utf8');
const symbol='MCX:CRUDEOILM26OCTFUT',key='manual-trend-fixture';
const calls=[],errors=[];
const state={manual_trend_revision:'manual-price-marker-consecutive-v1',running:false,status:'STOPPED',config:{underlying:symbol,timeframe:'5 minutes',mode:'LIVE',lots:2},instrument:symbol,pnl:{},live_available:true,indicator_family_revision:'indicator-family-masters-v1',indicator_selection_revision:'independent-indicators-v1',indicator_destinations_revision:'strategy-indicator-destinations-v2',runtime_revision:'renko-supertrend-assessment-recovery-v14',zone_target_revision:'strong-5m-zone-target-v1',market_structure_revision:'confirmed-host-structure-v1'};
function setup(batch){
const dom=new JSDOM('<!doctype html><html><head></head><body><button data-view="ema-cross"></button><main class="work"></main></body></html>',{url:'https://utrading.pinakicloud.com/?renkoInstance='+key+(batch?'&renkoBatchChart=1&renkoChartSymbol='+encodeURIComponent(symbol):''),runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;w.addEventListener('error',e=>errors.push(String(e.error||e.message)));w.setInterval=()=>1;w.ResizeObserver=class{observe(){}disconnect(){}};w.EventSource=class{addEventListener(){}close(){}};w.PaperCapital={ensure:async()=>{}};w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>null,route:(s,u)=>u,fetch:async(_s,u,opts)=>{
 const body=opts?.body?JSON.parse(opts.body):null;calls.push({batch,url:u,body});
 let d={items:[],instruments:[]};
 if(u.includes('instances'))d={instances:[{instance_key:key,broker:'FYERS',instrument:symbol,config:state.config,running:false}]};
 else if(u.includes('/runner?'))d=state;
 else if(u.includes('/settings?'))d=body?{saved_at:Date.now()/1000}:{settings:{symbol,mode:'LIVE','supertrend-family-enabled':true,'ema-family-enabled':false,'rsi-family-enabled':false,'adx-family-enabled':false,'brick-mode':'Auto'},saved_at:Date.now()/1000};
 else if(u.includes('/manual-brick?'))d={manual_brick:12.4,reference_atr:359.6,reference_bars:40,rule:{reference_seconds:52200,divisor:29,atr_length:Number(new URL(u,'https://test').searchParams.get('atr_length'))},symbol};
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
const b=child.window.document.getElementById('renko-chart-toggle');b.disabled=false;child.window.document.getElementById('renko-toggle').disabled=false;await b.onclick();
const submitted=calls.filter(c=>c.url.includes('/start?'));assert.equal(submitted.length,1,JSON.stringify({calls:calls.map(c=>c.url),error:child.window.document.getElementById('renko-action-error').textContent}));
for(const name of ['ema','rsi','adx'])assert.equal(submitted[0].body[name+'_family_enabled'],false);
assert.equal(submitted[0].body.supertrend_family_enabled,true);assert.equal(submitted[0].body.mode,'LIVE');assert.equal(submitted[0].body.timeframe,'1 minute');
assert.equal(child.window.document.getElementById('renko-action-error').textContent,'');
const actual=calls.find(c=>c.batch&&c.url.includes('/start?')).body;assert.equal(actual.manual_trend_enabled,true);assert.equal(actual.manual_trend_closes,3);assert.equal(actual.manual_trend_bullish,100);assert.equal(actual.manual_trend_bearish,100);
console.log('PASS manual trend fields and completed-close count transferred by full mounted Start handler: actual chart Start handler sends Supertrend-only LIVE and selected one-minute timeframe despite five-minute parent through mocked transport; no broker/network/order calls');main.window.close();child.window.close();
})().catch(e=>{console.error(e);process.exitCode=1});
