/* Explicit manual account selection; never expands runner or schedule authority. */
(function(root){
'use strict';
const widgets=new Map(),money=v=>Number(v||0).toLocaleString('en-IN',{maximumFractionDigits:2,minimumFractionDigits:2});
const el=(tag,text)=>Object.assign(document.createElement(tag),{textContent:text||''});
async function api(action,payload){
 const response=await fetch('/api/manual-multi/'+action,payload?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}:{});
 let data;try{data=await response.json();}catch(_){throw Error('Broker-wise order service is awaiting dashboard activation (HTTP '+response.status+').');}if(!response.ok)throw Error(data.error||'Broker review unavailable.');return data;
}
let readiness;
function serviceReady(){return readiness||(readiness=api('history'));}
function invalidate(widget){
 widget.revision=(widget.revision||0)+1;widget.review=null;widget.output.replaceChildren();widget.submit.disabled=true;
 const host=widget.host;
 host.querySelectorAll('#submit-ticket,#submit-handoff-batch,#submit-screener-order').forEach(b=>b.disabled=true);
}
function mount(id,budgetId){
 const host=document.getElementById(id);if(!host||widgets.has(id))return;
 const panel=el('section');panel.className='multi-account-ticket';
 const toggle=el('input');toggle.type='checkbox';const label=el('label','Use Live broker-wise allocation');label.prepend(toggle);
 const details=el('div');details.hidden=true;
 const note=el('p','Each ticked broker receives the full declared pool, distributed across its selected stocks. Choose its execution account and review exact instruments, quantities and costs. Runners and schedules keep their existing scope.');
 const amountLabel=el('label','Pool per broker (₹)');amountLabel.className='field';const amount=el('input');amount.type='number';amount.min='0.01';amount.step='0.01';amountLabel.append(amount);
 const list=el('div');list.className='multi-account-list';
 const history=el('button','Recent broker results');history.type='button';history.className='button secondary';
 const output=el('div');output.className='multi-account-results';output.setAttribute('aria-live','polite');
 const submit=el('button','Submit reviewed Live broker orders');submit.type='button';submit.className='button danger';submit.disabled=true;
 const availability=el('p');availability.className='multi-broker-availability';details.append(note,amountLabel,list,history,output,submit);panel.append(label,availability,details);
 host.append(panel);
 const widget={host,toggle,details,amount,list,output,submit,availability,budgetId,review:null};widgets.set(id,widget);
 const existing=()=>document.getElementById(budgetId)?.value||(['ticket-panel','handoff-batch-panel'].includes(id)?document.querySelector('#handoff [aria-label="Handoff shared capital"]')?.value:'')||(['trade-parser-order','order'].includes(id)?'50000':'');
 widget.defaultAmount=existing;
 toggle.onchange=()=>{details.hidden=!toggle.checked;if(!amount.value)amount.value=existing();invalidate(widget);
 const legacy=host.querySelector('#trade-parser-submit-order,#prepare');if(legacy){if(!legacy.dataset.singleLabel)legacy.dataset.singleLabel=legacy.textContent;legacy.textContent=toggle.checked?'Prepare selected account reviews':legacy.dataset.singleLabel;}
 if(id==='order'){const quantity=host.querySelector('[name=quantity]');if(quantity)quantity.disabled=toggle.checked;}
 if(id==='trade-parser-order'&&document.getElementById('trade-parser-input')?.value.trim())document.getElementById('trade-parser-run')?.click();
 };
 details.addEventListener('input',event=>{if(event.target===amount)amount.dataset.edited='true';invalidate(widget);});
 document.getElementById(budgetId)?.addEventListener('input',event=>{if(!amount.dataset.edited)amount.value=event.target.value;invalidate(widget);});
 history.onclick=async()=>{try{const result=await api('history');render(widget,{rows:result.batches.flatMap(b=>b.rows.map(r=>({...r,batch_id:b.batch_id})))},true);}catch(e){output.textContent=e.message;}};
 submit.onclick=async()=>{if(!widget.review)return;submit.disabled=true;try{const result=await api('submit',{batch_id:widget.review.batch_id,confirmation:widget.review.confirmation_phrase});render(widget,result,true);widget.review=null;}catch(e){output.textContent=e.message+' Refresh Recent broker results before any further action.';}};
 populate(widget);
}
async function populate(widget){
 try{
 await root.BrokerForms?.ready;
 const response=await fetch('/api/workspaces/accounts');const data=await response.json();if(!response.ok)throw Error(data.error||'Account inventory unavailable.');
 const current=(widget.host.id==='order'?(document.getElementById('account')?.value?{id:document.getElementById('account').value}:null):widget.host.id==='trade-parser-order'?root.BrokerForms?.account('parser'):root.BrokerForms?.account('manual')||root.BrokerForms?.account('handoff'))||root.SectorPulseWorkspace?.workspace;
 widget.list.replaceChildren();
 const groups=new Map();
 for(const a of data.accounts||[]){if(!groups.has(a.broker))groups.set(a.broker,[]);groups.get(a.broker).push(a);}
 const names={FYERS:'FYERS',DHAN:'Dhan',MOTILAL_OSWAL:'Motilal Oswal',DELTA_INDIA:'Delta India'};
 for(const [broker,accounts] of groups){
  const a=accounts.find(a=>a.id===current?.id)||accounts[0],brokerName=names[broker]||broker;
  const row=el('div');row.className='multi-account-row';row.dataset.account=a.id;
  const checked=el('input');checked.type='checkbox';checked.checked=accounts.some(a=>a.id===current?.id);checked.setAttribute('aria-label','Include '+brokerName);
  const name=el('label',brokerName);name.prepend(checked);
  const execution=el('select');execution.setAttribute('aria-label',brokerName+' execution account');
  for(const option of accounts){const node=el('option',option.label+(option.account_ref?' · '+option.account_ref:''));node.value=option.id;execution.append(node);}
  execution.value=a.id;execution.onchange=()=>{row.dataset.account=execution.value;invalidate(widget);};
  const identity=el('div');identity.className='multi-broker-identity';identity.append(name,el('small','Execution account'),execution);
  const amount=el('input');amount.type='number';amount.min='0.01';amount.step='0.01';amount.placeholder='Use shared broker pool';amount.setAttribute('aria-label',brokerName+' pool override');
  const risk=el('input');risk.type='number';risk.min='0';risk.step='0.01';risk.placeholder='Existing open risk (₹)';risk.setAttribute('aria-label',brokerName+' existing open risk');
  row.append(identity,amount,risk);widget.list.append(row);
 }
 await serviceReady();
 }catch(e){widget.toggle.disabled=true;widget.availability.textContent=e.message+' Existing single-broker orders remain available.';}
}
function render(widget,data,history=false){
 widget.output.replaceChildren();
 const total=(data.rows||[]).reduce((sum,row)=>sum+Number(row.allocation?.amount||row.requested_amount||0),0);
 if(total>0)widget.output.append(el('p','Combined broker pools ₹'+money(total)+' · each pool is distributed across that broker’s selected stocks.'));
 for(const row of data.rows||[]){
  const card=el('section');card.className='multi-account-result';card.append(el('strong',row.broker+' · '+row.label+' · '+(row.result?.status||row.state)));
  if(row.allocation)card.append(el('p','Amount ₹'+money(row.allocation.amount)+' · reserved ₹'+money(row.allocation.reserved)+' · unspent ₹'+money(row.allocation.unspent)));
  if(row.error)card.append(el('p',row.error));
  const nativeItems=row.preview?.items||(row.preview?[row.preview]:[]);
  const contracts=nativeItems.flatMap(item=>(item.instrument?.contracts||[item.order||item.body||item.contract||{}]).map(c=>({symbol:c.symbol||item.symbol||c.tradingsymbol||c.securityId||'Native contract',qty:c.quantity??c.qty??item.units,price:c.limit_price??c.limitPrice??c.price,cost:item.margin_required??item.instrument?.minimum_cash_required??item.order_value,product:item.order_policy?.product_type||item.ticket?.productType||c.productType||c.producttype||c.product||'See exact review'})));
  if(contracts.length){
   const table=el('table');table.className='multi-order-table';
   const head=el('tr');for(const title of ['Instrument','Quantity','Limit','Cash / margin','Product'])head.append(el('th',title));table.append(head);
   for(const c of contracts){const tr=el('tr'),titles=['Instrument','Quantity','Limit','Cash / margin','Product'];[c.symbol,c.qty??'—',c.price==null?'—':money(c.price),c.cost==null?'See exact review':money(c.cost),c.product].forEach((value,index)=>{const td=el('td',String(value));td.dataset.label=titles[index];tr.append(td);});table.append(tr);}
   card.append(table);
  }
  const review=el('details'),summary=el('summary','Exact orders and broker result');review.append(summary);
  const pre=el('pre');pre.className='packet-preview';pre.textContent=JSON.stringify(row.result||row.preview||row,(_key,value)=>typeof value==='number'?Number(value.toFixed(2)):value,2);review.append(pre);card.append(review);widget.output.append(card);
 }
 widget.submit.disabled=history||!(data.rows||[]).some(r=>r.state==='READY');
}
async function prepare(id,ticket){
 const widget=widgets.get(id);if(!widget?.toggle.checked)return null;
 invalidate(widget);
 if(!widget.amount.value)widget.amount.value=widget.defaultAmount?.()||document.getElementById(widget.budgetId)?.value||'';
 const amount=Number(widget.amount.value);if(!(amount>0&&Number.isFinite(amount)))throw Error('Enter the amount to apply independently to each selected broker.');
 const items=[];
 for(const row of widget.list.children){
  const inputs=row.querySelectorAll('input');if(!inputs[0].checked)continue;
  const body=structuredClone(ticket),risk=inputs[2].value;
  const sourceId=body.source_account_id||body.account_id||body.items?.[0]?.account_id||root.BrokerForms?.account('manual')?.id;
  const apply=item=>{item.external_open_risk=risk!==''?Number(risk):row.dataset.account===sourceId?(item.external_open_risk??null):null;};
  if(body._native_dhan)apply(body.native_payload);else if(body.items)body.items.forEach(apply);else apply(body);
  items.push({account_id:row.dataset.account,amount:inputs[1].value||amount,ticket:body});
 }
 if(!items.length)throw Error('Tick at least one broker.');
 const revision=widget.revision;const result=await api('prepare',{items,flow:id==='screener-order'?'screener':id==='trade-parser-order'?'trade-parser':id==='order'?'dhan-entry':'handoff'});
 if(widget.revision!==revision)throw Error('Order inputs changed while reviewing. Prepare again. No order was submitted.');
 widget.review=result;render(widget,result);
 return {multi_account:true,preview_id:result.batch_id,confirmation_phrase:result.confirmation_phrase,live_submission_enabled:false,submission_eligible:false,aggregate:{order_count:0,total_worst_case_risk:0,cash_reserved:0},warnings:['Review and submit using the selected-account panel below.']};
}
function boot(){mount('ticket-panel','handoff-allocation-budget');mount('handoff-batch-panel','handoff-allocation-budget');mount('screener-order','screener-allocation-budget');mount('trade-parser-order','parser-native-budget');mount('order','manual-order-amount');}
for(const name of ['input','change'])document.addEventListener(name,event=>{
 if(event.target.closest?.('.multi-account-ticket'))return;
 if(event.target.id==='account'){for(const widget of widgets.values())populate(widget);}
 for(const widget of widgets.values())if(widget.review)invalidate(widget);
},true);
root.addEventListener('broker-account-change',()=>{for(const widget of widgets.values()){invalidate(widget);populate(widget);}});
root.addEventListener('manual-ticket-account-ready',()=>{boot();for(const widget of widgets.values())populate(widget);});
root.MultiAccountOrders={prepare,enabled:id=>!!widgets.get(id)?.toggle.checked,boot};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
root.addEventListener('broker-accounts-ready',()=>{boot();for(const w of widgets.values())if(!w.review)populate(w);});
})(window);
