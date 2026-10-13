/* Read-only validation of the selected user's saved broker credentials. */
(function(root){
'use strict';
async function testConnection(account,request){
 if(!account?.id||!['FYERS','DHAN','DELTA_INDIA'].includes(account.broker))throw Error('Select a saved broker account.');
 const prefix='/broker-workspace/'+encodeURIComponent(account.id);
 const url=account.broker==='DHAN'?'/api/dhan/status?account_id='+encodeURIComponent(account.id):prefix+(account.broker==='FYERS'?'/api/account':'/api/delta-india/verify-auth');
 const response=await request(url,account.broker==='DELTA_INDIA'?{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}:{cache:'no-store'});
 const data=await response.json();
 if(!response.ok)throw Error(String(data.error||data.message||'Broker rejected the connection test.').replace(' Do not retry an uncertain order submission.',''));
 const connected=account.broker==='FYERS'?data.connected===true:account.broker==='DHAN'?data.authenticated===true:data.authenticated===true||data.authentication==='VERIFIED_READ_ONLY';
 if(!connected)throw Error(data.error||data.message||'Authentication not confirmed. Complete broker login or renew the saved credentials.');
 return {connected:true};
}
root.testBrokerConnection=account=>testConnection(account,root.fetch.bind(root));
if(typeof module!=='undefined')module.exports=testConnection;
})(typeof window==='undefined'?globalThis:window);
