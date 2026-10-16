const test=require('node:test');
const assert=require('node:assert/strict');
const {stopAllRenko}=require('../renko-supertrend.js');
test('kill stops producer before both brokers, keeps closing evidence and continues after failure',async()=>{
 const calls=[];
 const fetcher=async(url)=>{calls.push(url);if(url==='/api/renko-instances')return {ok:true,json:async()=>({instances:[{broker:'FYERS',instance_key:'default',running:true,instrument:'Nifty'},{broker:'FYERS',instance_key:'held',position:{},instrument:'Crude'},{broker:'DELTA_INDIA',instance_key:'btc',pending:{},instrument:'BTC'},{broker:'FYERS',instance_key:'flat',running:false}]})};if(url.includes('held'))return {ok:false,json:async()=>({error:'Broker unavailable'})};return {ok:true,json:async()=>url.includes('btc')?{running:true,pending:{}}:{running:false}};};
 const rows=await stopAllRenko(fetcher);
 assert.equal(calls[0],'/api/telegram/paper-stop');
 assert.equal(rows.length,3);assert.equal(rows[0].status,'STOPPED');assert.equal(rows[1].status,'FAILED');assert.match(rows[2].status,/PENDING/);
 assert.ok(calls.includes('/api/renko-delta/stop?instance=btc'));assert.ok(!calls.some(v=>v.includes('flat')||v.includes('/start')));
});
test('producer stop failure remains visible even when runners are flat',async()=>{
 const rows=await stopAllRenko(async(url)=>({ok:url!='/api/telegram/paper-stop',json:async()=>url==='/api/renko-instances'?{instances:[]}:{error:'Unavailable'}}));
 assert.equal(rows[0].status,'FAILED');assert.equal(rows[0].instrument,'Telegram Paper entries');
});
test('stalled stop returns an unconfirmed failure and continues to other runners',async()=>{
 const rows=await stopAllRenko(async(url,options)=>{
  if(url==='/api/renko-instances')return {ok:true,json:async()=>({instances:[{broker:'FYERS',instance_key:'hung',running:true,instrument:'Hung'},{broker:'FYERS',instance_key:'other',running:true,instrument:'Other'}]})};
  if(url.includes('hung'))return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted'))));
  return {ok:true,json:async()=>({running:false})};
 },10);
 assert.equal(rows[0].status,'FAILED');assert.match(rows[0].error,/not confirmed/);assert.equal(rows[1].status,'STOPPED');
});
