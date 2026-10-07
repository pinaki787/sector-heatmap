const test=require('node:test'),assert=require('node:assert/strict');
const ready=require('../paper-capital.js');
test('Paper refuses a deployed backend that cannot honor virtual capital',async()=>{
 global.fetch=async()=>({ok:false});await assert.rejects(ready.ensure('PAPER'),/awaits backend deployment/);
 global.fetch=async()=>({ok:true,json:async()=>({revision:'older'})});await assert.rejects(ready.ensure('paper'),/awaits backend deployment/);
 global.fetch=async()=>({ok:true,json:async()=>({revision:'paper-capital-inr-v1'})});await ready.ensure('PAPER');
});
test('Live keeps its existing checks and does not request Paper capability',async()=>{
 global.fetch=async()=>{throw Error('Paper endpoint must not be requested');};await ready.ensure('LIVE');
});
