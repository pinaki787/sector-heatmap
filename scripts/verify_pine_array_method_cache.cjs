const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [baseline,candidate]=process.argv.slice(2);
function load(path){
 const context=vm.createContext({console,setTimeout,clearTimeout,structuredClone});context.self=context;
 let text=fs.readFileSync(path,'utf8');
 const marker='}function xd(t)';
 assert.equal(text.split(marker).length,2);
 text=text.replace(marker,'}self.__ArrayClass=G;self.__ArrayType=W;function xd(t)');
 vm.runInContext(text,context);
 return context;
}
function exercise(c){
 const ctx={precision:x=>Math.round(x*100)/100},a=new c.__ArrayClass([3,1,2],c.__ArrayType.float,ctx),b=new c.__ArrayClass([8,9],c.__ArrayType.float,ctx);
 const result={sum:a.sum(),avg:a.avg(),min:a.min(),max:a.max(),median:a.median(),negative:a.get(-1),initial:[...a]};
 a.push(4);a.set(0,6);result.after=[...a];result.other=[...b];result.popped=a.pop();result.shifted=a.shift();result.copy=[...a.copy()];
 try{a.get(100)}catch(e){result.bounds=e.message}
 const methods=Object.keys(a).filter(k=>k.startsWith('_')).sort();result.ownMethodNames=methods;
 return JSON.parse(JSON.stringify(result));
}
const old=load(baseline),next=load(candidate);
assert.deepEqual(exercise(next),exercise(old),'numeric, mutation, copy, errors and own fields retain baseline behavior');
const contextA={precision:x=>x},contextB={precision:x=>x*2};
const a=new next.__ArrayClass([1,2],next.__ArrayType.float,contextA),b=new next.__ArrayClass([10,20],next.__ArrayType.float,contextA),c=new next.__ArrayClass([1,2],next.__ArrayType.float,contextB);
assert.equal(a._avg,b._avg);assert.notEqual(a._avg,c._avg);assert.equal(a.avg(),1.5);assert.equal(c.avg(),3);
contextA.precision=x=>x+1;assert.equal(a.avg(),2.5);assert.equal(b.avg(),16);
a.push(3);assert.deepEqual([...b],[10,20]);
const arrays=Array.from({length:1000},()=>new next.__ArrayClass([],next.__ArrayType.float,contextA));
assert.equal(new Set(arrays.map(a=>a._get)).size,1);
console.log(JSON.stringify({status:'PASS',semantic_comparison:true,contexts_isolated:true,context_precision_updates_observed:true,array_mutations_isolated:true,arrays:1000,unique_get_closures:1}));
