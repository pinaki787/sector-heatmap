const test=require('node:test'),assert=require('node:assert/strict');
const {supported,protectable,eligible,owns,endpoint}=require('../analysis-trailing.js');
const account={id:'dhan-a',broker:'DHAN',configured:true};
const row={kind:'DELIVERY_EQUITY',quantity:500,action:'TRAIL',candidate_stop:92.58,native_identity:{securityId:'42',exchangeSegment:'NSE_EQ'}};
test('configured broker accounts use their own protection routes',()=>{
 assert.equal(supported(account),true);
 for(const broker of ['FYERS','MOTILAL_OSWAL','DELTA_INDIA'])assert.equal(supported({...account,broker}),true);
 assert.throws(()=>endpoint({...account,broker:'UNKNOWN'},'/api/holdings-analysis/trail-enable'));
 assert.equal(supported({...account,configured:false}),false);
});
test('account and action boundary rejects conflicting or arbitrary routes',()=>{
 assert.equal(endpoint(account,'/api/holdings-analysis/trail-stop',{account_id:'dhan-a',broker:'DHAN'}),'/api/dhan/holdings-analysis/trail-stop?account_id=dhan-a');
 assert.throws(()=>endpoint(account,'/api/holdings-analysis/trail-enable',{account_id:'dhan-b'}));
 assert.throws(()=>endpoint(account,'/api/holdings-analysis/trail-enable',{broker:'FYERS'}));
 assert.throws(()=>endpoint(account,'/api/trade-ticket/submit'));
});
test('only held delivery equity is eligible, not candidate or option or short',()=>{
 assert.equal(eligible(row),true);
 for(const changed of [{quantity:0},{quantity:-5},{kind:'LONG_OPTION'},{native_identity:{securityId:'42',exchangeSegment:'MCX_COMM'}},{native_identity:{}},{action:'EXIT'},{candidate_stop:0}])assert.equal(eligible({...row,...changed}),false);
 assert.equal(protectable({...row,action:'HOLD'}),true,'existing monitors remain accessible if recommendation changes');
});
test('restoration binds source section, account, broker and saved portfolio',()=>{
 const job={kind:'ANALYSIS',feature:'holdings',request:{account_id:'dhan-a',payload:{broker:'DHAN',trailing_origin:'screener'}},output:{account_id:'dhan-a'}};
 assert.equal(owns(job,'dhan-a','screener'),true);
 assert.equal(owns(job,'dhan-a','handoff'),false);
 assert.equal(owns(job,'dhan-b','screener'),false);
 assert.equal(owns({...job,output:{account_id:'dhan-b'}},'dhan-a','screener'),false);
 assert.equal(owns({...job,kind:'RUNNER'},'dhan-a','screener'),false);
});

test('broker routes and crypto short positions retain their own ownership',()=>{
 assert.equal(endpoint({...account,broker:'FYERS'},'/api/holdings-analysis/trail-status'),'/broker-workspace/dhan-a/api/holdings-analysis/trail-status?account_id=dhan-a');
 assert.equal(endpoint({...account,broker:'MOTILAL_OSWAL'},'/api/holdings-analysis/trail-status'),'/api/motilal/holdings-analysis/trail-status?account_id=dhan-a');
 assert.equal(endpoint({...account,broker:'DELTA_INDIA'},'/api/holdings-analysis/trail-status'),'/broker-workspace/dhan-a/api/delta-india/holdings-analysis/trail-status?account_id=dhan-a');
 assert.equal(eligible({...row,kind:'LINEAR_FUTURE',quantity:-10,native_identity:{securityId:'42',exchangeSegment:'DELTA_24X7'}}),true);
});
