const test=require('node:test'),assert=require('node:assert/strict');
const {positionControlView,positionControlPayload}=require('../renko-ai-options.js');
const account={id:'owner',broker:'FYERS'},values={underlying:'MCX:CRUDEOILM26DECFUT'};
const context={account_id:'owner',broker:'FYERS',run_id:'run',runtime_session:'session',underlying:values.underlying,mode:'LIVE',route:'OPTIONS',timeframe:1};
test('Detach becomes Attach only after confirmed detached ownership',()=>{
 const live={position_control_capable:true,ownership:{position:{symbol:'CALL'}},position_control:{mode:'MANAGED'}};
 assert.equal(positionControlView(live).label,'Detach');
 assert.equal(positionControlView({...live,position_control_receipt:{phase:'CLAIMED'}}).blocked,true);
 const detached={...live,ownership:{position:null,detached_position:{symbol:'CALL'}},position_control:{mode:'DETACHED'},position_control_receipt:{phase:'DETACHED'}};
 assert.equal(positionControlView(detached).label,'Attach');assert.match(positionControlView(detached).status,/remains open/);
});
test('Stop receipt never reports square-off for unresolved broker state',()=>{
 const result=positionControlView({position_control_receipt:{phase:'RECOVERY_REQUIRED',error:'Unresolved fill'}});
 assert.equal(result.status,'Unresolved fill');
 assert.equal(positionControlView({position_control_receipt:{phase:'STOPPED',broker_flat_confirmed:true}}).status,'Squared off · stopped');
});
test('payload binds exact account run and real selected holding without entry direction',()=>{
 const snapshot={position_control_context:context,position_control_capable:true};
 assert.throws(()=>positionControlPayload(snapshot,values,{...account,id:'wrong'},'STOP','id'),/active strategy/);
 assert.throws(()=>positionControlPayload(snapshot,values,account,'ATTACH','id'),/actual open/);
 const body=positionControlPayload(snapshot,values,account,'ATTACH','id',{account:'owner',underlying:values.underlying,symbol:'EXACT',quantity:1,product:'MARGIN'});
 assert.deepEqual(body.holding,{symbol:'EXACT',quantity:1,product:'MARGIN'});assert.equal(body.operation,'ATTACH');assert.equal(body.direction,undefined);
});


test('retained uncertain order permits a Stop recovery request but blocks ownership transfer',()=>{
 const view=positionControlView({position_control_capable:true,ownership:{pending:{stage:'FILLED_AWAITING_FLAT'}}});
 assert.equal(view.blocked,true);assert.equal(view.stopBlocked,false);
});

test('native readiness is account source product timeframe and expiry bound for both brokers',()=>{
 const {nativeBrokerReady}=require('../renko-ai-options.js');
 for(const broker of ['DHAN','MOTILAL_OSWAL']){
  const a={id:'owner',broker},v={underlying:'MCX:CRUDE',timeframe:'1 minute',product:broker==='DHAN'?'MARGIN':'NORMAL',underlyingSignals:true,dataAccount:'data-owner'};
  const proof={market_data_broker:'FYERS',market_data_account:'data-owner',ready:true,account_id:a.id,broker,underlying:v.underlying,timeframe:1,product:v.product,signal_source:'UNDERLYING',valid_until:101};
  const snapshot={motilal_fyers_data_ready:true,native_broker_integration_ready:true,native_broker_readiness:proof};
  assert.equal(nativeBrokerReady(snapshot,a,v,100),true);
  for(const change of [{account_id:'other'},{broker:'FYERS'},{underlying:'OTHER'},{timeframe:5},{product:'INTRADAY'},{signal_source:'PREMIUM'},{valid_until:100},{ready:false}])
   assert.equal(nativeBrokerReady({...snapshot,native_broker_readiness:{...proof,...change}},a,v,100),false);
  assert.equal(nativeBrokerReady({...snapshot,native_broker_integration_ready:false},a,v,100),false);
 }
});

test('native ISO expiry values retain exact selection and use verified venue expiry cutoff',()=>{
 const {expiryDeadline}=require('../renko-ai-options.js');
 assert.equal(expiryDeadline({value:'2026-12-16',expires_at:1797439500}),1797439500000);
 assert.equal(expiryDeadline({value:'1797439500'}),1797439500000);
 assert.equal(Number.isNaN(expiryDeadline({value:'2026-12-16'})),true);
});

test('position controls cannot operate a Live run through a Paper or different-source draft',()=>{
 const snapshot={position_control_context:context,position_control_capable:true};
 for(const changes of [{execution:'PAPER'},{route:'DIRECT'},{timeframe:'5 minutes'}])
  assert.throws(()=>positionControlPayload(snapshot,{...values,...changes},account,'STOP','id'),/active run/);
 assert.equal(positionControlPayload(snapshot,{...values,execution:'LIVE',route:'OPTIONS',timeframe:'1 minute'},account,'STOP','id').operation,'STOP');
});
test('an options readiness proof cannot qualify a Dhan direct run',()=>{
 const {nativeBrokerReady}=require('../renko-ai-options.js');
 const account={broker:'DHAN',id:'owner'},values={underlying:'NSE_FNO:123',timeframe:'1 minute',product:'MARGIN',route:'DIRECT'};
 const proof={ready:true,account_id:'owner',broker:'DHAN',underlying:values.underlying,timeframe:1,product:'MARGIN',signal_source:'UNDERLYING',valid_until:200};
 const snapshot={native_broker_integration_ready:true,dhan_direct_ready:true,native_broker_readiness:proof};
 assert.equal(nativeBrokerReady(snapshot,account,values,100),false);
 assert.equal(nativeBrokerReady({...snapshot,native_broker_readiness:{...proof,execution_route:'DIRECT'}},account,values,100),true);
 assert.equal(nativeBrokerReady({...snapshot,dhan_direct_ready:false,native_broker_readiness:{...proof,execution_route:'DIRECT'}},account,values,100),false);
});
