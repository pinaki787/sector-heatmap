const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const text=fs.readFileSync('chart-workspace.js','utf8');
const start=text.indexOf('            run(data) {',text.indexOf('const plotValues =')),end=text.indexOf('\n          };',start);
const method=text.slice(start,end);
function render(isRenko,source,data){
 const context={values:[new Map(source)],completedBrickSignalView:()=>true,isRenko,canonicalAi:true,data};
 vm.runInNewContext('indicator={'+method+'};result=indicator.run(data);',context);
 return context.result[0];
}
test('completed-brick Renko rendering returns defined numeric points rather than shadowing the result',()=>{
 const result=render(true,[[1,{value:100,options:{color:'green'}}],[2,{value:101,options:{color:'green'}}]],[{time:1,sourceTime:1000},{time:2,sourceTime:1060}]);
 assert.deepEqual(Array.from(result),[100,101]);
});
test('time views carry the last completed-brick value forward without looking ahead',()=>{
 const result=render(false,[[120,{value:100,options:{color:'green'}}],[240,{value:99,options:{color:'red'}}]],[{time:60},{time:120},{time:180},{time:240},{time:300}]);
 assert.deepEqual(Array.from(result),[undefined,100,100,99,99]);
 assert.deepEqual(Array.from(result.colors),[undefined,'green','green','red','red']);
});
const source=require('../renko-ai-chart-source.js');
const owner='a'.repeat(32),href='https://example.test/?chartContext=renko&aiRenko=1&aiRun=check&chartSource='+owner+'&interval=1&brick=1';
const p=(i,close)=>({symbol:'EXACT',index:i,brick:1,source_time:60+i,available_at:61+i,open:close-1,high:close,low:close-1,close,st:close-2,direction:-1});
const payload=points=>({account:owner,run_id:'check',symbol:'EXACT',frame:1,brick:1,source_basis:'PROVIDER_CONFIRMED_OHLC',ohlc_available:true,rows:[],supertrend_basis:'COMPLETED_RENKO',signal_points:points});
test('owned signal cache accepts appended bricks, deduplicates identical refreshes, and rejects gaps',()=>{
 source.verify(payload([p(1,100)]),href,'EXACT');source.verify(payload([p(1,100),p(2,101)]),href,'EXACT');
 assert.equal(source.signalBars(href,'EXACT').length,2);
 assert.throws(()=>source.verify(payload([p(4,103)]),href,'EXACT'),/gap/);
 assert.equal(source.signalBars(href.replace('a'.repeat(32),'b'.repeat(32)),'EXACT'),undefined);
});

test('preview bricks retain selected geometry after navigation removes runtime URL parameters',()=>{
 const body=text.slice(text.indexOf('  let completedPreviewCache;'),text.indexOf('  function completedBrickSignalView()'));
 const context={rows:[{time:1,close:100},{time:2,close:120}],aiSelectionParams:new URLSearchParams('brick=10'),aiRuntimeParams:new URLSearchParams(''),settings:{interval:'5',size:999},chartSymbol:()=> 'EXACT',renko:(rows,size)=>size===10?[{time:1,open:100,close:110}]:[]};
 vm.runInNewContext(body+';result=completedPreviewSignalBars();',context);
 assert.equal(context.result.length,1);
 assert.equal(context.result[0].close,110);
 context.aiSelectionParams=new URLSearchParams('');
 context.settings.size=10;
 vm.runInNewContext('completedPreviewCache=undefined;result=completedPreviewSignalBars();',context);
 assert.equal(context.result.length,1);
});
