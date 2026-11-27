const test=require('node:test'),assert=require('node:assert/strict');
const {manualRequestNotice}=require('../renko-ai-options.js');
test('submission acknowledgement stays pending until actual fill or rejection',()=>{
 for(const phase of ['QUEUED','CLAIMED','PREPARING','SUBMITTING'])assert.equal(manualRequestNotice({manual_entry:{phase},notice:'Manual entry requested; strategy exits active'}),'Manual entry queued · awaiting runner and broker confirmation.');
});
test('rejection replaces acceptance notice and unresolved state never claims a position',()=>{
 assert.equal(manualRequestNotice({running:true,manual_entry:{phase:'REJECTED',error:'Executable depth is stale; no order sent'},notice:'Manual entry requested'}),'REJECTED · Executable depth is stale; no order sent');
 assert.equal(manualRequestNotice({running:true,manual_entry:{phase:'FAILED_OR_PENDING',error:'Reconcile'}}),'FAILED_OR_PENDING · Reconcile');
 assert.equal(manualRequestNotice({manual_entry:{phase:'FILLED'}}),'FILLED');
});
