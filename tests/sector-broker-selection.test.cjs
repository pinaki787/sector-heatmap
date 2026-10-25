const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {choices,sectorSelection}=require('../broker-account-options.js');
const accounts=['DELTA_INDIA','FYERS','DHAN','MOTILAL_OSWAL'].map((broker,i)=>({id:String(i),broker,label:broker,configured:true}));
test('Delta is absent only from Sector Rotation choices',()=>{
 assert.deepEqual(choices(accounts,{kind:'sector'}).map(r=>r.broker),['FYERS','DHAN','MOTILAL_OSWAL']);
 for(const kind of ['manual','renko','strategy','screener','account','parser'])assert.ok(choices(accounts,{kind}).some(r=>r.broker==='DELTA_INDIA'),kind+' choices changed');
});
test('valid sector choices survive; removed Delta selections require explicit replacement',()=>{
 const rows=choices(accounts,{kind:'sector',workspaceId:'0'});
 assert.equal(sectorSelection(rows,{workspaceId:'0'}).id,'1');
 assert.equal(sectorSelection(rows,{requestedId:'0'}),null);
 assert.equal(sectorSelection(rows,{previousId:'0',previousValue:'DELTA_INDIA'}),null);
 assert.equal(sectorSelection(rows,{workspaceId:'0',requestedId:'1'}).id,'1');
 assert.equal(sectorSelection(rows,{workspaceId:'0',requestedId:'0',previousId:'2'}).id,'2');
 assert.equal(sectorSelection(rows,{currentBroker:'FYERS'}).id,'1');
 assert.equal(sectorSelection([],{}),null);
});
const {JSDOM}=require('/home/trading/sector-heatmap/.private/test-node/node_modules/jsdom');
async function mounted({url='https://example.test/broker-workspace/0/',inventory=accounts}={}){
 const dom=new JSDOM('<html><body><label><input id="ema-band-lots"></label><label>Filter<select id="sector-filter"><option>All</option></select></label><select class="order-account"><option>Existing execution choice</option></select><select id="renko-broker"><option value="DELTA_INDIA">Delta India</option></select></body></html>',{url,runScripts:'outside-only'}),w=dom.window,calls=[];
 w.AbortSignal=AbortSignal;w.SectorPulseWorkspace={workspace:{id:'0',broker:'DELTA_INDIA'}};
 w.fetch=async(url,options)=>{calls.push({url,options});const value=url.includes('workspace-context')?w.SectorPulseWorkspace:url.includes('/workspaces/accounts')?{accounts:inventory}:{strategy_routes:[]};return {ok:true,json:async()=>value};};
 w.eval(fs.readFileSync('broker-form-routing.js','utf8'));w.eval(fs.readFileSync('broker-account-options.js','utf8'));
 await new Promise(resolve=>w.addEventListener('broker-accounts-ready',resolve,{once:true}));return {dom,w,calls};
}
test('unset Sector Rotation defaults to FYERS in Delta workspace; execution context stays Delta',async()=>{
 const {dom,w,calls}=await mounted();try{
  const sector=w.document.getElementById('sector-broker-account');
  assert.equal(sector.value,'account:1');assert.equal([...sector.options].some(o=>o.dataset.savedBrokerAccount==='0'),false);
  assert.match(sector.selectedOptions[0].textContent,/FYERS/);
  assert.match(sector.closest('label').querySelector('small').textContent,/data account only/);
  assert.equal(w.document.getElementById('renko-broker').value,'DELTA_INDIA');
  assert.ok([...w.document.querySelector('.order-account').options].some(o=>o.dataset.savedBrokerAccount==='0'));
  assert.equal(w.location.href,'https://example.test/broker-workspace/0/');
  await w.BrokerForms.fetch('sector','/api/sector-analysis');assert.equal(new URL(calls.at(-1).url).pathname,'/broker-workspace/1/api/sector-analysis');
 }finally{dom.window.close();}
});
test('saved valid sector URL binding remains usable inside Delta workspace',async()=>{
 const {dom,w}=await mounted({url:'https://example.test/broker-workspace/0/?sectorAccount=1'});try{
  assert.equal(w.document.getElementById('sector-broker-account').selectedOptions[0].dataset.savedBrokerAccount,'1');
  assert.equal(w.BrokerForms.account('sector').broker,'FYERS');assert.equal(w.document.getElementById('renko-broker').value,'DELTA_INDIA');
 }finally{dom.window.close();}
});
test('explicit sector changes stay in the workspace and do not overwrite global broker binding',async()=>{
 const url='https://example.test/broker-workspace/0/?brokerAccount=0&renkoBroker=DELTA_INDIA';
 const {dom,w}=await mounted({url});try{
  const sector=w.document.getElementById('sector-broker-account');
  for(const id of ['1','3']){
   sector.value='account:'+id;sector.dispatchEvent(new w.Event('change',{bubbles:true}));
   assert.equal(w.location.pathname,'/broker-workspace/0/');
   assert.equal(new URL(w.location.href).searchParams.get('sectorAccount'),id);
   assert.equal(new URL(w.location.href).searchParams.get('brokerAccount'),'0');
   assert.equal(new URL(w.location.href).searchParams.get('renkoBroker'),'DELTA_INDIA');
   assert.equal(w.document.getElementById('renko-broker').value,'DELTA_INDIA');
   assert.equal(w.SectorPulseWorkspace.workspace.id,'0');
  }
  const routed=new URL(w.BrokerForms.route('sector','/api/sector-analysis',accounts[3]));
  assert.equal(routed.pathname,'/api/motilal/sector-analysis');assert.equal(routed.searchParams.get('account_id'),'3');
 }finally{dom.window.close();}
});
test('Delta-only inventory shows unavailable sector state without selecting another account',async()=>{
 const {dom,w}=await mounted({inventory:accounts.slice(0,1)});try{
  const select=w.document.getElementById('sector-broker-account');assert.equal(select.options.length,1);assert.equal(select.value,'');
  assert.match(select.selectedOptions[0].textContent,/Sector Rotation unavailable/);
  assert.equal(w.document.getElementById('renko-broker').value,'DELTA_INDIA');
 }finally{dom.window.close();}
});

