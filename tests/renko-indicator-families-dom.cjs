const fs=require('fs'),assert=require('node:assert/strict'),{JSDOM}=require(process.env.RENKO_JSDOM_MODULE || 'jsdom');
(async()=>{
const dom=new JSDOM('<!doctype html><html><head></head><body><button data-view="ema-cross"></button><main class="work"></main></body></html>',{url:'https://utrading.pinakicloud.com/',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,errors=[];
w.addEventListener('error',e=>errors.push(e.error||e.message));
w.setInterval=()=>1;w.ResizeObserver=class{observe(){} disconnect(){}};
w.EventSource=class{addEventListener(){} close(){}};
w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>null,route:(s,u)=>u,fetch:async(_s,u)=>({ok:true,json:async()=>u.includes('/runner?')?{indicator_family_revision:'indicator-family-masters-v1',running:false,status:'STOPPED',config:{mode:'PAPER'},pnl:{},live_available:false}:u.includes('/settings?')?{settings:{},saved_at:0}:{items:[],instruments:[]}})};
w.eval(fs.readFileSync('renko-supertrend.js','utf8'));
await w.RenkoSupertrend.mount('renko-supertrend');
const names=['supertrend','ema','rsi','adx','structure','zones'];
for(const name of names){const input=w.document.getElementById('renko-'+name+'-family-enabled');assert.ok(input,name);assert.equal(input.checked,true);}
assert.equal(w.document.querySelectorAll('.renko-family-master').length,6);
assert.ok(w.document.body.textContent.includes('Chart only'));
setTimeout(()=>{for(const name of names)assert.equal(w.document.getElementById('renko-'+name+'-family-enabled').disabled,false,'loaded backend capability');
const master=w.document.getElementById('renko-ema-family-enabled'),rule=w.document.getElementById('renko-ema-fast-enabled'),chart=w.document.getElementById('renko-ema-fast-enabled-indicator');
const prior=rule.checked,chartPrior=chart.checked;
master.checked=false;master.dispatchEvent(new w.Event('change',{bubbles:true}));
assert.equal(rule.disabled,true);assert.equal(rule.checked,prior);assert.equal(chart.disabled,false);assert.equal(chart.checked,chartPrior);
master.checked=true;master.dispatchEvent(new w.Event('change',{bubbles:true}));
assert.equal(rule.disabled,false);assert.equal(rule.checked,prior);
assert.deepEqual(errors,[]);console.log('DOM loaded-backend PASS: six groups; OFF/ON preserves subordinate choices; chart controls remain enabled; zero uncaught errors');w.close();},100);

})().catch(error=>{console.error(error);process.exitCode=1;});
