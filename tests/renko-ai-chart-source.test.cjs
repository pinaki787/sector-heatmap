const test=require('node:test'),assert=require('node:assert/strict');
const {context,request,verify}=require('../renko-ai-chart-source.js');
const href='https://example.test/?chartContext=renko&aiRenko=1&aiRun=verification-seed&chartSource='+('a'.repeat(32))+'&interval=1&brick=2';
const payload={account:'a'.repeat(32),run_id:'verification-seed',symbol:'EXACT',frame:1,brick:2,source_basis:'PROVIDER_CONFIRMED_CLOSE_ONLY',ohlc_available:false,rows:[[120,null,null,null,4,null]]};
test('standalone and draft charts retain ordinary broker requests',()=>{
 assert.equal(context('https://example.test/?chartContext=renko&aiRenko=1'),null);
 assert.equal(request('/api/chart-workspace/history?interval=1','https://example.test/','EXACT'),null);
});
test('owned run uses exact captured history and excludes independently reconstructed live candles',()=>{
 assert.equal(request('/api/chart-workspace/history?interval=1&after=60',href,'EXACT').path,'/api/renko-supertrend/ai-options/chart-source?run_id=verification-seed&symbol=EXACT&frame=1&after=60');
 assert.deepEqual(request('/api/chart-workspace/live?interval=1',href,'EXACT').frame.rows,[]);
 assert.throws(()=>request('/api/chart-workspace/history?interval=5',href,'EXACT'),/retain/);
});
test('runtime chart rejects a different account, contract, frame, brick or fabricated OHLC',()=>{
 assert.equal(verify(payload,href,'EXACT'),payload);
 for(const changed of [{account:'b'.repeat(32)},{symbol:'OTHER'},{frame:5},{brick:3},{rows:[[120,4,4,4,4,null]]}])assert.throws(()=>verify({...payload,...changed},href,'EXACT'));
});


test('consumed link retains only its original exact run/account frozen source inputs',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 const browser={location:{href},URL,module:{exports:{}}};browser.globalThis=browser;
 vm.runInNewContext(fs.readFileSync('renko-ai-chart-source.js','utf8'),browser);
 const shortened='https://example.test/?chartContext=renko&aiRun=verification-seed&chartSource='+('a'.repeat(32));
 assert.equal(browser.module.exports.context(shortened).brick,2);
 assert.equal(browser.module.exports.context(shortened).frame,1);
 assert.equal(browser.module.exports.context(shortened.replace('verification-seed','other-run')),null);
});


test('runtime link retains frozen source parameters through chart address cleanup',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 const source=fs.readFileSync('chart-workspace.js','utf8'),start=source.indexOf('      const runtimeSourceLink='),end=source.indexOf('url.searchParams.delete(param);',start)+'url.searchParams.delete(param);'.length;
 const code=source.slice(start,end);
 const url=new URL(href+'&symbol=EXACT&type=Renko&chartInstance=fixture');
 vm.runInNewContext(code,{url,embeddedScope:'owned',sharedChartParameters:['aiRenko','brick','interval','symbol','type','chartContext','chartInstance']});
 assert.equal(url.searchParams.get('brick'),'2');assert.equal(url.searchParams.get('interval'),'1');assert.equal(url.searchParams.get('aiRenko'),'1');
});