test('saved Dhan sector choice wins over new FYERS default',async()=>{
 const {dom,w}=await mounted({url:'https://example.test/broker-workspace/0/?sectorAccount=2'});try{
  assert.equal(w.BrokerForms.account('sector').id,'2');
  assert.equal(w.BrokerForms.context().workspace.id,'0');
 }finally{dom.window.close();}
});
test('FYERS default is never selected when its configuration is missing',()=>{
 const rows=choices(accounts.map(a=>a.broker==='FYERS'?{...a,configured:false}:a),{kind:'sector',workspaceId:'0'});
 assert.equal(sectorSelection(rows,{workspaceId:'0'}),null);
});
const {connectionSelection}=require('../broker-connection-status.js');
test('sidebar follows owning workspace even when sector data uses another broker',()=>{
 const actual=connectionSelection({workspace:{id:'0',broker:'DELTA_INDIA'},accounts,selectedAccount:accounts[1],selectedBroker:'FYERS'});
 assert.equal(actual.account.id,'0');assert.equal(actual.broker,'DELTA_INDIA');
});
test('temporary inventory absence retains authenticated workspace identity',()=>{
 const actual=connectionSelection({workspace:{id:'owned',broker:'DELTA_INDIA',label:'Own'},accounts:[],selectedAccount:accounts[1]});
 assert.equal(actual.account.id,'owned');assert.equal(actual.broker,'DELTA_INDIA');
});
test('inventory broker mismatch cannot redirect the workspace connection check',()=>{
 const actual=connectionSelection({workspace:{id:'0',broker:'DELTA_INDIA'},accounts:[{id:'0',broker:'FYERS'}]});
 assert.equal(actual.account,null);assert.equal(actual.broker,'DELTA_INDIA');
});
test('shared page keeps its explicit selected-account behavior',()=>{
 assert.deepEqual(connectionSelection({selectedAccount:accounts[2]}),{account:accounts[2],broker:'DHAN'});
});
test('mounted sidebar stays bound to Delta across sector-account changes',async()=>{
 const {dom,w,calls}=await mounted();try{
  const card=w.document.createElement('aside');card.className='broker-card';card.innerHTML='<span class="label">BROKER CONNECTION</span><b><span id="broker-state"></span></b><div id="configured-broker-accounts"></div>';w.document.body.append(card);
  w.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({credentials:'CONFIGURED',authentication:'VERIFIED_READ_ONLY',authentication_fresh:true})};};
  w.module={exports:{}};w.eval(fs.readFileSync('broker-connection-status.js','utf8'));
  w.dispatchEvent(new w.CustomEvent('broker-accounts-ready'));
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(w.document.querySelector('#selected-broker-connection').textContent,'Delta India · Connected');
  const sector=w.document.querySelector('#sector-broker-account');sector.value='account:2';sector.dispatchEvent(new w.Event('change',{bubbles:true}));
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(w.document.querySelector('#selected-broker-connection').textContent,'Delta India · Connected');
  assert.equal(w.BrokerForms.account('sector').id,'2');
  assert.equal(w.BrokerForms.context().workspace.id,'0');
  assert.ok(calls.some(c=>c.url==='/broker-workspace/0/api/delta-india/status'));
  assert.equal(calls.some(c=>c.url.includes('/broker-workspace/1/api/auth/')),false);
 }finally{dom.window.close();}
});

test('connection card resolves its own workspace even before form routing is ready',async()=>{
 const dom=new JSDOM('<html><body><aside class="broker-card"><span class="label">Connection</span><b><span id="broker-state"></span></b><div id="configured-broker-accounts"></div></aside></body></html>',{url:'https://example.test/broker-workspace/owned/',runScripts:'outside-only'}),w=dom.window,calls=[];
 try{
  w.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>url.includes('workspace-context')?{workspace:{id:'owned',broker:'DELTA_INDIA'}}:{credentials:'CONFIGURED'}};};
  w.eval(fs.readFileSync('broker-connection-status.js','utf8'));
  w.dispatchEvent(new w.CustomEvent('broker-accounts-ready'));
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(w.document.querySelector('#selected-broker-connection').textContent,'Delta India · Connected');
  assert.ok(calls.includes('/api/workspace-context'));
  assert.ok(calls.includes('/broker-workspace/owned/api/delta-india/status'));
 }finally{dom.window.close();}
});
