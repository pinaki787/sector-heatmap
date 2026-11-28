/* Validated historical model reuse. No credentials, account mutation or orders. */
(function(root){'use strict';
const VERSION=3,TTL=7*86400000,MAX=64,fields=['tables','labels','ranges','sessions','shadowLabels','archive','previousDay','neighbors','previousShadow','targets','liquidity','pins','labelPins','version','price','computations'];
async function digest(value){
 const bytes=new TextEncoder().encode(JSON.stringify(value));
 const result=await root.crypto.subtle.digest('SHA-256',bytes);
 return Array.from(new Uint8Array(result),n=>n.toString(16).padStart(2,'0')).join('');
}
function sourceUsesVolume(source){
 const code=String(source).replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,'');
 return /\bvolume\b|\bta\.(?:vwap|vwma|mfi|obv|accdist|pvi|nvi|pvt|iii|wvad)\b/.test(code);
}
function candleInput(rows,includeVolume=true){
 return rows.map(r=>[r.openTime,r.closeTime,r.open,r.high,r.low,r.close,includeVolume?(r.volume??null):null,r.provisional===true,r.historicalPrefixThrough??null]);
}
function candleDigest(rows,includeVolume=true){return digest(candleInput(rows,includeVolume));}
function abortable(promise,signal){
 if(!signal)return promise;signal.throwIfAborted();
 return new Promise((resolve,reject)=>{const abort=()=>reject(signal.reason);signal.addEventListener('abort',abort,{once:true});Promise.resolve(promise).then(v=>{signal.removeEventListener('abort',abort);resolve(v)},e=>{signal.removeEventListener('abort',abort);reject(e)});});
}
function snapshot(model){
 const out={};for(const field of fields)out[field]=model[field] instanceof Map?[...model[field]]:model[field];
 return JSON.parse(JSON.stringify(out));
}
function restore(data,asOf){
 if(!data||!Array.isArray(data.tables)||!data.tables.length||!Array.isArray(data.archive)||data.archive.some(x=>!Number.isFinite(x.closed)||x.closed>asOf)||data.previousShadow?.closed>asOf)return null;
 if(!Array.isArray(data.pins)||!Array.isArray(data.labelPins))return null;
 const model=new root.SectorPulseAiV1Display.Model();
 for(const field of fields)if(Object.hasOwn(data,field))model[field]=['pins','labelPins'].includes(field)?new Map(data[field]||[]):data[field];
 return model;
}
function indexedStore(){
 let opening,lastError=null;
 const database=()=>opening??=(new Promise(resolve=>{
  if(!root.indexedDB){resolve(null);return;}
  let ended=false;const timer=setTimeout(()=>{ended=true;lastError='cache-open-timeout';resolve(null)},2000);
  const request=root.indexedDB.open('sector-pulse-historical-reference-models-v3');
  request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('models'))request.result.createObjectStore('models',{keyPath:'key'});};
  request.onsuccess=()=>{clearTimeout(timer);request.result.onversionchange=()=>request.result.close();if(ended)request.result.close();else resolve(request.result)};
  request.onerror=()=>{clearTimeout(timer);lastError=request.error?.name||'cache-open-error';ended=true;resolve(null)};
  request.onblocked=()=>{clearTimeout(timer);lastError='cache-open-blocked';ended=true;resolve(null)};
 }));
 async function transaction(mode,run){
  const db=await database();if(!db)return null;
  return new Promise(resolve=>{let value=null;const tx=db.transaction('models',mode);const store=tx.objectStore('models');run(store,v=>value=v);tx.oncomplete=()=>resolve(value);tx.onerror=tx.onabort=()=>{lastError=tx.error?.name||'cache-transaction-aborted';resolve(null)};});
 }
 return {
  get diagnostics(){return {lastError};},
  get:key=>transaction('readonly',(s,done)=>{const r=s.get(key);r.onsuccess=()=>done(r.result||null)}),
  put:record=>transaction('readwrite',(s,done)=>{s.put(record);const r=s.getAll();r.onsuccess=()=>{const rows=r.result.sort((a,b)=>a.savedAt-b.savedAt),now=Date.now();let remaining=rows.length;for(const row of rows)if(now-row.savedAt>TTL||remaining>MAX){s.delete(row.key);remaining--;}done(true)}}),
  delete:key=>transaction('readwrite',s=>s.delete(key))
 };
}
let sharedStore;
class PersistentReferenceCache{
 constructor({namespace,source,store,hash=digest,now=()=>Date.now()}){
  this.namespace=namespace;this.source=source;this.includeVolume=sourceUsesVolume(source);this.store=store||(sharedStore??=indexedStore());this.hash=hash;this.now=now;
 }
 async key(session,revision){try{return await this.hash([VERSION,this.namespace,this.source,session.open,session.asOf,revision]);}catch(error){error.code='CACHE_UNAVAILABLE';throw error;}}
 async read(session,revision,loadInput,signal,onProgress){
  const key=await this.key(session,revision),record=await abortable(this.store.get(key),signal);
  if(!record||record.schema!==VERSION||record.asOf!==session.asOf||this.now()-record.savedAt>TTL||!Array.isArray(record.dependencies)||!record.dependencies.length){this.lastRead={reason:!record?'missing':'invalid-or-expired',key:key.slice(0,12)};return null;}
  const started=root.performance?.now?.()||0;
  let cursor=0,changed=null,failed=null;
  const timings=[];
  // Independent intervals validate concurrently, with a small fixed bound.
  // The selected account/source and every dependency fingerprint remain mandatory.
  const validate=async()=>{
   while(cursor<record.dependencies.length&&!changed&&!failed){
    const dep=record.dependencies[cursor++];signal?.throwIfAborted();
    onProgress?.('Validating cached '+dep.request.interval+' candles…');
    try{
     const begin=root.performance?.now?.()||0;
     const rows=await abortable(loadInput(dep.request),signal),loaded=root.performance?.now?.()||0;
     const actualHash=await this.hash(candleInput(rows,this.includeVolume));
     timings.push({interval:dep.request.interval,loadMs:loaded-begin,hashMs:(root.performance?.now?.()||0)-loaded});
     if(actualHash!==dep.hash)changed={reason:'dependency-changed',interval:dep.request.interval,key:key.slice(0,12),expected:dep.sample,actual:{count:rows.length,first:candleInput(rows.slice(0,1))[0],last:candleInput(rows.slice(-1))[0]}};
    }catch(error){failed=error;}
   }
  };
  await Promise.all(Array.from({length:Math.min(3,record.dependencies.length)},validate));
  if(failed)throw failed;
  if(changed){this.lastRead=changed;await this.store.delete(key);return null;}

  const model=restore(record.model,session.asOf);if(!model){this.lastRead={reason:'invalid-model',key:key.slice(0,12)};await this.store.delete(key);return null;}
  this.lastRead={reason:'validated-hit',key:key.slice(0,12)};
  return {model,validationMs:(root.performance?.now?.()||0)-started,dependencies:record.dependencies.length,timings};
 }
 async write(session,revision,model,dependencies){
  if(!dependencies.length||dependencies.length>64)return false;
  const key=await this.key(session,revision);
  return this.store.put({key,schema:VERSION,asOf:session.asOf,savedAt:this.now(),model:snapshot(model),dependencies});
 }
}
class SnapshotReplayEngine{
 constructor({start,result,max=64}){this.start=start;this.result=result;this.max=max;this.completed=new Map();}
 begin(job){
  this.job=job;
  this.pending=new Promise((resolve,reject)=>{this.resolve=resolve;this.reject=reject;});
  // Cancellation of one viewport must not create an unhandled shared rejection.
  void this.pending.catch(()=>{});
 }
 dispose(){this.control?.stop?.();}
 finish(plots){
  const model=this.result(this.job,plots);
  this.completed.set(this.job.key,model);
  while(this.completed.size>this.max)this.completed.delete(this.completed.keys().next().value);
  this.resolve(model);
 }
 async evaluate(job,signal,onProgress){
  if(this.completed.has(job.key))return this.completed.get(job.key);
  this.progress=onProgress;onProgress?.(this.ready?'Waiting for the current reference calculation…':'Initializing the shared reference engine…');
  if(!this.ready){
   this.begin(job);this.replay={...job.replay,controlled:true,onControl:c=>this.control=c};
   this.ready=Promise.resolve(this.start(this.replay,plots=>{try{this.finish(plots)}catch(e){this.reject(e)}},message=>this.progress?.(message)))
    .then(data=>this.finish(data.plots)).catch(error=>{this.failed=error;this.reject(error);throw error;});
   void this.ready.catch(()=>{});
  }
  await abortable(this.ready,signal);
  await abortable(this.pending,signal);
  if(this.failed)throw this.failed;
  if(this.completed.has(job.key))return this.completed.get(job.key);
  signal?.throwIfAborted();
  this.begin(job);Object.assign(this.replay,job.replay);this.replay.controlled=true;
  this.control.refresh(true);
  return abortable(this.pending,signal);
 }
}
function compactReferenceResult(message){
 if(!message||typeof message!=='object'||!message.plots)return message;
 return {...message,plots:Object.fromEntries(Object.entries(message.plots).map(([key,plot])=>[key,plot&&Array.isArray(plot.data)?{...plot,data:plot.data.slice(-1)}:plot]))};
}
function referenceWorkerBootstrap(url){
 return 'const __spCompactReference='+compactReferenceResult.toString()+';const __spPostMessageRaw=self.postMessage.bind(self);self.postMessage=(message,...rest)=>__spPostMessageRaw(__spCompactReference(message),...rest);importScripts('+JSON.stringify(url)+');';
}

root.SectorPulseReferenceCache={PersistentReferenceCache,SnapshotReplayEngine,digest,candleInput,candleDigest,sourceUsesVolume,compactReferenceResult,referenceWorkerBootstrap,abortable,snapshot,restore,indexedStore};
})(typeof window==='undefined'?globalThis:window);
