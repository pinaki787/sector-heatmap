const test=require('node:test'),assert=require('node:assert/strict');
const {dhanChartSymbol,createDhanChartResolver}=require('../renko-ai-options.js');
const rows=[{id:'IDX_I:13',symbol:'NIFTY',exchange:'NSE',segment:'IDX_I'},{id:'NSE_EQ:9436',symbol:'AXISCADES',exchange:'NSE',segment:'NSE_EQ'}];
test('Nifty alias resolves through selected Dhan catalog rather than saved stock',()=>{
 assert.equal(dhanChartSymbol('NSE:NIFTY',rows,'NSE_INDEX'),'IDX_I:13');
 assert.equal(dhanChartSymbol('NSE:NIFTY50-INDEX',rows,'NSE_INDEX'),'IDX_I:13');
 assert.equal(dhanChartSymbol('NSE:AXISCADES',rows,'NSE_EQUITY'),'NSE_EQ:9436');
 assert.equal(dhanChartSymbol('MCX_COMM:123',[]),'MCX_COMM:123');
 assert.throws(()=>dhanChartSymbol('BSE:NIFTY',rows),/unavailable/);
 assert.throws(()=>dhanChartSymbol('NSE:NIFTY',[...rows,{...rows[0],id:'IDX_I:99'}]),/ambiguous/);
});
test('per-account lookups deduplicate and successful selections do not poll',async()=>{
 let calls=[];let now=0;
 const resolve=createDhanChartResolver(async(account)=>{calls.push(account);return rows;},()=>now);
 const first=resolve('A','NSE:NIFTY','NSE_INDEX');
 assert.equal(first,resolve('A','NSE:NIFTY','NSE_INDEX'));
 await first.promise;assert.equal(first.symbol,'IDX_I:13');
 now=120000;assert.equal(resolve('A','NSE:NIFTY','NSE_INDEX'),first);assert.equal(calls.length,1);
 await resolve('B','NSE:NIFTY','NSE_INDEX').promise;assert.deepEqual(calls,['A','B']);
 assert.equal(resolve('A','NSE_EQ:9436').symbol,'NSE_EQ:9436');assert.equal(calls.length,2);
});
test('failed lookups never provide a fallback chart symbol or request storm',async()=>{
 let calls=0;const resolve=createDhanChartResolver(async()=>{calls++;throw Error('Unavailable');},()=>100);
 const row=resolve('A','NSE:NIFTY','NSE_INDEX');await row.promise;
 assert.equal(row.symbol,undefined);assert.equal(row.error,'Unavailable');
 for(let i=0;i<10;i++)assert.equal(resolve('A','NSE:NIFTY','NSE_INDEX'),row);
 assert.equal(calls,1);
});
test('mapped runtime request retains execution source and exact displayed identity',()=>{
 const source=require('../renko-ai-chart-source.js'),href='https://test/?chartContext=renko&aiRenko=1&aiRun=run1&chartSource='+'a'.repeat(32)+'&symbol=IDX_I%3A13&aiSourceSymbol=NSE%3ANIFTY&interval=1&brick=10';
 const result=source.request('/api/chart-workspace/history?interval=1',href,'IDX_I:13');
 const q=new URL(result.path,'https://test').searchParams;
 assert.equal(q.get('symbol'),'NSE:NIFTY');assert.equal(q.get('display_symbol'),'IDX_I:13');
});
