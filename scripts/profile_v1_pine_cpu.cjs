/* Isolated archive replay CPU sample; no broker credentials or network. */
const inspector=require('node:inspector'),fs=require('node:fs');
const session=new inspector.Session();session.connect();
const [output,worker,workspace]=process.argv.slice(2);
if(!output||!worker||!workspace)throw Error('output worker workspace required');
const post=(name,args={})=>new Promise((resolve,reject)=>session.post(name,args,(error,result)=>error?reject(error):resolve(result)));
(async()=>{
 await post('Profiler.enable');await post('Profiler.setSamplingInterval',{interval:2000});await post('Profiler.start');
 globalThis.PineReplayAllocationCheckpoint=requests=>{
  if(requests.length<Number(process.env.PROFILE_REQUESTS||25))return;
  session.post('Profiler.stop',{},(error,result)=>{
   if(error){console.error(error);process.exit(1)}
   fs.writeFileSync(output,JSON.stringify(result.profile));
   console.log('Saved CPU sample at reference request '+requests.length);process.exit(0);
  });
 };
 process.argv=[process.argv[0],'scripts/verify_v1_open_renko_references.cjs',worker,workspace,output+'.replay.json'];
 require('./verify_v1_open_renko_references.cjs');
})().catch(error=>{console.error(error);process.exit(1)});
