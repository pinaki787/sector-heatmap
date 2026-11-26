const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {createStrategyVisit}=require('../renko-ai-options.js');
test('every new visit defaults to actual AI mode despite any older generic selection',()=>{
 const visit=createStrategyVisit();
 assert.equal(visit.enter(),'AI_RENKO_OPTIONS');
 for(const alternative of ['SUPERTREND','SIMPLE_BRICK']){
  visit.choose(alternative);assert.equal(visit.enter(),alternative);
  visit.leave();assert.equal(visit.enter(),'AI_RENKO_OPTIONS');
 }
});
test('deliberate alternatives survive hydration and switches during the current visit',()=>{
 const visit=createStrategyVisit();visit.enter();visit.choose('SUPERTREND');
 assert.equal(visit.enter(),'SUPERTREND');assert.equal(visit.selected(),'SUPERTREND');
 assert.equal(visit.choose('unsupported'),'SUPERTREND');
 visit.leave();visit.choose('SIMPLE_BRICK');assert.equal(visit.enter(),'AI_RENKO_OPTIONS');
});
test('entry logic ignores stored scalar modes and never submits or alters a runner',()=>{
 const source=fs.readFileSync('renko-ai-options.js','utf8');
 const start=source.indexOf(' const strategyVisit=createStrategyVisit();'),end=source.indexOf(" root.addEventListener('renko-ai-context-ready',restoreAiView);",start);
 const block=source.slice(start,end);
 assert.match(block,/attributeFilter:\['class','hidden'\]/);
 assert.match(block,/mode.value=intended/);
 assert.doesNotMatch(block,/localStorage|fetch\(|POST|\.start\(|\.stop\(/);
 assert.match(source,/if\(!applyingViewDefault\)strategyVisit.choose\(mode.value\)/);
});
test('stopped historical manual failure is not shown as a current retained order',()=>{
 const {manualRequestLabel}=require('../renko-ai-options.js');
 const receipt={phase:'FAILED_OR_PENDING',error:'Retained order'};
 assert.match(manualRequestLabel({running:false,ownership:{pending:null,position:null},manual_entry:receipt}),/^Previous run/);
 assert.match(manualRequestLabel({running:false,ownership:{pending:{id:'uncertain'}},manual_entry:receipt}),/^FAILED_OR_PENDING/);
 assert.match(manualRequestLabel({running:true,ownership:{},manual_entry:receipt}),/^FAILED_OR_PENDING/);
});
