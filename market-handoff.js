/* AI market research lives inside the existing Analysis Handoff permission scope. */
(function(root){
'use strict';
function organizeHandoff(section,providerPanel,marketPanel){
 const doc=section.ownerDocument,make=(tag,className,text)=>{const n=doc.createElement(tag);n.className=className;if(text)n.textContent=text;return n;};
 const header=section.querySelector(':scope > header');
 let navigation=section.querySelector('[data-handoff-output-actions]');
 if(!navigation){navigation=make('nav','handoff-workspace-actions');navigation.dataset.handoffOutputActions='1';header.after(navigation);}
 navigation.classList.add('handoff-workspace-actions');navigation.setAttribute('aria-label','Analysis workspace actions');
 for(const button of [...section.children].filter(n=>n.tagName==='BUTTON'&&n.textContent==='Saved jobs & outputs'))navigation.prepend(button);
 const grid=section.querySelector('.handoff-grid'),stock=section.querySelector('#collect-candidates')?.closest('section.panel');
 if(stock)stock.id='handoff-stock-analysis';
 marketPanel.id='handoff-market-analysis';
 for(const [target,label] of [[stock,'Stock analysis'],[marketPanel,'Index & commodity analysis']]){
  if(!target||navigation.querySelector('[data-jump="'+target.id+'"]'))continue;
  const jump=make('button','button secondary',label);jump.type='button';jump.dataset.jump=target.id;jump.onclick=()=>target.scrollIntoView({block:'start',behavior:'auto'});navigation.append(jump);
 }
 const broker=section.querySelector('#ticket-broker')?.closest('label');
 const context=make('section','panel handoff-analysis-context');context.setAttribute('aria-label','Analysis account and provider');
 if(broker){broker.classList.add('field');broker.style.cssText='margin:0;min-width:0';context.append(broker);}
 providerPanel.className='handoff-provider';providerPanel.style.cssText='min-width:0';context.append(providerPanel);
 if(grid)grid.before(context);else navigation.after(context);
 if(stock){
  const route=stock.querySelector('.route-set'),collect=section.querySelector('#collect-candidates');
  if(collect){const actions=make('div','handoff-action-row handoff-collect-actions');actions.setAttribute('aria-label','Collect stock candidates');actions.append(collect);const product=stock.querySelector('#cash-product-choice');if(product)product.after(actions);else if(route)route.after(actions);}
  const batch=section.querySelector('#candidate-batch-actions');
  if(batch){
   batch.classList.add('handoff-batch-actions');const selection=make('div','handoff-action-row'),allocation=make('div','handoff-action-row handoff-allocation-actions');
   for(const id of ['select-all-candidates','clear-candidate-selection']){const n=section.querySelector('#'+id);if(n)selection.append(n);}
   for(const n of [...batch.children])allocation.append(n);
   batch.append(selection,allocation);const list=section.querySelector('#candidate-list');if(list)list.before(batch);selection.setAttribute('aria-label','Manual candidate selection');if(list)list.before(selection);
   const selectAll=section.querySelector('#select-all-candidates'),clearAll=section.querySelector('#clear-candidate-selection');
   if(selectAll){selectAll.classList.remove('secondary');selectAll.title='Select eligible recommendations for review; no orders are submitted.';}
   const updateSelectionAvailability=()=>{const ready=!!section.querySelector('.candidate-select:not(:disabled)');if(selectAll)selectAll.disabled=!ready;if(clearAll)clearAll.disabled=!ready;};
   updateSelectionAvailability();if(list)new MutationObserver(updateSelectionAvailability).observe(list,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled']});
  }
 }
 const buttons=[...marketPanel.querySelectorAll(':scope > button')],load=buttons.find(n=>n.textContent==='Load broker instruments'),run=buttons.find(n=>n.textContent==='Analyze selected instruments'),stop=buttons.find(n=>n.textContent==='Stop analysis');
 const title=marketPanel.querySelector('h3'),head=make('div','handoff-market-heading');
 if(title){title.before(head);head.append(title);}
 if(load){load.classList.add('secondary');head.append(load);}
 const select=marketPanel.querySelector('select[multiple]');
 if(select){select.id='handoff-market-symbols';select.style.cssText='width:100%;max-width:none;min-height:180px';const label=make('label','field','Choose up to six instruments');label.htmlFor=select.id;select.before(label);label.append(select);}
 const actions=make('div','handoff-action-row handoff-market-actions');actions.setAttribute('aria-label','Index and commodity analysis actions');
 if(run)actions.append(run);if(stop){stop.classList.add('danger');actions.append(stop);}
 const outputs=make('button','button secondary','Saved jobs & outputs');outputs.type='button';outputs.onclick=()=>{const original=[...navigation.querySelectorAll('button')].find(n=>n.textContent==='Saved jobs & outputs');if(original)original.click();};actions.append(outputs);
 if(select)select.closest('label').after(actions);else marketPanel.append(actions);
 const style=make('style','');style.textContent='#handoff .handoff-workspace-actions,#handoff .handoff-action-row{display:flex;align-items:center;flex-wrap:wrap;gap:10px}#handoff .handoff-workspace-actions{margin:0 0 18px;padding:12px 0;border-block:1px solid #344960}#handoff .handoff-workspace-actions>button:first-child{margin-right:auto}#handoff .handoff-analysis-context{display:grid;grid-template-columns:minmax(220px,.65fr) minmax(0,1.35fr);gap:24px;padding:18px;margin-bottom:16px;align-items:start}#handoff .handoff-analysis-context select{height:40px;box-sizing:border-box}#handoff .handoff-provider label{display:grid;gap:6px;font-size:12px;color:var(--muted)}#handoff .handoff-provider select{width:100%;min-height:40px;background:#081525;color:var(--text);border:1px solid #31506f;border-radius:8px;padding:9px}#handoff .handoff-provider p{font-size:12px;line-height:1.6;color:var(--muted);margin-bottom:0}#handoff .handoff-collect-actions,#handoff .handoff-market-actions{margin:16px 0}#handoff .handoff-market-heading{display:flex;gap:16px;justify-content:space-between;align-items:center;flex-wrap:wrap}#handoff .handoff-market-heading h3{margin:0}#handoff .handoff-batch-actions:not([hidden]){display:grid;gap:14px;padding-top:14px;border-top:1px solid #344960}#handoff .handoff-allocation-actions{align-items:end}#handoff .handoff-action-row .button,#handoff .handoff-workspace-actions .button{min-height:40px;margin:0}#handoff #handoff-market-analysis{margin-top:20px;border-top:3px solid #6c9fc5;scroll-margin-top:16px}#handoff #handoff-stock-analysis{scroll-margin-top:16px}#handoff .handoff-market-outcomes{margin-top:18px;padding-top:16px;border-top:1px solid #344960}#handoff .handoff-market-outcomes:empty:before{content:"No saved analysis for this account. Load instruments, choose up to six, then analyze.";display:block;color:var(--muted);font-size:13px}#handoff [hidden]{display:none!important}@media(max-width:720px){#handoff .handoff-analysis-context{grid-template-columns:1fr;gap:16px}#handoff .handoff-workspace-actions>button:first-child{margin-right:0;flex:1 0 100%}#handoff .handoff-action-row .button{flex:1 1 160px}#handoff .handoff-market-heading{align-items:stretch}#handoff .handoff-market-heading .button{width:100%}}';section.append(style);
}

if(typeof module!=='undefined'&&module.exports){module.exports={organizeHandoff};return;}
if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
let providerSelect,panel,choices,result,note,active,submissionRevision=0,submitting=false,stopRequested=false,stopSent=false,latestJobCreated=0,submittedSymbols=null;
const account=()=>root.BrokerForms?.account('handoff')?.id;
const providerKey=()=> 'sector-pulse:handoff-ai-provider:v1:'+String(root.SectorPulseWorkspace?.username||'user')+':'+String(account()||'dashboard');
function savedProvider(){try{const value=localStorage.getItem(providerKey());return ['RULES_ONLY','CODEX_CHATGPT'].includes(value)?value:'RULES_ONLY';}catch{return 'RULES_ONLY';}}
root.HandoffAIProvider={selected:()=>providerSelect?.value||savedProvider(),payload:()=>{const ai_provider=providerSelect?.value||savedProvider();return {ai_provider,recipient:'codex'};}};
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function button(text,action){const n=el('button',text);n.type='button';n.className='button';n.onclick=action;return n;}
async function request(path,payload){
 const response=await root.BrokerForms.fetch('handoff',path,payload?{method:'POST',headers:{'Content-Type':'application/json',...(path.endsWith('/analyze-market')?{'X-Job-Return-Accepted':'1'}:{})},body:JSON.stringify(payload)}:{cache:'no-store'});
 const data=await response.json();if(!response.ok)throw Error(data.error||data.message||'Broker analysis unavailable.');return data;
}
function render(data,job){
 result.replaceChildren();const heading=el('h4',job?.status==='CANCELLED'?'Analysis cancelled':job?.status==='FAILED'?'Analysis failed':(data.instruments||[]).length?'Analysis outcome':'No eligible recommendations');result.append(heading);if(job)result.append(el('p','Saved job · '+job.status+' · '+new Date(job.updated*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST'));if(data.ai_provider)result.append(el('p','AI path used: '+(data.ai_provider==='RULES_ONLY'?'Broker candles and rule-based analysis — no AI call':'Codex · ChatGPT account')));result.append(el('p',data.ai_review?.summary||'No eligible market recommendation.'));
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
 if((data.exclusions||[]).length)result.append(el('h4','Why instruments were excluded'));for(const row of data.exclusions||[])result.append(el('p',row.symbol+': '+row.reason));if(!(data.instruments||[]).length&&!(data.exclusions||[]).length)result.append(el('p',job?.status==='CANCELLED'?'The job stopped before an instrument outcome was saved. Earlier results remain in Saved jobs & outputs.':'No instrument result was saved. Open Saved jobs & outputs for the job status and any partial output.'));
 result.append(el('small','Saved research as of '+new Date((data.completed_at||data.created_at)*1000).toLocaleString('en-IN')+'. Refresh broker quotes before submitting an order.'));
 if(job?.terminal)root.HandoffLevelReport?.complete(result,{key:(account()||'dashboard')+':market',label:'Completed index & commodity analysis · '+job.status+' · expand output'});
}
async function load(){
 note.textContent='Loading selected-broker index and commodity symbols…';choices.replaceChildren();
 try{const data=await request('/api/analysis-handoff/market-catalog');for(const row of data.instruments||[]){const option=el('option',row.name+' · '+row.symbol);option.value=row.symbol;choices.append(option);}note.textContent=choices.length?'Choose up to six instruments.':'No eligible instruments in this broker master.';}catch(error){note.textContent=error.message;}
}
async function stopAnalysis(){
 stopRequested=true;
 if(!active){note.textContent=submitting?'Stop requested; waiting for the server to accept this job.':'Open Saved jobs to choose an active analysis.';return;}
 if(stopSent)return;stopSent=true;
 try{await root.SectorPulseJobs.client.cancel(active.base,active.job.job_id);note.textContent='Stop requested; partial output will remain saved.';}
 catch(error){stopSent=false;note.textContent=error.message;}
}
async function run(){
 const symbols=[...choices.selectedOptions].map(n=>n.value);if(!symbols.length||symbols.length>6){note.textContent='Choose one to six instruments.';return;}
 note.textContent='Analysis submitted. It continues if you leave this page; retrieve it from Saved jobs.';
 const revision=++submissionRevision;submitting=true;stopRequested=false;stopSent=false;active=null;submittedSymbols=JSON.stringify(symbols);
 try{const data=await request('/api/analysis-handoff/analyze-market',{symbols,account_id:account(),...root.HandoffAIProvider.payload()});if(revision!==submissionRevision)return;if(data.job_accepted){note.textContent='Analysis job accepted. You can continue working; output will appear automatically and remain in Saved jobs.';return;}render(data);note.textContent='Analysis completed and saved.';}catch(error){if(revision===submissionRevision)note.textContent=error.message;}finally{if(revision===submissionRevision){if(!active?.job||active.job.terminal)active=null;submitting=false;}}
}
async function mount(){
 await root.BrokerForms?.ready;const section=document.getElementById('handoff');if(!section)return;
 const providerPanel=el('section');providerPanel.className='panel';providerPanel.style.padding='16px';
 const label=el('label','AI analysis path');providerSelect=el('select');providerSelect.setAttribute('aria-label','AI analysis path');
 for(const [value,title] of [['RULES_ONLY','Broker candles and rule-based analysis — no AI call'],['CODEX_CHATGPT','Codex · ChatGPT account']]){const option=el('option',title);option.value=value;providerSelect.append(option);}
 providerSelect.value=savedProvider();providerSelect.onchange=()=>{try{localStorage.setItem(providerKey(),providerSelect.value);}catch{}};
 label.append(providerSelect);providerPanel.append(label,el('p','Applies to cash equity, stock options, indices and commodities. Only public market evidence is shared. Each submitted job keeps its chosen path; providers never switch automatically. Rule-based mode makes no AI call. Account mode uses the configured server Codex sign-in and its account limits.'));
 const brokerField=section.querySelector('#ticket-broker')?.closest('label');if(brokerField)brokerField.after(providerPanel);else section.prepend(providerPanel);
 panel=el('section');panel.className='panel';panel.style.padding='16px';panel.append(el('h3','AI index & commodity analysis'));
 panel.append(el('p','Selected-broker completed candles and ATM option quotes supply premium entry, target and stop. Symbols with existing exposure are excluded.'));
 choices=el('select');choices.multiple=true;choices.size=7;choices.setAttribute('aria-label','Index and commodity instruments');choices.style.cssText='width:100%;max-width:720px';panel.append(choices);
 panel.append(button('Load broker instruments',load),button('Analyze selected instruments',run),button('Stop analysis',stopAnalysis));
 note=el('p','Load instruments from the selected broker to begin.');note.setAttribute('role','status');result=el('div');result.className='handoff-market-outcomes';result.setAttribute('aria-label','Index and commodity analysis outcomes');panel.append(note,result);section.append(panel);organizeHandoff(section,providerPanel,panel);
 function restoreMarketOutput(){
  if(submitting||(active&&!active.job?.terminal))return;
  const records=[...(root.SectorPulseJobs?.records?.values()||[])].filter(record=>record.job?.request?.path?.endsWith('/analyze-market')&&record.job.request.account_id===account()).sort((a,b)=>b.job.created-a.job.created);
  const record=records[0];if(record&&record.job.created<latestJobCreated)return;
  if(!record){note.textContent='No saved index or commodity analysis for this broker account. Load instruments to begin.';return;}
  latestJobCreated=record.job.created;
  if(record.job.output?.kind==='MARKET_HANDOFF')render(record.job.output,record.job);
  else {result.replaceChildren(el('h4','Analysis '+String(record.job.status).toLowerCase()),el('p',record.job.error||record.job.message||'No output saved yet.'));}
  note.textContent='Latest saved analysis · '+record.job.status+' · belongs to the selected broker account.';
 }
 root.addEventListener('sector-pulse-jobs-refreshed',restoreMarketOutput);
 restoreMarketOutput();
 const owned=d=>d?.job?.request?.path?.endsWith('/analyze-market')&&d.job.request.account_id===account();
 root.addEventListener('sector-pulse-job-submitted',event=>{const d=event.detail;if(!submitting||!owned(d)||JSON.stringify(d.job.request.payload?.symbols)!==submittedSymbols||d.job.created<latestJobCreated)return;active=d;latestJobCreated=d.job.created;stopSent=false;if(stopRequested)void stopAnalysis();});
 root.addEventListener('sector-pulse-job-update',event=>{const d=event.detail;if(!owned(d)||d.job.created<latestJobCreated||(submitting&&!active))return;
  if(active&&active.job.job_id!==d.job.job_id)return;
  if(!d.job.terminal){active=d;latestJobCreated=d.job.created;note.textContent=d.job.message||d.job.status;if(stopRequested)void stopAnalysis();}
  else {active=null;submitting=false;if(d.job.output?.kind==='MARKET_HANDOFF'&&d.job.status!=='COMPLETED'){render(d.job.output,d.job);note.textContent=d.job.message||d.job.status;}}
 });
 root.addEventListener('sector-pulse-job-output',event=>{const d=event.detail;if(d.output?.kind==='MARKET_HANDOFF'&&d.job.request.account_id===account()&&d.job.created>=latestJobCreated){latestJobCreated=d.job.created;render(d.output,d.job);}});
 root.addEventListener('broker-account-change',()=>{submissionRevision++;providerSelect.value=savedProvider();choices.replaceChildren();result.replaceChildren();active=null;submitting=false;stopRequested=false;stopSent=false;latestJobCreated=0;note.textContent='Load instruments for the selected broker.';restoreMarketOutput();});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})(typeof window==='undefined'?globalThis:window);
