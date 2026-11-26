/* Exact append-only Close Renko cache for an immutable owned runtime source. */
(function(root){'use strict';
class OwnedRenkoCache{
 constructor(renko){this.renko=renko;this.reset();}
 reset(){this.scope=null;this.size=null;this.count=0;this.first=null;this.last=null;this.bricks=[];}
 build(source,size,scope){
  if(!Array.isArray(source)||!Number.isFinite(size)||size<=0)throw Error('Valid owned source and brick required.');
  const append=this.scope===scope&&this.size===size&&source.length>=this.count&&source[0]===this.first&&source[this.count-1]===this.last&&this.bricks.length>0;
  if(!append){
   this.bricks=this.renko(source,size,undefined,'close',false);
  }else if(source.length>this.count){
   const added=this.renko(source.slice(this.count),size,this.bricks.at(-1),'close',false),offset=this.bricks.length;
   this.bricks=this.bricks.concat(added.map((brick,index)=>({...brick,time:offset+index+1})));
  }
  this.scope=scope;this.size=size;this.count=source.length;this.first=source[0];this.last=source.at(-1);
  // The chart renderer owns its returned array; it cannot mutate the cache.
  return this.bricks.slice();
 }
}
root.RenkoAiIncremental={OwnedRenkoCache};
if(typeof module!=='undefined')module.exports={OwnedRenkoCache};
})(typeof window==='undefined'?globalThis:window);
