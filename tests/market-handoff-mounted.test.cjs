const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const {JSDOM}=require('jsdom');
const tick=()=>new Promise(r=>setImmediate(r));
test('market panel uses selected broker, persists render event, and clears cross-account output',async()=>{
 const dom=new JSDOM('<section id="handoff"></section>',{url:'https://host/',runScripts:'outside-only'});const w=dom.window;let aid='selected';const calls=[];
 const output={kind:'MARKET_HANDOFF',created_at:1,completed_at:2,ai_review:{summary:'Saved AI review'},instruments:[{symbol:'NSE:NIFTY50-INDEX',recommendation:{decision:'BULLISH',confidence:'MODERATE',rationale:'Completed candles',risks:[]},recommended_plan:{symbol:'EXACT-ATM',option_type:'CE',entry:100,target:120,stop_loss:90,lot_size:65,reward_to_risk:2}}],exclusions:[]};
 w.BrokerForms={ready:Promise.resolve(),account:()=>({id:aid}),fetch:async(kind,path,options)=>{calls.push({kind,path,options});return {ok:true,json:async()=>path.endsWith('market-catalog')?{instruments:[{symbol:'NSE:NIFTY50-INDEX',name:'NIFTY'}]}:output};}};
 w.eval(fs.readFileSync('market-handoff.js','utf8'));await tick();
 const click=text=>[...w.document.querySelectorAll('button')].find(n=>n.textContent===text).click();
 click('Load broker instruments');await tick();const select=w.document.querySelector('select');select.options[0].selected=true;
 click('Analyze selected instruments');await tick();assert.match(w.document.body.textContent,/ATM premium entry100/);assert.match(w.document.body.textContent,/Premium stop loss90/);
 assert.equal(calls[1].kind,'handoff');assert.equal(JSON.parse(calls[1].options.body).account_id,'selected');
 w.dispatchEvent(new w.CustomEvent('broker-account-change'));assert(!w.document.body.textContent.includes('EXACT-ATM'));
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-output',{detail:{job:{request:{account_id:'another'}},output}}));assert(!w.document.body.textContent.includes('EXACT-ATM'));
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-output',{detail:{job:{request:{account_id:aid}},output}}));assert(w.document.body.textContent.includes('EXACT-ATM'));
 dom.window.close();
});
