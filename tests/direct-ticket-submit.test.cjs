const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
for(const file of ['dashboard-enhancements.js']){
 test(file+': Submit uses displayed preview without typing and sends once',async()=>{
  const source=fs.readFileSync(path.join(__dirname,'..',file),'utf8');
  const start=source.indexOf("$('screener-route-preview-groups').innerHTML=groups.map");
  const end=source.indexOf("    } catch (error) {invalidateScreenerOrderPreview(error.message)}",start);
  assert(start>=0&&end>start);
  const dom=new JSDOM('<div id="screener-route-preview-groups"></div><p id="screener-order-status"></p>');
  const $=id=>dom.window.document.getElementById(id);let calls=[];
  const groups=[{route:'EQUITY',budget:1000,preview:{preview_id:'p',confirmation_phrase:'CONFIRM p',live_submission_enabled:true,submission_eligible:true,aggregate:{cash_reserved:900,order_count:1}}},
   {route:'LONG_OPTION',budget:1000,preview:{preview_id:'blocked',live_submission_enabled:false,submission_eligible:true,aggregate:{cash_reserved:900,order_count:1}}}];
  const post=async(url,body)=>{calls.push({url,body});return {status:'PENDING',message:'Fake broker only'};};
  new Function('groups','$','escapeHtml','screenerRouteLabel','money','postJson','screenerOrderPreview',source.slice(start,end))(groups,$,String,String,String,post,{});
  assert.equal(dom.window.document.querySelector('input'),null);
  const buttons=dom.window.document.querySelectorAll('button');assert.equal(buttons[0].disabled,false);assert.equal(buttons[1].disabled,true);assert.equal(calls.length,0);
  buttons[0].click();buttons[0].click();await new Promise(r=>setImmediate(r));
  assert.deepEqual(calls,[{url:'/api/trade-ticket/submit-batch',body:{preview_id:'p',confirmation:'CONFIRM p'}}]);
  assert.equal(buttons[0].disabled,true);assert.equal(groups[0].consumed,true);
  assert(!source.includes('Exact confirmation phrase'));assert(!source.includes('Exact fresh confirmation phrase'));
  dom.window.close();
 });
}
test('archived older account dashboard also enables Submit without typing',{skip:!fs.existsSync(path.join(__dirname,'../outputs/direct-ticket-submit/account-dashboard.after.js'))},async()=>{
 const source=fs.readFileSync(path.join(__dirname,'../outputs/direct-ticket-submit/account-dashboard.after.js'),'utf8');
 assert(source.includes("$('submit-screener-order').disabled = !preview.live_submission_enabled || !preview.submission_eligible"));
 assert(!source.includes('Exact fresh confirmation phrase'));
 const start=source.indexOf('  const submitScreenerOrder = async () => {');
 const end=source.indexOf('  renderScreenerSources()',start);
 const dom=new JSDOM('<button id="submit-screener-order"></button><pre id="screener-order-preview"></pre><p id="screener-order-status"></p>');
 const $=id=>dom.window.document.getElementById(id),calls=[];
 const handler=new Function('$','screenerOrderPreview','postJson',source.slice(start,end)+';return submitScreenerOrder;')($,{preview_id:'legacy',confirmation_phrase:'CONFIRM legacy'},async(url,body)=>{calls.push(body);return {status:'PENDING',message:'Fake broker only'};});
 await handler();assert.deepEqual(calls,[{preview_id:'legacy',confirmation:'CONFIRM legacy'}]);
 assert.equal($('submit-screener-order').disabled,true);dom.window.close();
});
