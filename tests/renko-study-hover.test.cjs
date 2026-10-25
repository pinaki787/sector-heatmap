const test=require('node:test'),assert=require('node:assert/strict');
const {studyHoverValue,coalescedHover}=require('../renko-supertrend.js');
test('hover uses exact candle gap, including zero and negative values',()=>{
 const points=new Map([[100,-4],[200,0],[300,6]]),latest={time:300,value:6};
 assert.equal(studyHoverValue(points,latest,100).value,-4);
 assert.equal(studyHoverValue(points,latest,200).value,0);
 assert.equal(studyHoverValue(points,latest,200).available,true);
 assert.equal(studyHoverValue(points,latest,200).hovered,true);
});
test('missing candle never substitutes latest and leaving restores latest',()=>{
 const points=new Map([[100,1]]),latest={time:100,value:1};
 assert.equal(studyHoverValue(points,latest,200).available,false);
 assert.equal(studyHoverValue(points,latest,null).value,1);
 assert.equal(studyHoverValue(points,latest,null).hovered,false);
 assert.equal(studyHoverValue(new Map(),null,null).available,false);
});
test('study hover bursts use the shared one-frame scheduler',()=>{
 const frames=[],values=[],update=coalescedHover(p=>values.push(p.time),f=>frames.push(f));
 for(let i=0;i<100;i++)update({time:i});assert.equal(frames.length,1);
 frames[0]();assert.deepEqual(values,[99]);
});
