
const test=require('node:test'),assert=require('node:assert/strict');
const {chartLayoutVisible}=require('../renko-ai-options.js');
test('split charts show only requested instruments and preserve single-tab selection',()=>{
 for(const active of ['underlying','call','put','owned']){
  const tabs=['underlying','call','put','owned'];
  assert.deepEqual(tabs.filter(t=>chartLayoutVisible('single',t,active)),[active]);
  assert.deepEqual(tabs.filter(t=>chartLayoutVisible('underlying-call',t,active)),['underlying','call']);
  assert.deepEqual(tabs.filter(t=>chartLayoutVisible('underlying-put',t,active)),['underlying','put']);
  assert.deepEqual(tabs.filter(t=>chartLayoutVisible('three',t,active)),['underlying','call','put']);
 }
});
