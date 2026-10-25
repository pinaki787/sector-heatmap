const {test}=require('node:test'),assert=require('node:assert/strict');
const {policyPayload}=require('../handoff-schedule.js');
test('schedule binds explicit mode and capital to one owned account',()=>{
 const fields={capital:100000,enabled:true,mode:'MANUAL',ai_provider:'RULES_ONLY'};
 assert.equal(policyPayload(fields,{id:'owned'}).live_authorized,false);
 assert.equal(policyPayload({...fields,mode:'AUTO'},{id:'owned'}).live_authorized,true);
 for(const capital of [NaN,Infinity,0,100001])assert.throws(()=>policyPayload({...fields,capital},{id:'owned'}));
 assert.throws(()=>policyPayload(fields,null));
});

test('duplicate reporting is explicit and independent of Live authorization',()=>{const a={id:'owned'},f={capital:100000,enabled:true,mode:'MANUAL',ai_provider:'RULES_ONLY'};assert.equal(policyPayload(f,a).allow_duplicate_reports,false);assert.equal(policyPayload({...f,allow_duplicate_reports:true},a).allow_duplicate_reports,true);assert.equal(policyPayload({...f,allow_duplicate_reports:true},a).live_authorized,false);assert.equal(policyPayload({...f,allow_duplicate_reports:'true'},a).allow_duplicate_reports,false);});
