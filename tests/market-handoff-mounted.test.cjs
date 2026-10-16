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

test('Stop before acceptance cancels the submitted market job once and retains partial output',async()=>{
 const dom=new JSDOM('<section id="handoff"></section>',{url:'https://host/',runScripts:'outside-only'});const w=dom.window,cancels=[];let finish;
 w.BrokerForms={ready:Promise.resolve(),account:()=>({id:'selected'}),fetch:async(kind,path)=>path.endsWith('market-catalog')?{ok:true,json:async()=>({instruments:[{symbol:'NIFTY',name:'NIFTY'}]})}:new Promise(resolve=>{finish=resolve;})};
 w.SectorPulseJobs={client:{cancel:async(base,id)=>cancels.push({base,id})}};
 w.eval(fs.readFileSync('market-handoff.js','utf8'));await tick();
 const click=text=>[...w.document.querySelectorAll('button')].find(n=>n.textContent===text).click();
 click('Load broker instruments');await tick();w.document.querySelector('option').selected=true;
 click('Analyze selected instruments');click('Stop analysis');assert.match(w.document.body.textContent,/waiting for the server/);assert.equal(cancels.length,0);
 const job={job_id:'owned-job',kind:'ANALYSIS',created:2,status:'RUNNING',terminal:false,request:{path:'/api/analysis-handoff/analyze-market',account_id:'selected',payload:{symbols:['NIFTY']}}};
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{job:{...job,job_id:'older-job',created:1},base:'https://host/api/jobs'}}));assert.equal(cancels.length,0);
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-submitted',{detail:{job,base:'https://host/api/jobs'}}));await tick();click('Stop analysis');await tick();
 assert.deepEqual(cancels,[{base:'https://host/api/jobs',id:'owned-job'}]);
 const output={kind:'MARKET_HANDOFF',created_at:1,ai_review:{summary:'Partial broker evidence retained'},instruments:[],exclusions:[]};
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{job:{...job,terminal:true,status:'CANCELLED',message:'Stopped; partial output retained.',output},base:'https://host/api/jobs'}}));
 finish({ok:false,json:async()=>({error:'Stopped; partial output retained.'})});await tick();assert.match(w.document.body.textContent,/Partial broker evidence retained/);
 dom.window.close();
});
