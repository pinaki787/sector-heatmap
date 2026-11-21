const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(){
 const controls=new Map(),calls=[],location={href:'https://portal.example/',origin:'https://portal.example',search:''};
 const window={addEventListener(){},dispatchEvent(){},fetch:async(url,options)=>{calls.push({url,options});return {ok:true}}};
 const document={getElementById:id=>controls.get(id),querySelector:()=>null};
 vm.runInNewContext(fs.readFileSync('broker-form-routing.js','utf8'),{window,document,location,URL,URLSearchParams,Promise,CustomEvent:class{}});
 const accounts=[{id:'fyers-owner',broker:'FYERS'},{id:'delta-owner',broker:'DELTA_INDIA'},{id:'dhan-owner',broker:'DHAN'}];
 window.BrokerForms.setAccounts(accounts);controls.set('renko-broker',{value:'account:fyers-owner'});
 return {router:window.BrokerForms,accounts,calls,controls};
}
test('FYERS Renko search routes to the selected private FYERS account',async()=>{
 const {router,accounts,calls}=setup();
 assert.equal(router.route('renko','/api/ema-band/underlying-search?q=NIFTY&market=NSE_INDEX',accounts[0]),'https://portal.example/broker-workspace/fyers-owner/api/ema-band/underlying-search?q=NIFTY&market=NSE_INDEX');
 await router.fetch('renko','/api/ema-band/underlying-search?q=NIFTY');assert.equal(calls.length,1);
 assert.match(calls[0].url,/broker-workspace\/fyers-owner/);
});
test('the exception cannot redirect Delta or Dhan to FYERS instruments',()=>{
 const {router,accounts}=setup();
 for(const account of accounts.slice(1))assert.throws(()=>router.route('renko','/api/ema-band/underlying-search?q=NIFTY',account),/differs/);
});
test('instrument lookup exception permits only GET, never actions',async()=>{
 const {router,calls}=setup();
 for(const method of ['POST','PUT','DELETE'])await assert.rejects(router.fetch('renko','/api/ema-band/underlying-search',{method}),/read-only/);
 assert.equal(calls.length,0);
});
test('other strategy routes, near-match paths, external origins and cross-broker actions remain blocked',()=>{
 const {router,accounts}=setup();
 for(const url of ['/api/ema-band/runner','/api/ema-band/underlying-search/start','/api/renko-delta/start','https://outside.example/api/ema-band/underlying-search'])assert.throws(()=>router.route('renko',url,accounts[0]),/differs/);
});
