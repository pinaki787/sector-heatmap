const {test}=require('node:test'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom'),fs=require('node:fs');
const source=fs.readFileSync(require('node:path').resolve(__dirname,'../resource-restarts.js'),'utf8');
const settle=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
function setup(saved,handler){
 const dom=new JSDOM('<section><header></header></section>',{url:'https://dashboard.test',runScripts:'outside-only'}),w=dom.window;
 const ticks=[];w.setInterval=fn=>{ticks.push(fn);return ticks.length;};w.clearInterval=()=>{};
 const timers=[];w.setTimeout=fn=>{timers.push(fn);return timers.length;};w.clearTimeout=()=>{};w.AbortSignal.timeout=()=>undefined;
 if(saved)w.localStorage.setItem('sector-pulse:service-restart:owner',saved);
 w.fetch=async(url,options)=>handler(url,options);w.eval(source);w.ServerRestarts.mount(w.document.querySelector('section'),{admin:true,username:'owner'});
 return {w,dom,timers,ticks,button:w.document.querySelector('[data-dashboard]'),status:()=>w.document.querySelector('[data-outcome]').textContent,saved:()=>w.localStorage.getItem('sector-pulse:service-restart:owner')};
}
const response=data=>({ok:true,json:async()=>data});
test('lost restart response probes every two seconds, never repeats POST, and persists READY',async()=>{
 let posts=0,id;const app=setup(null,async(url,opts)=>{
  if(url.endsWith('/me'))return response({csrf:'token'});
  if(url.endsWith('/restart-targets'))return response({accounts:[]});
  if(url.endsWith('/service-restart')){posts++;id=JSON.parse(opts.body).request_id;throw Error('connection lost');}
  return response({request_id:id,status:'READY',message:'Replacement ready'});
 });
 app.button.click();await settle();assert.equal(posts,1);assert.match(app.status(),/WAITING/);assert.equal(app.button.disabled,true);
 await app.timers.at(-1)();await settle();assert.match(app.status(),/READY/);assert.equal(posts,1);assert.equal(app.button.disabled,false);
 assert.equal(JSON.parse(app.saved()).status,'READY');app.dom.window.close();
});
test('reload resumes saved request without submitting another restart',async()=>{
 let posts=0;const saved=JSON.stringify({kind:'dashboard',id:'saved-request',status:'WAITING',label:'Dashboard',startedAt:Date.now(),events:[]});
 const app=setup(saved,async(url,opts)=>{if(opts.method==='POST')posts++;return response(url.endsWith('/restart-targets')?{accounts:[]}:{request_id:'saved-request',status:'READY',message:'Recovered'});});
 await settle();assert.equal(posts,0);assert.match(app.status(),/READY/);app.dom.window.close();
});
test('definitive rejection immediately reports blocker rather than waiting for recovery',async()=>{
 const app=setup(null,async url=>url.endsWith('/restart-targets')?response({accounts:[]}):url.endsWith('/me')?response({csrf:'token'}):({ok:false,status:400,json:async()=>({error:'Active runner blocks restart'})}));
 app.button.click();await settle();assert.match(app.status(),/FAILED.*Active runner/);assert.equal(app.w.document.querySelector('progress').value,0);assert.equal(app.w.document.querySelector('progress').getAttribute('aria-valuetext'),'Restart failed');assert.equal(app.button.disabled,false);app.dom.window.close();
});
test('non administrators receive no restart controls',()=>{
 const dom=new JSDOM('<section><header></header></section>',{runScripts:'outside-only'});dom.window.eval(source);dom.window.ServerRestarts.mount(dom.window.document.querySelector('section'),{admin:false});assert.equal(dom.window.document.querySelector('[data-dashboard]'),null);dom.window.close();
});

test('opening resources retrieves the server restart outcome without browser storage',async()=>{
 const app=setup(null,async url=>response(url.endsWith('/restart-targets')?{accounts:[]}:{request_id:'server-request',started_at:Date.now()/1000,status:'READY',message:'Dashboard is ready'}));
 await settle();assert.match(app.status(),/READY/);assert.equal(JSON.parse(app.saved()).id,'server-request');app.dom.window.close();
});

test('progress is indeterminate during checks and completed only after READY',async()=>{
 let id;
 const app=setup(null,async(url,opts)=>{
  if(url.endsWith('/me'))return response({csrf:'token'});
  if(url.endsWith('/restart-targets'))return response({accounts:[]});
  if(url.endsWith('/service-restart')){id=JSON.parse(opts.body).request_id;return response({status:'SCHEDULED',message:'Accepted'});}
  return response({request_id:id,status:'READY',message:'Ready'});
 });
 app.button.click();await settle();const bar=app.w.document.querySelector('progress');
 assert.equal(bar.hasAttribute('value'),false);assert.match(bar.getAttribute('aria-valuetext'),/accepted/);
 await app.timers.at(-1)();await settle();assert.equal(bar.value,1);assert.equal(app.w.document.querySelectorAll('.restart-stages [data-state="done"]').length,4);
 assert.match(app.w.document.querySelector('[data-probes]').textContent,/1 status checks/);app.dom.window.close();
});
test('elapsed timer updates each second while readiness is pending, without another command',async()=>{
 let now=Date.now();const saved=JSON.stringify({kind:'dashboard',id:'waiting',status:'WAITING',label:'Dashboard',startedAt:now-4000,events:[]});
 const app=setup(saved,async url=>url.endsWith('/restart-targets')?response({accounts:[]}):new Promise(()=>{}));
 app.w.Date.now=()=>now;assert.equal(app.ticks.length,1);now+=5000;app.ticks[0]();
 assert.match(app.w.document.querySelector('[data-elapsed]').textContent,/9s elapsed/);
 assert.equal(app.w.document.querySelector('progress').hasAttribute('value'),false);app.dom.window.close();
});
