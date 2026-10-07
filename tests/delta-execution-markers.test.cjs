const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={};vm.createContext(context);vm.runInContext(fs.readFileSync('delta-india.js','utf8').split('/* Independent Delta India')[0],context);const build=context.DeltaExecutionMarkers;
test('Paper markers use durable exact ledger fills including partial exits and isolate workflow/instrument',()=>{
 const state={paper:{trades:[{lifecycle_id:'p1',mode:'PAPER',symbol:'BTCUSD',side:'LONG',contracts:10,entry_time:1000,entry_price:100,exit_fills:[{time:1010,price:102,contracts:3},{time:1020,price:99,contracts:7}]}]}};
 const markers=build({state,workflow:'PAPER',symbol:'BTCUSD'});assert.equal(markers.length,3);assert.equal(markers[1].contracts,3);assert.equal(markers[2].time,1020);assert.ok(markers.every(m=>m.lifecycle_id==='p1'));
 assert.equal(build({state,workflow:'LIVE',symbol:'BTCUSD'}).length,0);assert.equal(build({state,workflow:'PAPER',symbol:'ETHUSD'}).length,0);
});
test('Live markers require actual matching broker fills; never use signal, rejected or unfilled order snapshots',()=>{
 const order=(id,side,reduce=false)=>({order_id:id,symbol:'BTCUSD',request_id:'r'+id,execution_reason:reduce?'EXIT':'ENTRY',request:{product_id:1,side,reduce_only:reduce}});
 const state={orders:[order(1,'buy'),order(2,'sell',true),order(3,'buy')]};const fill=(id,order_id,side,size)=>({id,order_id,side,size,price:100,created_at:new Date((1000+id)*1000).toISOString(),product_id:1,symbol:'BTCUSD'});
 const account={fills:[fill(1,1,'buy',10),fill(2,2,'sell',4),fill(3,999,'buy',1),{...fill(4,1,'buy',1),product_id:2}]};
 const markers=build({state,account,workflow:'LIVE',symbol:'BTCUSD'});assert.equal(markers.length,2);assert.equal(markers[1].kind,'EXIT');assert.equal(markers[1].contracts,4);assert.equal(markers[1].lifecycle_id,'r1');assert.equal(markers[1].time,1002);
});

test('option feedback retains the recorded traded strike and call/put on entry and exit',()=>{for(const prefix of ['C','P']){const symbol=prefix+'-BTC-86400-021026',state={paper:{trades:[{lifecycle_id:'actual-option',mode:'PAPER',symbol,side:'LONG',contracts:10,entry_time:1000,entry_price:214,exit_fills:[{time:1010,price:222,contracts:10}]}]}};const markers=build({state,workflow:'PAPER',symbol});assert.equal(markers.length,2);for(const marker of markers){assert.equal(marker.contract_label,(prefix==='C'?'CALL':'PUT')+' · strike 86400 · '+symbol);assert.equal(marker.lifecycle_id,'actual-option');}}const state={paper:{trades:[{lifecycle_id:'future',mode:'PAPER',symbol:'BTCUSD',side:'LONG',contracts:10,entry_time:1000,entry_price:86000}]}};assert.equal(build({state,workflow:'PAPER',symbol:'BTCUSD'})[0].contract_label,'Futures · BTCUSD');});
