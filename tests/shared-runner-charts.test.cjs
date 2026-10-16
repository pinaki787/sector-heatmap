const {test}=require('node:test'),assert=require('node:assert/strict');
const {sharedRunnerCharts}=require('../renko-supertrend.js');
test('fresh device sees active and pending account runners without local choices',()=>{
 const rows=[{broker:'FYERS',instrument:'NIFTY',instance_key:'a',running:true},{broker:'FYERS',instrument:'GOLD',instance_key:'b',pending:{}},{broker:'DHAN',instrument:'NIFTY',instance_key:'c',running:true},{broker:'FYERS',instrument:'OLD',instance_key:'d'}];
 assert.deepEqual(sharedRunnerCharts(rows,'FYERS',[]).map(v=>v.instance_key),['a','b']);
});
test('active default cannot be hidden by stopped duplicate; saved selection retained',()=>{
 const rows=[{broker:'FYERS',instrument:'NIFTY',instance_key:'default',running:true},{broker:'FYERS',instrument:'NIFTY',instance_key:'saved'},{broker:'FYERS',instrument:'GOLD',instance_key:'gold'}];
 assert.deepEqual(sharedRunnerCharts(rows,'FYERS',['GOLD']).map(v=>v.instance_key),['default','gold']);
});
