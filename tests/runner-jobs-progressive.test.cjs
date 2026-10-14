const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readSources}=require('../runner-jobs.js');
test('fast jobs appear before slow source settles; failures retain successful results',async()=>{
 let finishSlow;const seen=[];
 const slow=new Promise(resolve=>finishSlow=resolve);
 const tasks=['fast','slow','failed'].map(url=>({source:{url}}));
 const pending=readSources(tasks,async url=>{if(url==='slow')return slow;if(url==='failed')throw Error('unavailable');return {running:true};},(task,data,error)=>seen.push({url:task.source.url,data,error}));
 await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(seen.map(x=>x.url),['fast','failed']);
 assert.equal(seen[0].data.running,true);assert.match(seen[1].error.message,/unavailable/);
 finishSlow({running:false});await pending;
 assert.deepEqual(seen.map(x=>x.url),['fast','failed','slow']);
});
