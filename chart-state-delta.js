/* Connection-scoped, lossless transport. Reconstructs the existing state API. */
(function(root){
'use strict';
function member(value,key){
 if(value===null||typeof value!=='object'||!Object.hasOwn(value,key))throw Error('Missing state path');
 return value[key];
}
function replaceAt(value,path,change){
 if(!path.length)return change(value);
 const [key,...rest]=path;
 if(value===null||typeof value!=='object')throw Error('Invalid state path');
 const copy=Array.isArray(value)?value.slice():{...value};
 const next=replaceAt(member(value,key),rest,change);
 Object.defineProperty(copy,key,{value:next,writable:true,enumerable:true,configurable:true});
 return copy;
}
function createDecoder(){
 let state,sequence=0;
 return payload=>{
  if(!payload||payload.v!==1||!Number.isSafeInteger(payload.seq)||payload.seq<1)throw Error('Invalid state revision');
  if(Object.hasOwn(payload,'full')){
   if(payload.seq!==1&&payload.seq!==sequence+1)throw Error('State revision gap');
   state=payload.full;sequence=payload.seq;return state;
  }
  if(state===undefined||payload.base!==sequence||payload.seq!==sequence+1||!Array.isArray(payload.ops))throw Error('State revision gap');
  let next=state;
  for(const op of payload.ops){
   if(!Array.isArray(op.path)||op.path.some(k=>typeof k!=='string'&&!Number.isSafeInteger(k)))throw Error('Invalid state path');
   if(op.op==='set'){
    if(!op.path.length)next=op.value;
    else{
     const path=op.path.slice(0,-1),key=op.path.at(-1);
     next=replaceAt(next,path,value=>{
      if(value===null||typeof value!=='object')throw Error('Invalid state parent');
      const copy=Array.isArray(value)?value.slice():{...value};
      Object.defineProperty(copy,key,{value:op.value,writable:true,enumerable:true,configurable:true});
      return copy;
     });
    }
   }else if(op.op==='remove'){
    if(!op.path.length)throw Error('Cannot remove root state');
    const path=op.path.slice(0,-1),key=op.path.at(-1);
    next=replaceAt(next,path,value=>{
     if(Array.isArray(value)||!Object.hasOwn(value,key))throw Error('Invalid removal');
     const copy={...value};delete copy[key];return copy;
    });
   }else if(op.op==='splice'){
    next=replaceAt(next,op.path,value=>{
     if(!Array.isArray(value)||!Number.isSafeInteger(op.start)||!Number.isSafeInteger(op.delete)
        ||op.start<0||op.start>value.length||op.delete<0||op.start+op.delete>value.length||!Array.isArray(op.items))throw Error('Invalid state splice');
     return [...value.slice(0,op.start),...op.items,...value.slice(op.start+op.delete)];
    });
   }else throw Error('Unknown state operation');
  }
  state=next;sequence=payload.seq;return state;
 };
}
function attach(stream){
 const decode=createDecoder();
 stream.addEventListener('state-delta',event=>{
  try{const state=decode(JSON.parse(event.data)),message=new MessageEvent('state',{data:''});Object.defineProperty(message,'decodedState',{value:state});stream.dispatchEvent(message);}
  catch{stream.close();stream.dispatchEvent(new Event('error'));}
 });
 return stream;
}
const snapshots=new Map();
function fetchState(fetcher,url,options={}){
 const target=new URL(url,typeof location==='object'?location.href:'http://localhost/');
 if((options.method||'GET').toUpperCase()!=='GET'||!(/\/api\/renko-instances$/.test(target.pathname)||/^\/api\/renko-(dhan|motilal)\/[a-f0-9]{32}\/instances$/.test(target.pathname)))return fetcher(url,options);
 const key=target.href;
 let entry=snapshots.get(key);
 if(!entry){entry={id:crypto.randomUUID(),decode:createDecoder(),queue:Promise.resolve()};snapshots.set(key,entry);}
 const execute=async(retry=true)=>{
  target.searchParams.set('compact_state','1');target.searchParams.set('state_client',entry.id);
  const response=await fetcher(target.href,options);
  const value=await response.json();
  let decoded=value;
  if(response.ok&&response.headers.get('X-State-Delta')==='1'){
   try{decoded=entry.decode(value);}
   catch(error){
    entry.id=crypto.randomUUID();entry.decode=createDecoder();
    if(retry)return execute(false);
    throw error;
   }
  }
  return {ok:response.ok,status:response.status,headers:response.headers,json:async()=>decoded};
 };
 const pending=entry.queue.catch(()=>{}).then(()=>execute());
 entry.queue=pending;
 return pending;
}
const api={createDecoder,attach,fetchState};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
else root.SectorPulseStateDelta=api;
})(globalThis);
