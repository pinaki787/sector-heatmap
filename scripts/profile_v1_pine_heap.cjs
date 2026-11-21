/* Isolated archive replay allocation sample. Never loads broker credentials. */
const inspector=require('node:inspector'),fs=require('node:fs');
const session=new inspector.Session();session.connect();
const output=process.argv[2],worker=process.argv[3],workspace=process.argv[4];
if(!output||!worker||!workspace)throw Error('output worker workspace required');
const post=(name,args={})=>new Promise((resolve,reject)=>session.post(name,args,(error,result)=>error?reject(error):resolve(result)));
(async()=>{
 await post('HeapProfiler.startSampling',{samplingInterval:131072});
 globalThis.PineReplayAllocationCheckpoint=requests=>{
  if(requests.length<Number(process.env.PROFILE_REQUESTS||12))return;
  session.post('HeapProfiler.stopSampling',{},(error,result)=>{
   if(error){console.error(error);process.exit(1)}
   fs.writeFileSync(output,JSON.stringify(result.profile));
   console.log('Saved allocation sample at reference request '+requests.length);process.exit(0);
  });
 };
 setTimeout(async()=>{
  try{
   const {profile}=await post('HeapProfiler.stopSampling');
   fs.writeFileSync(output,JSON.stringify(profile));
   console.log('Saved isolated allocation sample');process.exit(0);
  }catch(error){console.error(error.message);process.exit(1)}
 },25000);
 process.argv=[process.argv[0],'scripts/verify_v1_open_renko_references.cjs',worker,workspace,output+'.replay.json'];
 require('./verify_v1_open_renko_references.cjs');
})().catch(error=>{console.error(error);process.exit(1)});
