/* AI market research lives inside the existing Analysis Handoff permission scope. */
(function(root){
'use strict';
if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
let panel,choices,result,note,active,submissionRevision=0;
const account=()=>root.BrokerForms?.account('handoff')?.id;
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function button(text,action){const n=el('button',text);n.type='button';n.className='button';n.onclick=action;return n;}
async function request(path,payload){
 const response=await root.BrokerForms.fetch('handoff',path,payload?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}:{cache:'no-store'});
 const data=await response.json();if(!response.ok)throw Error(data.error||data.message||'Broker analysis unavailable.');return data;
}
function render(data){
 result.replaceChildren();result.append(el('p',data.ai_review?.summary||'No eligible market recommendation.'));
 for(const row of data.instruments||[]){
  const card=el('article');card.className='panel';card.style.padding='12px';
  const rec=row.recommendation||{};card.append(el('h4',row.symbol+' · '+(rec.decision||'WAIT')+' · '+(rec.confidence||'')),el('p',rec.rationale||''));
  const plan=row.recommended_plan;
  if(plan){
   card.append(el('p','BUY '+plan.option_type+' · '+plan.symbol));
   const table=el('table');const body=el('tbody');
   for(const [label,value] of [['ATM premium entry',plan.entry],['Premium target',plan.target],['Premium stop loss',plan.stop_loss],['Reward / risk',plan.reward_to_risk],['Lot size',plan.lot_size]]){const tr=el('tr');tr.append(el('th',label),el('td',value===undefined?'Unavailable':String(value)));body.append(tr);}
   table.append(body);card.append(table);
  }
  for(const risk of rec.risks||[])card.append(el('p',risk));
  result.append(card);
 }
 for(const row of data.exclusions||[])result.append(el('p',row.symbol+': '+row.reason));
 result.append(el('small','Saved research as of '+new Date((data.completed_at||data.created_at)*1000).toLocaleString('en-IN')+'. Refresh broker quotes before submitting an order.'));
}
async function load(){
 note.textContent='Loading selected-broker index and commodity symbols…';choices.replaceChildren();
 try{const data=await request('/api/analysis-handoff/market-catalog');for(const row of data.instruments||[]){const option=el('option',row.name+' · '+row.symbol);option.value=row.symbol;choices.append(option);}note.textContent=choices.length?'Choose up to six instruments.':'No eligible instruments in this broker master.';}catch(error){note.textContent=error.message;}
}
async function run(){
 const symbols=[...choices.selectedOptions].map(n=>n.value);if(!symbols.length||symbols.length>6){note.textContent='Choose one to six instruments.';return;}
 note.textContent='Analysis submitted. It continues if you leave this page; retrieve it from Saved jobs.';
 const revision=++submissionRevision;
 try{const data=await request('/api/analysis-handoff/analyze-market',{symbols,account_id:account()});if(revision!==submissionRevision)return;render(data);note.textContent='Analysis completed and saved.';}catch(error){if(revision===submissionRevision)note.textContent=error.message;}finally{if(revision===submissionRevision)active=null;}
}
async function mount(){
 await root.BrokerForms?.ready;const section=document.getElementById('handoff');if(!section)return;
 panel=el('section');panel.className='panel';panel.style.padding='16px';panel.append(el('h3','AI index & commodity analysis'));
 panel.append(el('p','Selected-broker completed candles and ATM option quotes supply premium entry, target and stop. Symbols with existing exposure are excluded.'));
 choices=el('select');choices.multiple=true;choices.size=7;choices.setAttribute('aria-label','Index and commodity instruments');choices.style.cssText='width:100%;max-width:720px';panel.append(choices);
 panel.append(button('Load broker instruments',load),button('Analyze selected instruments',run),button('Stop analysis',async()=>{try{if(active)await root.SectorPulseJobs.client.cancel(active.base,active.job.job_id);else note.textContent='Open Saved jobs to choose an active analysis.';}catch(error){note.textContent=error.message;}}));
 note=el('p','Load instruments from the selected broker to begin.');note.setAttribute('role','status');result=el('div');panel.append(note,result);section.append(panel);
 root.addEventListener('sector-pulse-job-update',event=>{const d=event.detail;if(d.job.request?.path?.endsWith('/analyze-market')&&d.job.request.account_id===account()&&!d.job.terminal){active=d;note.textContent=d.job.message||d.job.status;}});
 root.addEventListener('sector-pulse-job-output',event=>{const d=event.detail;if(d.output?.kind==='MARKET_HANDOFF'&&d.job.request.account_id===account())render(d.output);});
 root.addEventListener('broker-account-change',()=>{submissionRevision++;choices.replaceChildren();result.replaceChildren();active=null;note.textContent='Load instruments for the selected broker.';});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})(window);
