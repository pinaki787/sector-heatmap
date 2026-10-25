const {test}=require('node:test'),assert=require('node:assert/strict');
const {read}=require('../sector-detail-client.js');
function xhr(status,body,events){
 return class {open(...args){events.push(args)}setRequestHeader(){}send(){this.status=status;this.responseText=body;this.onload()}}
}
test('read-only fallback retains exact owned sidecar path',async()=>{
 const events=[],value=await read('a'.repeat(32),'pharma','intraday',xhr(200,JSON.stringify({sector:{sector_id:'pharma'}}),events));
 assert.equal(events.length,1);assert.equal(events[0][0],'GET');
 const url=new URL(events[0][1],'https://portal.example');
 assert.equal(url.pathname,'/api/notification-admin/sector-detail');assert.equal(url.searchParams.get('account_id'),'a'.repeat(32));
 assert.equal(value.sector.sector_id,'pharma');
});
test('HTML gateway and permission errors remain errors, never fabricated charts',async()=>{
 await assert.rejects(read('a'.repeat(32),'pharma','intraday',xhr(502,'<html>bad gateway</html>',[])),/temporarily unavailable/);
 await assert.rejects(read('a'.repeat(32),'pharma','intraday',xhr(403,JSON.stringify({error:'Not assigned'}),[])),/Not assigned/);
});
test('missing account cannot silently use a different broker',async()=>{
 await assert.rejects(read('', 'pharma','intraday'),/saved sector data account/);
});
