const {test}=require('node:test'),assert=require('node:assert/strict');
const {positionControlView,journalQuantity,manualRequestLabel}=require('../renko-ai-options.js');
test('only the exact resolved prior recovery receipt stops showing as a current error',()=>{
 const snapshot={running:false,ownership:{position:null,pending:null},reconciliation:{phase:'RECOVERED_CLOSED',key:'owned',completed_at:100},position_control_receipt:{phase:'RECOVERY_REQUIRED',error:'obsolete limit error',updated_at:90,retained_pending:{key:'owned'}}};
 assert.match(positionControlView(snapshot).status,/reconciled/);
 for(const change of [{running:true},{ownership:{pending:{key:'other'}}},{position_control_receipt:{...snapshot.position_control_receipt,updated_at:110}},{reconciliation:{...snapshot.reconciliation,key:'other'}}]){
  assert.match(positionControlView({...snapshot,...change}).status,/obsolete/);
 }
});
test('tiny contract multipliers are exact fractions rather than misleading zero',()=>{
 assert.equal(journalQuantity(10,.001),'10.00 × 1/1,000');
 assert.equal(journalQuantity(50,1),'50.00 × 1.00');
});
test('earlier rejected manual requests are clearly historical only while stopped and unowned',()=>{
 const snapshot={running:false,ownership:{position:null,pending:null},manual_entry:{phase:'REJECTED',error:'depth unavailable'}};
 assert.match(manualRequestLabel(snapshot),/^Previous run/);
 assert.match(manualRequestLabel({...snapshot,running:true}),/^REJECTED/);
});

test('an active worker recovery pause is visible even without an outstanding command',()=>{
 const view=positionControlView({running:true,ownership:{position:null,pending:null},position_control:{mode:'RECOVERY_REQUIRED',entries_paused:true}});
 assert.match(view.status,/Recovery pause/);assert.match(view.status,/entries disabled/);
});
