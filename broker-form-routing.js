/* Shared strategy forms; account routing never changes or starts a runner. */
(function(root){
'use strict';
const IDS={parser:'parser-broker-account',account:'live-feed-broker-account',sector:'sector-broker-account',band:'ema-band-broker-account',rsi:'cross-broker-account',kama:'kama-broker-account',renko:'renko-broker'};
const ROUTES={band:'band',rsi:'ema',kama:'kama',renko:'renko'};
let accounts=[],resolveReady,rejectReady,manualRevision=0;
const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject;});
function initial(kind){
 const p=new URLSearchParams(location.search);
 return p.get(kind+'Account')||(p.get('brokerForm')===kind||kind==='renko'?p.get('brokerAccount'):null);
}
function account(kind){
 const control=['manual','handoff'].includes(kind)?document.querySelector('.view.active .order-account'):document.getElementById(IDS[kind]);
 const value=control?.value;
 const bound=control?.selectedOptions?.[0]?.dataset.savedBrokerAccount;
 const id=bound|| (value?.startsWith('dhan:')?value.slice(5):value?.startsWith('account:')?value.slice(8):kind==='renko'&&value==='DHAN'?initial(kind):control?null:initial(kind));
 return accounts.find(a=>a.id===id)||null;
}
function kind(url){const p=new URL(url,location.href).pathname;
 return p.startsWith('/api/trade-recommendation/')?'parser':(['/api/account','/api/realized-pnl','/api/live-pnl','/api/auth/status','/api/auth/start','/api/chartink/analyze','/api/chartink/analyze-options'].includes(p) )?'account':p.startsWith('/api/analysis-handoff/')?'handoff':p.startsWith('/api/sector-analysis')?'sector':p.startsWith('/api/trade-ticket/')?'manual':p.startsWith('/api/kama/')?'kama':p.startsWith('/api/ema-crossover/')?'rsi':p.startsWith('/api/ema-band/')?'band':p.startsWith('/api/renko-')?'renko':null;
}
function route(kind,url,selected){
 const u=new URL(url,location.href);if(kind==='parser'&&selected?.broker!=='FYERS')throw Error('Select a configured FYERS account for this parser.');if(!selected||u.origin!==location.origin||!u.pathname.startsWith('/api/'))return u.href;
 if(u.pathname.startsWith('/api/dhan/')||Object.values(ROUTES).some(k=>u.pathname.startsWith('/api/'+k+'-dhan/')))return u.href;
 if(kind==='handoff'&&selected.broker==='DHAN'){
  u.pathname=u.pathname.replace('/api/analysis-handoff/','/api/dhan/analysis-handoff/');
  u.searchParams.set('account_id',selected.id);return u.href;
 }
 if(kind==='account'&&selected.broker==='DHAN'){
  const paths={'/api/account':'account','/api/realized-pnl':'realized-pnl','/api/live-pnl':'live-pnl','/api/auth/status':'status'};
  if(!paths[u.pathname])throw Error('This analysis action still requires its FYERS data provider; Dhan account selection cannot redirect it.');
  u.pathname='/api/dhan/'+paths[u.pathname];u.searchParams.set('account_id',selected.id);return u.href;
 }
 if(kind==='sector'&&selected.broker==='DHAN'){
  if(!['/api/sector-analysis','/api/sector-analysis/detail'].includes(u.pathname))throw Error('Unsupported Dhan sector analysis request.');
  u.pathname=u.pathname.replace('/api/sector-analysis','/api/dhan/sector-analysis');
  u.searchParams.set('account_id',selected.id);return u.href;
 }
 if(kind==='sector'&&selected.broker!=='FYERS')throw Error('Delta India sector market data is not available. Select FYERS or Dhan for Indian sector analysis.');
 if(selected.broker==='DHAN'){
  if(kind==='manual'){u.pathname='/broker-workspace/'+selected.id+u.pathname;return u.href;}
  if(kind==='renko')return u.href;
  const base=kind==='rsi'&&u.pathname.startsWith('/api/ema-band/')?'/api/ema-band/':kind==='rsi'?'/api/ema-crossover/':kind==='band'?'/api/ema-band/':'/api/kama/';
  if(!u.pathname.startsWith(base))throw Error('Selected account cannot handle this strategy request.');
  const action=u.pathname.slice(base.length).replaceAll('/','-');
  u.pathname='/api/'+ROUTES[kind]+'-dhan/'+selected.id+'/form-'+action;
  const job=new URLSearchParams(location.search);
  if(job.get(kind+'Account')===selected.id&&job.get(kind+'Instance'))u.searchParams.set('instance',job.get(kind+'Instance'));
 }else u.pathname='/broker-workspace/'+selected.id+u.pathname;
 return u.href;
}
async function scopedFetch(key,url,options){
 if(!key)return root.fetch(url,options);
 await ready;
 let declared=null;
 if(key==='manual'){
  const query=new URL(url,location.href).searchParams;
  let body={};try{body=JSON.parse(options?.body||'{}');}catch(error){throw Error('Invalid broker request body.');}
  const ids=[body.account_id,...(body.items||[]).map(item=>item.account_id)].filter(Boolean);
  if(new Set(ids).size>1)throw Error('A batch must use one selected broker account.');
  declared=ids[0]||query.get('account_id');
 }
 const selected=declared?accounts.find(a=>a.id===declared):account(key),id=selected?.id||null,revision=manualRevision;
 if(!selected)throw Error('Select a configured broker account before using this form.');
 if(key==='handoff'&&selected.broker==='DHAN'&&options?.body){
  const body=JSON.parse(options.body);options={...options,body:JSON.stringify({...body,account_id:selected.id,broker:'DHAN'})};
 }
 const response=await root.fetch(route(key,url,selected),options);
 if(key==='manual'?manualRevision!==revision:(account(key)?.id||null)!==id)throw Error(options?.method==='POST'?'Broker account changed during an action. Check the previous account status before another action.':'Broker account changed; previous response discarded.');
 return response;
}
function setAccounts(value){accounts=value;resolveReady();}
function remember(kind,id){
 const url=new URL(location.href);
 if(id){url.searchParams.set(kind+'Account',id);if(kind!=='manual'){url.searchParams.set('brokerForm',kind);url.searchParams.set('brokerAccount',id);}}
 else{url.searchParams.delete(kind+'Account');if(url.searchParams.get('brokerForm')===kind){url.searchParams.delete('brokerForm');url.searchParams.delete('brokerAccount');}}
 history.replaceState(null,'',url);
}
function onChange(kind,selected){
 if(kind==='manual'){
  manualRevision++;
  for(const control of document.querySelectorAll('.view.active .order-account')){
   const option=[...control.options].find(o=>o.dataset.savedBrokerAccount===selected?.id&&!o.disabled);
   if(option)control.value=option.value;
  }
 }
 remember(kind,selected?.id);
 if(kind==='renko'){
  const url=new URL(location.href);url.searchParams.set('renkoBroker',selected.broker);url.searchParams.set('renkoAccount',selected.id);url.searchParams.set('brokerAccount',selected.id);url.searchParams.delete('renkoInstance');url.searchParams.delete('brokerForm');
  location.href=url.href;return;
 }
 // Existing controls stay on this screen. Read requests and activation use the new account.
 root.dispatchEvent(new CustomEvent('broker-account-change',{detail:{kind,account:selected}}));
}
function presentation(kind){
 const selected=account(kind),dhan=selected?.broker==='DHAN';
 const disable=(id,value)=>{const node=document.getElementById(id);if(!node)return;node.disabled=dhan;if(dhan&&value!==undefined){if(node.type==='checkbox')node.checked=value;else node.value=value;}node.title=dhan?'Unavailable for this Dhan route; not silently applied.':'';};
 if(kind==='band'){
  let limit=document.getElementById('ema-band-max-trades');
  if(!limit){const field=document.createElement('label');field.className='field';field.textContent='Maximum entries per run';limit=document.createElement('input');limit.id='ema-band-max-trades';limit.type='number';limit.min='1';limit.value='2';field.append(limit);document.getElementById('ema-band-lots').closest('label').after(field);}
  limit.closest('label').hidden=!dhan;
  for(const id of ['ema-band-stop-pct','ema-band-target-pct','ema-band-profit-protection-pct']){const node=document.getElementById(id);if(node){node.disabled=false;node.title='';}}
  const resistance=document.getElementById('ema-band-resistance-volume-exit');if(resistance)resistance.disabled=false;
  const session=document.getElementById('ema-band-session');
  if(dhan&&session){if(session.options&&![...session.options].some(o=>o.value==='0915-1510'))session.add(new Option('Dhan · 09:15–15:10 IST','0915-1510'));session.value='0915-1510';}
  disable('ema-band-session');
 }
 if(kind==='kama'){
  const quantity=document.getElementById('kama-quantity');if(dhan&&quantity){quantity.closest('label').hidden=false;if(!quantity.value)quantity.value='1';}
  const route=document.getElementById('kama-execution-mode');if(route){for(const o of route.options)o.disabled=dhan&&o.value!=='OPTIONS';if(dhan)route.value='OPTIONS';}
  const live=document.querySelector('#kama-mode option[value="LIVE"]');if(live)live.disabled=false;
 }
 const section=document.getElementById({band:'ema-band',rsi:'ema-cross',kama:'kama'}[kind]);if(!section)return;
 let note=section.querySelector('.broker-route-note');
 if(!note){note=document.createElement('p');note.className='broker-route-note ticket-warning';section.querySelector('.head').after(note);}
 note.textContent=selected?(selected.label+' · '+selected.broker+' · account selection does not start or stop a runner. '+(dhan?(kind==='kama'?'Bought options · Paper/Live · underlying invalidation and full-premium idea cap.':kind==='band'?'Bought options · LIMIT IOC · optional premium exits and completed-candle resistance/volume exit.':'Bought options · LIMIT IOC · confirmed RSI crossover and optional premium trailing.'):'Private account credentials and runner state.')):'Select your saved broker account.';
 for(const warning of section.querySelectorAll('.ticket-warning')){
  if(warning===note)continue;
  if(!warning.dataset.brokerOriginal)warning.dataset.brokerOriginal=warning.textContent;
  if(warning.dataset.brokerOriginal.includes('FYERS'))warning.textContent=dhan?'Dhan · bought ATM calls for bullish setups and puts for bearish setups. Marketable LIMIT IOC; fresh quotes, funds, static IP and confirmed owned quantities are required. Unavailable settings are disabled. Selecting a broker does not start, stop or transfer a position.':warning.dataset.brokerOriginal;
 }
 for(const label of section.querySelectorAll('.label,.badge,small,h3,button,option')){
  if(label.children.length||label.closest('#ema-band-broker-account,#cross-broker-account,#kama-broker-account'))continue;
  if(!label.dataset.brokerOriginal)label.dataset.brokerOriginal=label.textContent;
  if(label.dataset.brokerOriginal.includes('FYERS'))label.textContent=dhan?label.dataset.brokerOriginal.replaceAll('FYERS','Dhan'):label.dataset.brokerOriginal;
 }
}
root.addEventListener('broker-account-change',event=>presentation(event.detail.kind));
root.addEventListener('broker-accounts-ready',()=>['band','rsi','kama'].forEach(presentation));
root.BrokerForms={ready,accounts:()=>accounts.slice(),account,initial,kind,route,fetch:scopedFetch,setAccounts,onChange,fail:error=>rejectReady(error)};
if(typeof module!=='undefined')module.exports={route,kind};
})(typeof window==='undefined'?globalThis:window);
