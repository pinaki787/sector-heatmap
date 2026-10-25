const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('/home/trading/sector-heatmap/.private/test-node/node_modules/jsdom');
test('captured rerun keeps exact saved payload and account route, and never starts a runner',async()=>{
 const dom=new JSDOM('<main class="work"></main>',{url:'https://example.test/',runScripts:'outside-only'}),w=dom.window;w.AbortSignal.timeout=()=>undefined;w.HTMLElement.prototype.scrollIntoView=function(){};
 const payload={account_id:'a'.repeat(32),period:'custom',from_date:'2026-10-16',to_date:'2026-10-16',allow_download:false,settings:{ema_third_enabled:true,ema_third_length:100,lots:'1'}};
 const old={job_id:'old',kind:'ANALYSIS',feature:'renko-supertrend',label:'Captured',created:1,status:'COMPLETED',terminal:true,output:{status:'INCOMPLETE'},request:{account_id:payload.account_id,path:'/api/renko-supertrend/backtest',payload}};
 const next={...old,job_id:'new',created:2,output:{status:'COMPLETE'}};const posts=[];
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[{id:payload.account_id,label:'FYERS',broker:'FYERS',configured:true}],account:()=>null};
 w.fetch=async(url,opt={})=>{if(opt.method==='POST'){posts.push([String(url),JSON.parse(opt.body)]);return {ok:true,status:200,json:async()=>({job_id:'new',job:next})};}return {ok:true,json:async()=>String(url).includes('job_id=new')?next:{jobs:String(url).includes('/broker-workspace/')?[old]:[]}};};
 w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await new Promise(r=>setTimeout(r,40));w.SectorPulseJobs.open('ANALYSIS');await new Promise(r=>setTimeout(r,20));
 [...w.document.querySelectorAll('button')].find(x=>x.textContent==='Open saved output').click();[...w.document.querySelectorAll('button')].find(x=>x.textContent==='Rerun captured backtest').click();await new Promise(r=>setTimeout(r,40));
 assert.equal(posts.length,1);assert.match(posts[0][0],new RegExp('/broker-workspace/'+payload.account_id+'/api/renko-supertrend/backtest'));assert.deepEqual(posts[0][1],payload);assert(!/start|order|cancel/.test(posts[0][0]));assert.match(w.document.querySelector('#saved-job-report').textContent,/COMPLETE/);dom.window.close();
});
