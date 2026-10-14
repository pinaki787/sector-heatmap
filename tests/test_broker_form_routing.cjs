const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(){
 const controls=new Map(),events=[],location={href:'https://portal.example/',origin:'https://portal.example',search:''};
 const window={addEventListener(){},dispatchEvent(e){events.push(e)},fetch:async()=>({ok:true})};
 const context={window,document:{getElementById:id=>controls.get(id),querySelector:()=>null},location,history:{replaceState(a,b,u){location.search=u.search}},URL,URLSearchParams,Promise,CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}}};
 vm.runInNewContext(fs.readFileSync('broker-form-routing.js','utf8'),context);
 const accounts=[{id:'dhan-owner',broker:'DHAN'},{id:'fyers-owner',broker:'FYERS'},{id:'delta-owner',broker:'DELTA_INDIA'}];
 window.BrokerForms.setAccounts(accounts);return{router:window.BrokerForms,controls,events,location,window,accounts};
}
test('Dhan uses native owned adapters while saved FYERS and Delta use private transport',()=>{
 const {router,accounts}=setup();
 assert.equal(router.route('band','/api/ema-band/runner',accounts[0]),'https://portal.example/api/band-dhan/dhan-owner/form-runner');
 assert.equal(router.route('rsi','/api/ema-band/chart?q=1',accounts[0]),'https://portal.example/api/ema-dhan/dhan-owner/form-chart?q=1');
 assert.equal(router.route('kama','/api/kama/runner/start',accounts[0]),'https://portal.example/api/kama-dhan/dhan-owner/form-runner-start');
 assert.equal(router.route('band','/api/ema-band/runner',accounts[1]),'https://portal.example/broker-workspace/fyers-owner/api/ema-band/runner');
 assert.equal(router.route('renko','/api/renko-delta/runner',accounts[2]),'https://portal.example/broker-workspace/delta-owner/api/renko-delta/runner');
 assert.equal(router.route('manual','/api/trade-ticket/preview',accounts[0]),'https://portal.example/broker-workspace/dhan-owner/api/trade-ticket/preview');
 assert.equal(router.route('band','https://outside.example/api/ema-band/runner',accounts[0]),'https://outside.example/api/ema-band/runner');
});
test('selecting broker in Band, RSI and KAMA stays on existing page without runner actions',()=>{
 for(const kind of ['band','rsi','kama']){
  const {router,accounts,location,events,window}=setup();let calls=0;window.fetch=()=>{calls++;};
  router.onChange(kind,accounts[0]);assert.equal(location.href,'https://portal.example/');
  assert.equal(calls,0);assert.equal(events[0].detail.kind,kind);
 }
});
test('late old-account response is rejected after account selection changes',async()=>{
 const {router,controls,window,accounts}=setup();
 const control={value:'account:'+accounts[0].id};controls.set('ema-band-broker-account',control);
 let complete,started;const began=new Promise(resolve=>{started=resolve});window.fetch=()=>new Promise(resolve=>{complete=resolve;started();});
 const pending=router.fetch('band','/api/ema-band/runner');await began;
 control.value='account:'+accounts[1].id;complete({ok:true});
 await assert.rejects(pending,/account changed/i);
});
test('choosing server default cannot retain private-account routing from old query',()=>{
 const {router,controls,location}=setup();location.search='?bandAccount=dhan-owner';
 controls.set('ema-band-broker-account',{value:'FYERS'});assert.equal(router.account('band'),null);
});

test('sector summary and detail use selected private FYERS account, never shared token',async()=>{
 const {router,controls,window}=setup();
 controls.set('sector-broker-account',{value:'account:fyers-owner'});
 const urls=[];window.fetch=async url=>{urls.push(url);return {ok:true}};
 for(const url of ['/api/sector-analysis?mode=intraday','/api/sector-analysis/detail?sector=bank']){
  assert.equal(router.kind(url),'sector');await router.fetch(router.kind(url),url);
 }
 assert.equal(urls.length,2);
 assert.ok(urls.every(url=>url.startsWith('https://portal.example/broker-workspace/fyers-owner/api/sector-analysis')));
});
test('sector requests fail closed without an owned account',async()=>{
 const {router,window}=setup();let calls=0;window.fetch=async()=>{calls++};
 await assert.rejects(router.fetch('sector','/api/sector-analysis'),/Select a configured broker account/);
 assert.equal(calls,0);
});

