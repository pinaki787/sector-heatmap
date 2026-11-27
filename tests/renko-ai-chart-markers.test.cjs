const test=require('node:test'),assert=require('node:assert/strict');
const {markers}=require('../renko-ai-chart-markers.js');
test('confirmed exact contract fills attach to the final confirmed brick of that source bar',()=>{
 const bars=[{time:1,sourceTime:100},{time:2,sourceTime:100},{time:3,sourceTime:200,provisional:true}];
 const events=[{symbol:'CE-A',timestamp:100,action:'BUY',mode:'PAPER',confirmed:true,price:40.1234},{symbol:'CE-B',timestamp:100,action:'SELL',confirmed:true},{symbol:'CE-A',timestamp:200,action:'SELL',confirmed:true},{symbol:'CE-A',timestamp:100,action:'SELL',confirmed:false}];
 assert.deepEqual(markers(events,bars,'CE-A'),[{time:2,position:'belowBar',color:'#26a69a',shape:'arrowUp',text:''}]);
 assert.deepEqual(markers(events,bars,'UNDERLYING'),[]);
});


test('confirmed fill without a new source-bar brick attaches only to the latest preceding confirmed brick',()=>{
 const {markers}=require('../renko-ai-chart-markers.js');
 const result=markers([{symbol:'EXACT',source_timestamp:180,timestamp:181,confirmed:true,action:'BUY',mode:'PAPER',price:40}],
 [{time:1,sourceTime:60},{time:2,sourceTime:120},{time:3,sourceTime:240},{time:4,sourceTime:150,provisional:true}],'EXACT');
 assert.equal(result.length,1);assert.equal(result[0].time,2);assert.equal(result[0].text,'');
 assert.deepEqual(markers([{symbol:'EXACT',timestamp:1,confirmed:true,action:'BUY',mode:'LIVE'}],[{time:1,sourceTime:60}],'EXACT'),[]);
});

test('underlying and premium fills keep arrows without text in either execution mode',()=>{
 for(const mode of ['PAPER','LIVE'])for(const symbol of ['CE-A','INDEX']){
 const out=markers(['BUY','SELL','OPEN_SHORT','CLOSE_SHORT'].map(action=>({symbol:'CE-A',underlying:'INDEX',confirmed_at:100,action,mode,confirmed:true,price:42.5})),[{time:1,sourceTime:100}],symbol);
 assert.deepEqual(out.map(m=>m.text),['','','','']);
 }
});

test('active entry line uses confirmed contract fill and never plots option premium as underlying price',()=>{
 const {entryLine}=require('../renko-ai-chart-markers.js');
 const p={symbol:'CE',underlying:'INDEX',quantity:1,side:'CE',fill_price:40,entry_timestamp:150};
 const bars=[{time:1,sourceTime:100,close:25000},{time:2,sourceTime:200,close:25100}];
 assert.equal(entryLine(p,bars,'CE').price,40);
 assert.equal(entryLine(p,bars,'INDEX').price,25000);
 assert.equal(entryLine(p,bars,'INDEX').reference,true);
 assert.equal(entryLine(null,bars,'CE'),null);
 assert.equal(entryLine({...p,quantity:0},bars,'CE'),null);
 assert.equal(entryLine(p,bars,'OTHER'),null);
 assert.equal(entryLine({...p,fill_price:null},bars,'CE'),null);
});

test('moving line uses exact fresh open-trade monetary P&L and falls back to directional points',()=>{
 const {currentLine}=require('../renko-ai-chart-markers.js');
 const p={symbol:'CE',underlying:'INDEX',quantity:2,side:'CE',fill_price:40,entry_timestamp:100};
 const bars=[{time:100,close:25000},{time:200,close:25010}];
 const trade={symbol:'CE',status:'OPEN',quantity:2,entry_premium:40,latest_price:42,latest_time:200,unrealized_gross:40,currency:'INR'};
 assert.equal(currentLine(p,bars,'CE',trade,201).title,'INR +40.00 gross');
 assert.equal(currentLine(p,bars,'CE',trade,201).price,42);
 assert.equal(currentLine(p,bars,'INDEX',trade,201).price,25010);
 assert.equal(currentLine(p,bars,'INDEX',{...trade,symbol:'OTHER'},201).title,'+10.00 pts');
 assert.equal(currentLine({...p,side:'PE'},bars,'INDEX',null,201).title,'-10.00 pts');
 assert.equal(currentLine(p,bars,'INDEX',trade,220).title,'+10.00 pts');
 assert.equal(currentLine(null,bars,'INDEX',trade,201),null);
});

