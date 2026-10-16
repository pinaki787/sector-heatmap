const test=require('node:test'),assert=require('node:assert/strict');
const ready=require('../paper-capital.js');
test('Paper distinguishes an unavailable service from a missing deployed revision',async()=>{
 global.fetch=async()=>({ok:false,status:503});
 await assert.rejects(ready.ensure('PAPER'),/HTTP 503.*No new Paper session/);
 global.fetch=async()=>({ok:true,status:200,json:async()=>({revision:'older'})});
 await assert.rejects(ready.ensure('paper'),/has not loaded the required Paper capital revision/);
 global.fetch=async()=>({ok:true,status:200,json:async()=>({revision:'paper-capital-inr-v1'})});
 await ready.ensure('PAPER');
});
test('Paper reports expired login separately and never starts a session',async()=>{
 global.fetch=async()=>({ok:false,status:401});
 await assert.rejects(ready.ensure('PAPER'),/login expired/);
});
test('Live keeps its existing checks and does not request Paper capability',async()=>{
 global.fetch=async()=>{throw Error('Paper endpoint must not be requested');};
 await ready.ensure('LIVE');
});
