const {test}=require('node:test'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom'),fs=require('fs');
test('the shared FYERS choice applies across forms and does not connect Dhan',async()=>{
 const dom=new JSDOM('<head></head><body><section class="view active" id="handoff"><select class="order-account" id="ticket-broker"><option value="fyers">FYERS</option></select></section><div class="broker-card"><span class="label">BROKER CONNECTION</span></div><div id="sector-filter"></div><div id="screener-analysis"></div><div id="open-positions"></div><select id="renko-broker"></select></body>',{runScripts:'outside-only',url:'https://portal.example/?brokerAccount=fyers-owner'});
 const w=dom.window,calls=[];
 const accounts=[{id:'dhan-owner',broker:'DHAN',configured:true,label:'Dhan'},{id:'fyers-owner',broker:'FYERS',configured:true,label:'FYERS'}];
 w.fetch=async(url)=>{calls.push(String(url));return {ok:true,json:async()=>String(url).includes('workspace-context')?{username:'test',workspace:null}:String(url).includes('workspaces/accounts')?{accounts}:String(url).includes('capabilities')?{strategy_routes:['renko','rsi','band','kama'],screener_read_only:true}:{}};};
 w.eval(fs.readFileSync('broker-form-routing.js','utf8'));w.eval(fs.readFileSync('broker-account-options.js','utf8'));
 await new Promise(r=>setTimeout(r,40));
 for(const kind of ['handoff','sector','screener','account','renko'])assert.equal(w.BrokerForms.account(kind)?.id,'fyers-owner',kind);
 assert.equal(calls.some(u=>u.includes('/api/dhan/status')),false);
 assert.equal(w.document.querySelector('#selected-broker-connection'),null);
 dom.window.close();
});
test('changing broker clears old per-form ownership before reloading the same workspace',()=>{
 const dom=new JSDOM('<body></body>',{runScripts:'outside-only',url:'https://portal.example/'});dom.window.module={exports:{}};dom.window.eval(fs.readFileSync('broker-form-routing.js','utf8'));const {brokerSwitchUrl}=dom.window.module.exports;
 const url=new URL(brokerSwitchUrl('https://portal.example/?renkoAccount=old&handoffAccount=old&sectorAccount=old&renkoInstance=old',{id:'selected',broker:'FYERS'},'handoff'));
 assert.equal(url.searchParams.get('brokerAccount'),'selected');assert.equal(url.searchParams.get('handoffAccount'),'selected');
 assert.equal(url.searchParams.has('sectorAccount'),false);assert.equal(url.searchParams.has('renkoInstance'),false);dom.window.close();
});

test('a sole eligible Dhan account binds shared forms and the native Renko client',async()=>{
 const dom=new JSDOM('<button data-view="ema-cross"></button><main class="work"><section class="view active" id="handoff"><select class="order-account" id="ticket-broker"><option value="fyers">FYERS</option></select></section><div id="screener-analysis"></div><div id="sector-filter"></div><div id="trade-parser-input"></div></main>',{url:'https://portal.example/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,calls=[];
 const account={id:'dhan-owner',broker:'DHAN',configured:true,label:'Saved Dhan'};
 const context={username:'test',workspace:null,parser_native_supported:true};
 w.SectorPulseWorkspace=context;
 w.AbortSignal=AbortSignal;
 w.ResizeObserver=class{observe(){} disconnect(){}};
 w.EventSource=class{addEventListener(){} close(){}};
 w.fetch=async(url,options)=>{
  const path=new URL(url,w.location.href).pathname;
  calls.push([path,options?.method||'GET']);
  const data=path.endsWith('/workspace-context')?context:path.endsWith('/workspaces/accounts')?{accounts:[account]}:
   path.endsWith('/capabilities')?{screener_read_only:true,strategy_routes:['renko']}:
   {settings:{},items:[],instances:[],trades:[],matches:[]};
  return {ok:true,json:async()=>data};
 };
 try{
  for(const file of ['renko-supertrend.js','broker-form-routing.js','broker-account-options.js'])w.eval(fs.readFileSync(file,'utf8'));
  await w.RenkoSupertrend.mount('renko-supertrend');
  for(const kind of ['renko','handoff','screener','sector','parser'])assert.equal(w.BrokerForms.account(kind)?.id,account.id,kind);
  assert.match(w.document.querySelector('#renko-broker').selectedOptions[0].textContent,/Dhan/);
  assert.ok(calls.some(([path,method])=>path.startsWith('/api/renko-dhan/'+account.id+'/')&&method==='GET'));
  assert.ok(calls.every(([,method])=>method==='GET'));
 }finally{dom.window.close();}
});
