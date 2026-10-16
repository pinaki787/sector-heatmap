const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('motilal-oswal.js','utf8');
async function mount({authRequired=true,ok=false,previous=0,search='',permitted=true,saved=false}={}){
 const elements=new Map(),calls=[],redirects=[],storage=new Map();if(previous)storage.set('motilal-login-recovery:/broker-workspace/'+'a'.repeat(32),String(previous));
 const element=()=>({textContent:'',append(){},hidden:true});
 const scope={URLSearchParams,Date,JSON,Error,Number,sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},history:{replaceState(){}},location:{pathname:'/broker-workspace/'+'a'.repeat(32)+'/',search,assign:url=>redirects.push(url)},document:{getElementById:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element},fetch:async(path)=>{calls.push(path);if(path.endsWith('workspace-context'))return {ok:true,json:async()=>({csrf:'test',visible:true,permitted,workspace:{id:'a'.repeat(32),label:'MO',account_ref:'TEST'}})};if(path.endsWith('/saved-login'))return {ok:true,json:async()=>({configured:saved,client_id:'TEST',otp_required:false})};if(path.endsWith('saved-login-start'))return {ok:true,json:async()=>({otp_required:true,message:'Enter OTP'})};if(path.endsWith('login-start'))return {ok:true,json:async()=>({url:'https://broker.test/login'})};if(path.endsWith('login-complete'))return {ok:false,json:async()=>({error:'Rejected callback',auth_required:true})};return {ok,json:async()=>ok?{authenticated:true}:{error:'Expired',auth_required:authRequired}};}};
 vm.runInNewContext(source,scope);await new Promise(r=>setImmediate(r));return {calls,redirects,elements};
}
test('expired session automatically opens broker login once',async()=>{const r=await mount();assert.deepEqual(r.redirects,['https://broker.test/login']);assert.equal(r.calls.filter(p=>p.endsWith('login-start')).length,1);});
test('network failure cannot trigger authentication',async()=>{assert.equal((await mount({authRequired:false})).redirects.length,0);});
test('authenticated session stays on connection page',async()=>{assert.equal((await mount({ok:true})).redirects.length,0);});
test('recent attempt prevents redirect loop',async()=>{assert.equal((await mount({previous:Date.now()})).redirects.length,0);});
test('failed callback never launches another login automatically',async()=>{assert.equal((await mount({search:'?authtoken=mock'})).redirects.length,0);});
test('unassigned connection never triggers authentication',async()=>{assert.equal((await mount({permitted:false})).redirects.length,0);});

test("saved login requests OTP without browser redirect",async()=>{const r=await mount({saved:true});assert.equal(r.redirects.length,0);assert.equal(r.calls.filter(p=>p.endsWith("saved-login-start")).length,1);assert.equal(r.elements.get("otp-form").hidden,false);});