test('Renko broker switching replaces both account parameters atomically',()=>{
 const {router,accounts,location,window}=setup();
 location.href='https://portal.example/?renkoAccount=fyers-owner&brokerAccount=fyers-owner&renkoBroker=FYERS&renkoInstance=old';
 let calls=0;window.fetch=()=>{calls++;};
 router.onChange('renko',accounts[0]);
 const url=new URL(location.href);
 assert.equal(url.searchParams.get('renkoAccount'),'dhan-owner');
 assert.equal(url.searchParams.get('brokerAccount'),'dhan-owner');
 assert.equal(url.searchParams.get('renkoBroker'),'DHAN');
 assert.equal(url.searchParams.has('renkoInstance'),false);
 assert.equal(calls,0);
});

test('Dhan sector summary and detail use its native account data endpoint',async()=>{
 const {router,controls,window}=setup(),urls=[];
 controls.set('sector-broker-account',{value:'account:dhan-owner'});
 window.fetch=async url=>{urls.push(new URL(url));return {ok:true}};
 await router.fetch('sector','/api/sector-analysis?mode=swing');
 await router.fetch('sector','/api/sector-analysis/detail?mode=swing&sector=bank');
 assert.deepEqual(urls.map(u=>u.pathname),['/api/dhan/sector-analysis','/api/dhan/sector-analysis/detail']);
 assert.ok(urls.every(u=>u.searchParams.get('account_id')==='dhan-owner'&&u.searchParams.get('mode')==='swing'));
 assert.equal(urls[1].searchParams.get('sector'),'bank');
});
test('Delta cannot use an Indian sector data route',async()=>{
 const {router,controls,window}=setup();let calls=0;window.fetch=async()=>{calls++};
 controls.set('sector-broker-account',{value:'account:delta-owner'});
 await assert.rejects(router.fetch('sector','/api/sector-analysis'),/sector market data is not available/);
 assert.equal(calls,0);
});

test('Dhan handoff uses native account evidence while FYERS retains its private workspace',()=>{
 const {router,accounts}=setup();
 for(const action of ['candidates','analyze','size','preview']){
  const url='/api/analysis-handoff/'+action;
  assert.equal(router.kind(url),'handoff');
  assert.equal(router.route('handoff',url,accounts[0]),'https://portal.example/api/dhan/analysis-handoff/'+action+'?account_id=dhan-owner');
  assert.equal(router.route('handoff',url,accounts[1]),'https://portal.example/broker-workspace/fyers-owner'+url);
 }
});
test('Dhan account data uses native endpoints without rewriting analysis as FYERS',()=>{
 const {router,accounts}=setup();
 assert.equal(router.route('account','/api/account',accounts[0]),'https://portal.example/api/dhan/account?account_id=dhan-owner');
});

test('positions selection preserves the independently selected Renko broker and instance',()=>{
 const {router,accounts,location}=setup();
 location.href='https://portal.example/?renkoAccount=dhan-owner&renkoBroker=DHAN&renkoInstance=retained';
 router.onChange('account',accounts[1]);
 const p=new URLSearchParams(location.search);
 assert.equal(p.get('renkoAccount'),'dhan-owner');
 assert.equal(p.get('renkoBroker'),'DHAN');
 assert.equal(p.get('renkoInstance'),'retained');
 assert.equal(p.get('accountAccount'),'fyers-owner');
});

test('FYERS parser scopes every endpoint to the selected account and rejects absent or unsupported accounts',async()=>{
 const {router,controls,window,accounts}=setup();
 const calls=[];window.fetch=async url=>{calls.push(url);return {ok:true}};
 controls.set('parser-broker-account',{value:'account:fyers-owner'});
 for(const action of ['parse','quote','ai-analysis','prepare-order','submit-direct','lifecycle']){
  const url='/api/trade-recommendation/'+action;
  assert.equal(router.kind(url),'parser');
  await router.fetch('parser',url);
  assert.equal(calls.at(-1),'https://portal.example/broker-workspace/fyers-owner'+url);
 }
 controls.set('parser-broker-account',{value:''});
 await assert.rejects(router.fetch('parser','/api/trade-recommendation/submit-direct'),/configured broker account/);
 assert.throws(()=>router.route('parser','/api/trade-recommendation/quote',accounts[0]),/FYERS account/);
 assert.equal(calls.length,6);
});

test('Renko initialization binds the same account as a sector-origin page',()=>{
 const {router,location}=setup();
 location.search='?brokerForm=sector&brokerAccount=dhan-owner&renkoInstance=owned';
 assert.equal(router.initial('renko'),'dhan-owner');
 location.search+='&renkoAccount=fyers-owner';
 assert.equal(router.initial('renko'),'fyers-owner');
});
