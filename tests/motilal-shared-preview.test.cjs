const {test}=require('node:test');
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('dashboard-enhancements.js','utf8');
function fixture(){
 const calls=[],id='a'.repeat(32),context={Map,Error,JSON,window:{BrokerForms:{kind:()=> 'manual',account:()=>({id}),fetch:async(kind,url,options)=>{calls.push({kind,url,body:JSON.parse(options.body)});return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({preview_id:'MO-test',broker:'MOTILAL_OSWAL',account_id:id})};}}}};
 const a=source.indexOf('  const previewAccounts = new Map()'),b=source.indexOf('  // KAMA has no ticket',a);
 assert.ok(a>=0&&b>a);vm.runInNewContext(source.slice(a,b)+'\nthis.postJson=postJson;',context);return {...context,calls,id};
}
test('native reviewed submission retains the account of its prepared ticket',async()=>{
 const f=fixture();await f.postJson('/api/trade-ticket/prepare',{broker:'MOTILAL_OSWAL',account_id:f.id});
 await f.postJson('/api/trade-ticket/submit',{preview_id:'MO-test',confirmation:'exact'});
 assert.equal(f.calls[1].body.broker,'MOTILAL_OSWAL');assert.equal(f.calls[1].body.account_id,f.id);
 assert.equal(f.calls[1].body.confirmation,'exact');
});
test('native submission with missing review context never reaches transport',async()=>{
 const f=fixture();await assert.rejects(()=>f.postJson('/api/trade-ticket/submit',{preview_id:'MO-lost'}),/context is missing/);assert.equal(f.calls.length,0);
});
test('canonical page loads routing before dashboard and account inventory afterwards',()=>{
 const page=fs.readFileSync('index.html','utf8'),routing=page.indexOf('src="/broker-form-routing.js'),dashboard=page.indexOf('src="/dashboard-enhancements.js'),accounts=page.indexOf('src="/broker-account-options.js');
 assert.ok(routing>=0&&routing<dashboard&&accounts>dashboard);
});
