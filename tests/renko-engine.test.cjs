const test=require('node:test'),assert=require('node:assert/strict');
const {canStartRunner}=require('../renko-engine.js');
const ready={account:{id:'private'},symbol:'ETHUSD',mode:'PAPER',state:{running:false,live_available:false}};
test('Start is available with selected Paper configuration and no preview token',()=>assert.equal(canStartRunner(ready),true));
test('Start preserves account, selection, state, exposure, busy and Live capability checks',()=>{
 for(const changes of [{account:null},{symbol:''},{mode:'BACKTEST'},{state:null},{busy:true},{state:{running:true}},{state:{position:{}}},{state:{pending:{}}},{mode:'LIVE'}])assert.equal(canStartRunner({...ready,...changes}),false);
 assert.equal(canStartRunner({...ready,mode:'LIVE',state:{live_available:true}}),true);
});
const {startRunner}=require('../renko-engine.js');
test('Current backend receives full settings in one Start request',async()=>{
 const calls=[],settings={mode:'PAPER',engine_settings:{percent:.66}};
 await startRunner(async(...args)=>{calls.push(args);return {running:true};},settings,'renko-engine-direct-start-v2');
 assert.deepEqual(calls,[['start',settings]]);
});
test('Already-running older backend prepares internally without a confirmation window',async()=>{
 const calls=[];await startRunner(async(action,data)=>{calls.push([action,data]);return action==='preview'?{id:'token',confirmation:'internal'}:{running:true};},{mode:'PAPER'},'renko-engine-broker-v1');
 assert.deepEqual(calls,[['preview',{mode:'PAPER'}],['start',{preview_id:'token',confirmation:'internal'}]]);
});
