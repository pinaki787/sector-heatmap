const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const source=fs.readFileSync('handoff-screener.js','utf8');
async function setup(broker='FYERS'){const dom=new JSDOM('<head></head><body><section id="handoff"><div class="handoff-schedule"></div></section><section id="screener"><div id="screener-analysis"></div></section></body>',{runScripts:'outside-only',url:'https://example.test/'});const w=dom.window,calls=[];let handoff={id:'owned',broker},screener=handoff;
const value={enabled:true,auto_enabled:true,symbols:['TEST'],sources:[{id:'source',label:'Chosen screen',url:'https://chartink.com/screener/chosen',symbols:['TEST']}],revision:'known'};
w.BrokerForms={ready:Promise.resolve(),account:k=>k==='handoff'?handoff:screener,context:()=>({csrf:'test-csrf'}),fetch:async(kind,url,options)=>{calls.push({kind,url,options});return {ok:true,json:async()=>options?.body?{...value,...JSON.parse(options.body)}:value};}};w.eval(source);await new Promise(r=>setTimeout(r,20));return{dom,w,calls,setScreener:a=>screener=a};}
test('page load reads saved sources without changing Auto or source settings',async()=>{const {w,calls,dom}=await setup();assert.equal(calls.length,1);assert.equal(calls[0].options,undefined);assert.match(w.document.querySelector('[data-status]').textContent,/explicitly selected/);assert.equal(w.document.querySelector('[data-auto]').checked,true);dom.window.close();});
test('explicit save changes only source inclusion and retains selected universe',async()=>{const {w,calls,dom}=await setup();w.document.querySelector('[data-auto]').checked=false;w.document.querySelector('[data-save]').click();await new Promise(r=>setTimeout(r,20));const body=JSON.parse(calls[1].options.body);assert.equal(body.auto_enabled,false);assert.deepEqual(body.symbols,['TEST']);assert.equal(body.account_id,'owned');assert.equal('capital' in body,false);assert.equal('live_authorized' in body,false);dom.window.close();});
test('source selection from a different account cannot overwrite Handoff choices',async()=>{const {w,calls,dom,setScreener}=await setup();setScreener({id:'different',broker:'FYERS'});w.dispatchEvent(new w.CustomEvent('sector-pulse-screener-selection',{detail:{symbols:['OTHER'],sources:[{id:'s',label:'Other',url:'https://chartink.com/screener/other',symbols:['OTHER']}]}}));await new Promise(r=>setTimeout(r,20));assert.equal(calls.length,1);assert.match(w.document.querySelector('[data-state]').textContent,/same broker account/);dom.window.close();});
test('unsupported broker never falls back to FYERS',async()=>{const {w,calls,dom,setScreener}=await setup();setScreener({id:'delta',broker:'DELTA_INDIA'});w.document.querySelector('[data-clear]').click();await new Promise(r=>setTimeout(r,20));assert.equal(calls.length,1);assert.match(w.document.querySelector('[data-state]').textContent,/Select the owned FYERS or Dhan/);dom.window.close();});

test('same-account Dhan source selection is supported without changing Auto or capital',async()=>{const {w,calls,dom}=await setup('DHAN');assert.equal(w.document.querySelector('[data-use]').closest('section').hidden,false);w.document.querySelector('[data-save]').click();await new Promise(r=>setTimeout(r,20));const body=JSON.parse(calls[1].options.body);assert.equal(body.broker,'DHAN');assert.equal(body.account_id,'owned');assert.equal(body.auto_enabled,true);assert.equal('capital' in body,false);assert.equal('live_authorized' in body,false);dom.window.close();});

test('Auto remains disabled until the backend advertises Screener scope',async()=>{
 const {w,dom}=await setup();
 assert.equal(w.document.querySelector('[data-start-auto]').disabled,true);
 assert.equal(w.document.querySelector('[data-pause-auto]').disabled,false);
 dom.window.close();
});
test('Auto rejects invalid funds before changing saved sources or schedule',async()=>{
 const {w,calls,dom}=await setup();
 w.document.querySelector('[data-auto-capital]').value='0';
 w.dispatchEvent(new w.CustomEvent('sector-pulse-screener-selection',{detail:{action:'ENABLE_SCREENER_AUTO',symbols:['TEST'],sources:[]}}));
 await new Promise(r=>setTimeout(r,20));
 assert.equal(calls.length,1);
 assert.match(w.document.querySelector('[data-auto-state]').textContent,/Enter allotted funds/);
 dom.window.close();
});
