const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('/home/trading/sector-heatmap/.private/test-node/node_modules/jsdom');
const base={mode:'PAPER',quantity:7,product:'ATM_OPTIONS',gold_proxy:false,timeframe:'5 minutes',ema_exit_enabled:true,ema_exit_length:10,supertrend_exit_enabled:true};
async function mounted({legacy=false}={}){
 const dom=new JSDOM('<html><body><nav class="nav"><button data-view="trade-parser">Parser</button></nav><main class="work"></main></body></html>',{url:'https://example.test/broker-workspace/owned/',runScripts:'outside-only'}),w=dom.window,calls=[];
 const execution={api_version:1,settings:{...base},revision:'r1',running:false,mode:'PAPER',quantity:7,lifecycle:{reason:'NOT_STARTED',message:'Explicit start required.'},recommendations:[]};
 const status=()=>({workspace_broker:'DELTA_INDIA',configured:true,running:true,connection:'VERIFIED',route:'SUBSCRIBER',authentication:'AUTHORIZED',queue:[],...(legacy?{paper_pipeline:{running:true,mode:'PAPER',quantity:1000,recommendations:[]}}:{execution:{...execution,settings:{...execution.settings}}})});
 w.fetch=async(url,options)=>{const body=options?.body?JSON.parse(options.body):null;calls.push({url,body});
  const action=url.split('/').at(-1);let data=status();
  if(action==='execution-settings'){execution.settings={...execution.settings,...body};execution.revision='r2';execution.mode=body.mode;execution.quantity=body.quantity;data={...execution};}
  if(action==='execution-preview')data={ticket_id:'preview',text:body.text,config_revision:execution.revision,execution_mode:execution.settings.mode,quantity:execution.settings.quantity,contract:{symbol:'C-ETH-100',option_type:'CE',expiry_epoch:2000000000,quantity_multiplier:.01,underlying_asset:'ETH'},quote:{bid:1,ask:2}};
  if(action==='execution-submit')data={mode:execution.settings.mode,quantity:execution.settings.quantity,status:'RENKO_CONFIRMED_POSITION',position:{quantity:execution.settings.quantity,symbol:'C-ETH-100'},management_owner:'RENKO_SUPERTREND'};
  if(action==='execution-start'){execution.settings={...execution.settings,...body};execution.running=true;execution.mode=body.mode;execution.quantity=body.quantity;data={...execution};}
  return {ok:true,json:async()=>data};
 };
 w.eval(fs.readFileSync('telegram-parser.js','utf8'));
 const settle=async()=>{for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));};
 await settle();return {dom,w,calls,settle};
}
test('one mode and quantity control; no legacy exact-native product or auto-start on load',async()=>{
 const {dom,w,calls}=await mounted();try{
  assert.equal(w.document.querySelectorAll('#tg-mode').length,1);assert.equal(w.document.querySelectorAll('#tg-quantity').length,1);
  assert.equal(w.document.querySelector('#tg-product').options.length,1);assert.equal(w.document.querySelector('#tg-product').value,'ATM_OPTIONS');
  assert.equal(w.document.querySelector('#tg-option-mode'),null);assert.equal(w.document.querySelector('#tg-paper-start'),null);
  assert.equal(calls.some(c=>c.body),false);
 }finally{dom.window.close();}
});
test('manual paste parses then submits through unified settings and never legacy submit',async()=>{
 const {dom,w,calls,settle}=await mounted();try{
  w.document.querySelector('#tg-text').value='ETHUSD BUY ABOVE 100';w.document.querySelector('#tg-preview').click();await settle();
  assert.match(w.document.querySelector('#tg-preview-result').textContent,/PAPER · 7/);
  assert.equal(w.document.querySelector('#tg-submit').disabled,false);
  w.document.querySelector('#tg-submit').click();await settle();
  assert.ok(calls.some(c=>c.url.endsWith('/execution-preview')));
  const sent=calls.find(c=>c.url.endsWith('/execution-submit'));assert.ok(sent);assert.equal(sent.body.config_revision,'r2');assert.equal(sent.body.entry_confirmed,true);
  assert.equal('mode' in sent.body,false);assert.equal('quantity' in sent.body,false);
  assert.equal(calls.some(c=>c.url==='/api/telegram/submit'||c.url.endsWith('/option-submit')),false);
 }finally{dom.window.close();}
});
test('Live Run is disabled until explicit consent and uses the displayed single quantity',async()=>{
 const {dom,w,calls,settle}=await mounted();try{
  const mode=w.document.querySelector('#tg-mode');mode.value='LIVE';mode.dispatchEvent(new w.Event('change'));
  assert.equal(w.document.querySelector('#tg-run').disabled,true);
  const consent=w.document.querySelector('#tg-live-consent');consent.checked=true;consent.dispatchEvent(new w.Event('change'));
  assert.equal(w.document.querySelector('#tg-run').disabled,false);
  w.document.querySelector('#tg-run').click();await settle();
  const start=calls.find(c=>c.url.endsWith('/execution-start'));assert.equal(start.body.mode,'LIVE');assert.equal(start.body.quantity,7);assert.equal(start.body.live_confirmed,true);
 }finally{dom.window.close();}
});
test('old running backend remains visible; activation pending disables all new entry paths',async()=>{
 const {dom,w,calls}=await mounted({legacy:true});try{
  assert.match(w.document.querySelector('#tg-capability').textContent,/activation is pending/);
  assert.equal(w.document.querySelector('#tg-run').disabled,true);assert.equal(w.document.querySelector('#tg-preview').disabled,true);assert.equal(w.document.querySelector('#tg-submit').disabled,true);
  assert.match(w.document.querySelector('#tg-execution').textContent,/RUNNING.*PAPER.*1000/);
  assert.equal(calls.some(c=>c.body),false);
 }finally{dom.window.close();}
});

test('legacy connection uses receive-only start',async()=>{
 const {dom,w,calls,settle}=await mounted({legacy:true});try{
  w.document.querySelector('#tg-connect').disabled=false;w.document.querySelector('#tg-connect').click();await settle();
  const request=calls.find(c=>c.url.endsWith('/start'));assert.ok(request);assert.deepEqual(request.body,{auto:false});
  assert.equal(calls.some(c=>c.url.endsWith('/connect')),false);
 }finally{dom.window.close();}
});

test('reuse authorized session does not call unsupported login',async()=>{
 const {dom,w,calls,settle}=await mounted({legacy:true});try{
 w.document.querySelector('#tg-login').click();await settle();
 assert.equal(calls.some(c=>c.url.endsWith('/login')),false);
 assert.match(w.document.querySelector('#tg-message').textContent,/authorized and ready/);
 }finally{dom.window.close();}
});