test('entry/current lines update existing series and both disappear on close without chart rebuild',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),source=fs.readFileSync('chart-workspace.js','utf8');
 const start=source.indexOf('  function applyAiRuntimeMarkers('),end=source.indexOf('  if(aiRuntimeEmbedded)window.addEventListener',start);
 const helper=require('../renko-ai-chart-markers.js');let created=0,updated=0,removed=0;
 const series={setMarkers(){},createPriceLine(){created++;return {applyOptions(){updated++;}}},removePriceLine(){removed++;}};
 const c={window:{RenkoAiChartMarkers:helper},aiRuntimeEmbedded:true,aiBandCloud:null,aiRuntimeBars:[],aiRuntimeEvents:[],aiActivePosition:{symbol:'CE',quantity:1,side:'CE',fill_price:40},aiActiveTrade:null,aiEntryLine:null,aiEntryLineSeries:null,aiEntryLineKey:null,aiCurrentLine:null,aiCurrentLineSeries:null,chartSymbol:()=> 'CE',series,bars:[{time:100,close:42}]};
 vm.createContext(c);vm.runInContext(source.slice(start,end)+';applyAiRuntimeMarkers(series,bars);applyAiRuntimeMarkers(series,bars);aiActivePosition=null;applyAiRuntimeMarkers(series,bars);',c);
 assert.equal(created,2);assert.equal(updated,1);assert.equal(removed,2);
});

test('Motilal chart mapping transforms display symbols without losing execution ownership or changing audit records',()=>{
 const {mappedChartOwnership}=require('../renko-ai-options.js');
 const p={symbol:'MO:MCX:11',underlying:'MCX:22',quantity:10,fill_price:40,entry_underlying_price:6000,side:'PE'};
 const t={symbol:p.symbol,status:'OPEN',quantity:10,entry_premium:40,latest_price:42,latest_time:200,unrealized_gross:20,currency:'INR'};
 const event={symbol:p.symbol,underlying:p.underlying,action:'BUY',confirmed:true,mode:'LIVE',timestamp:100};
 const original={active_position:p,active_trade:t,events:[event],execution_account:'MOTILAL_OWNER'};
 const mapped=mappedChartOwnership(original,{'MO:MCX:11':'MCX:EXACTPE','MCX:22':'MCX:EXACTFUT'});
 assert.equal(mapped.active_position.symbol,'MCX:EXACTPE');
 assert.equal(mapped.active_position.execution_symbol,p.symbol);assert.equal(mapped.execution_account,'MOTILAL_OWNER');
 assert.equal(mapped.events[0].underlying,'MCX:EXACTFUT');assert.equal(original.events[0].symbol,'MO:MCX:11');
 const {entryLine,currentLine}=require('../renko-ai-chart-markers.js');
 assert.equal(entryLine(mapped.active_position,[{time:200,close:5990}],'MCX:EXACTFUT').price,6000);
 assert.equal(currentLine(mapped.active_position,[{time:200,close:42}],'MCX:EXACTPE',mapped.active_trade,201).title,'INR +20.00 gross');
 assert.equal(entryLine(mapped.active_position,[],'OTHER'),null);
});

test('same-contract P&L cannot use another entry order or an unproven order match',()=>{
 const {currentLine}=require('../renko-ai-chart-markers.js');
 const p={symbol:'CE',quantity:2,side:'CE',fill_price:40,entry_timestamp:100,order_id:'new-entry'};
 const bars=[{time:200,close:42}];
 const t={symbol:'CE',status:'OPEN',quantity:2,entry_premium:40,latest_price:42,latest_time:200,unrealized_gross:40,currency:'INR',entry_order:'old-entry'};
 assert.equal(currentLine(p,bars,'CE',t,201).title,'+2.00 pts');
 assert.equal(currentLine(p,bars,'CE',{...t,entry_order:''},201).title,'+2.00 pts');
 assert.equal(currentLine(p,bars,'CE',{...t,entry_order:'new-entry'},201).title,'INR +40.00 gross');
});

test('PAXG current gross P&L uses recorded contracts and multiplier in both directions',()=>{
 const {currentLine}=require('../renko-ai-chart-markers.js');
 const p={symbol:'PAXGUSD',side:'LONG',quantity:10,fill_price:3566.3,order_id:'confirmed-entry'};
 const bars=[{time:100,close:3568.3}];
 const trade={symbol:'PAXGUSD',status:'OPEN',quantity:10,entry_premium:3566.3,entry_order:'confirmed-entry',latest_time:100,latest_price:3568.3,currency:'USD',unrealized_gross:(3568.3-3566.3)*10*.001};
 assert.equal(currentLine(p,bars,p.symbol,trade,101).title,'USD +0.02 gross');
 assert.equal(currentLine(p,bars,p.symbol,{...trade,latest_price:3564.3,unrealized_gross:-.02},101).title,'USD -0.02 gross');
 assert.equal(currentLine({...p,side:'SHORT'},bars,p.symbol,{...trade,unrealized_gross:-.02},101).title,'USD -0.02 gross');
 assert.equal(currentLine(null,bars,p.symbol,trade,101),null);
 assert.match(currentLine(p,bars,p.symbol,{...trade,entry_order:'unrelated-manual'},101).title,/pts$/);
});
