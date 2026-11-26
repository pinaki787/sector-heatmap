const test=require('node:test'),assert=require('node:assert/strict');
const {positionControlView,positionControlPayload}=require('../renko-ai-options.js');
const account={id:'a'.repeat(32),broker:'FYERS'},symbol='MCX:CRUDEOILM26DECFUT';
const values={underlying:symbol,execution:'LIVE',route:'OPTIONS',timeframe:'1 minute'};
function state(){return {running:true,position_control_capable:true,position_control_context:{account_id:account.id,broker:account.broker,run_id:'run-1',runtime_session:'bound-session',underlying:symbol,mode:'LIVE',route:'OPTIONS',timeframe:1},position_control:{mode:'MANAGED'},ownership:{position:{symbol:'EXACT',quantity:1,spot_brick:7.142857142857143,option_brick:3.5714285714285716,fill_price:390}}};}
test('Detach sends only bound ownership intent and preserves the captured holding geometry',()=>{
 const s=state(),copy=JSON.stringify(s),p=positionControlPayload(s,values,account,'DETACH','id');
 assert.equal(positionControlView(s).label,'Detach');assert.equal(p.operation,'DETACH');assert.equal(p.run_id,'run-1');
 assert.equal(p.holding,undefined);assert.equal(p.direction,undefined);assert.equal(JSON.stringify(s),copy);
 const detached={...s,ownership:{position:null,detached_position:s.ownership.position},position_control:{mode:'DETACHED'}};
 assert.equal(positionControlView(detached).label,'Attach');
});
test('unavailable backend capability and foreign source cannot enqueue a Detach intent',()=>{
 const s=state();
 assert.throws(()=>positionControlPayload({...s,position_control_capable:false},values,account,'DETACH','id'),/not loaded/);
 assert.throws(()=>positionControlPayload(s,values,{...account,id:'foreign'},'DETACH','id'),/active strategy/);
 assert.throws(()=>positionControlPayload(s,{...values,underlying:'OTHER'},account,'DETACH','id'),/active strategy/);
 assert.equal(positionControlView({...s,ownership:{pending:{}}}).blocked,true);
});
