const {test}=require('node:test');
const assert=require('node:assert/strict');
const {eligible,jobsURL,createClient}=require('../analysis-jobs.js');
test('only research and runner activation are queued; orders stay explicit',()=>{
 for(const path of ['/api/analysis-handoff/analyze','/api/dhan/analysis-handoff/analyze-market','/api/renko/start'])assert(eligible(path,'POST'));
 for(const path of ['/api/trade-ticket/submit','/api/trade-ticket/preview','/api/renko/stop','/api/auth/login'])assert(!eligible(path,'POST'));
});
test('job retrieval retains selected workspace and native broker account',()=>{
 const id='a'.repeat(32);
 assert.equal(jobsURL('https://host/broker-workspace/'+id+'/api/analyze',id).pathname,'/broker-workspace/'+id+'/api/jobs');
 assert.equal(jobsURL('https://host/api/dhan/analysis-handoff/analyze',id).searchParams.get('account_id'),id);
});
test('watchers share one poll and cancellation targets the account',async()=>{
 let calls=0;let cancelled;const base='https://host/api/jobs?account_id=selected';
 const client=createClient(async(url,options={})=>{if(options.method==='POST'){cancelled={url,body:JSON.parse(options.body)};return {ok:true,json:async()=>({status:'CANCELLING'})};}calls++;return {ok:true,json:async()=>({job_id:'job',terminal:calls>1,status:calls>1?'COMPLETED':'RUNNING',output:calls>1?{saved:1}:null})};},{sleep:async()=>{}});
 const a=client.watch(base,'job'),b=client.watch(base,'job');assert.equal(a,b);
 assert.deepEqual((await a).output,{saved:1});assert.equal(calls,2);
 await client.cancel(base,'job');assert.equal(cancelled.body.account_id,'selected');assert.match(cancelled.url,/jobs\/cancel/);
});
