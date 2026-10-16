
const assert=require('node:assert/strict');
const test=require('../broker-connection-test.js');
(async()=>{
 for(const [broker,data,path,method] of [
 ['FYERS',{connected:true},'/broker-workspace/account/api/account',undefined],
 ['DHAN',{authenticated:true},'/api/dhan/status?account_id=account',undefined],
 ['DELTA_INDIA',{authentication:'VERIFIED_READ_ONLY'},'/broker-workspace/account/api/delta-india/verify-auth','POST']]){
 let calls=0;
 await test({id:'account',broker},async(url,options)=>{calls++;assert.equal(url,path);assert.equal(options.method,method);return {ok:true,json:async()=>data}});
 assert.equal(calls,1);
 await assert.rejects(test({id:'account',broker},async()=>({ok:true,json:async()=>({})})));
 await assert.rejects(test({id:'account',broker},async()=>({ok:false,json:async()=>({error:'Rejected'})})),/Rejected/);
 }
 await assert.rejects(test({broker:'FYERS'},()=>{throw Error('must not fetch')}));
 console.log('All broker connection checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
