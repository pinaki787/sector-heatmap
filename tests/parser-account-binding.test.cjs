const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
async function page({accounts,url='https://portal.example/',saved,username='owner',native=true}={}){
 const dom=new JSDOM('<body><section id="trade-parser"><label>Recommendation<textarea id="trade-parser-input">keep this source text</textarea></label></section><section id="open-positions"></section></body>',{url,runScripts:'outside-only'});
 const w=dom.window;w.AbortSignal=AbortSignal;let mutations=0;
 const observers=[],Observer=w.MutationObserver;w.MutationObserver=class extends Observer{constructor(fn){super(fn);observers.push(this)}};const close=dom.window.close.bind(dom.window);dom.window.close=()=>{observers.forEach(o=>o.disconnect());close()};
 if(saved)for(const [key,value] of Object.entries(saved))w.localStorage.setItem(key,value);
 w.fetch=async (url,options)=>{
  if(options?.method==='POST')mutations++;
  return {ok:true,json:async()=>url==='/api/workspace-context'?{username,workspace:null,parser_native_supported:native}:url==='/api/workspaces/accounts'?{accounts}:url.startsWith('/api/dhan/capabilities')?{strategy_routes:['renko','rsi','band','kama']}: {}};
 };
 w.eval(fs.readFileSync('broker-form-routing.js','utf8'));w.eval(fs.readFileSync('broker-account-options.js','utf8'));
 for(let n=0;n<30&&!w.document.getElementById('parser-broker-account');n++)await new Promise(r=>setTimeout(r,5));
 return {dom,w,mutations:()=>mutations};
}
const dhan={id:'d',broker:'DHAN',label:'Algo',configured:true},fyers={id:'f',broker:'FYERS',label:'FYERS',configured:true};
test('connected sole Dhan initializes Parser and Live Feed without clearing text or sending mutations',async()=>{
 const {dom,w,mutations}=await page({accounts:[dhan]});
 assert.equal(w.BrokerForms.account('parser').id,'d');assert.equal(w.BrokerForms.account('account').id,'d');
 assert.equal(w.document.getElementById('trade-parser-input').value,'keep this source text');assert.equal(mutations(),0);dom.window.close();
});
test('multiple owned accounts require selection, then preserve the per-user choice',async()=>{
 const first=await page({accounts:[dhan,fyers]});assert.equal(first.w.BrokerForms.account('parser'),null);first.dom.window.close();
 const saved=await page({accounts:[dhan,fyers],saved:{'parser-account:owner':'account:d'}});
 assert.equal(saved.w.BrokerForms.account('parser').id,'d');saved.dom.window.close();
 const other=await page({accounts:[dhan,fyers],username:'other',saved:{'parser-account:owner':'account:d'}});
 assert.equal(other.w.BrokerForms.account('parser'),null);other.dom.window.close();
});
test('explicit owned context takes precedence; foreign context never falls back',async()=>{
 for(const [id,expected] of [['d','d'],['foreign',null]]){
  const p=await page({accounts:[dhan,fyers],url:'https://portal.example/?brokerAccount='+id});
  assert.equal(p.w.BrokerForms.account('parser')?.id||null,expected);p.dom.window.close();
 }
});
test('missing connection and pending backend activation remain explicit unavailable states',async()=>{
 const missing=await page({accounts:[{...dhan,configured:false}]});assert.equal(missing.w.BrokerForms.account('parser'),null);missing.dom.window.close();
 const old=await page({accounts:[dhan],native:false});assert.equal(old.w.BrokerForms.account('parser'),null);assert.match(old.w.document.getElementById('parser-broker-account').textContent,/activation pending/);old.dom.window.close();
});
