/* Selected broker status; read-only, account-bound and stale-response safe. */
(function(root){
'use strict';
function connectionSelection({workspace,accounts=[],selectedAccount=null,selectedBroker='FYERS'}={}){
 if(workspace?.id&&workspace.broker){
  const account=accounts.find(a=>a.id===workspace.id)||workspace;
  return {account:account.broker===workspace.broker?account:null,broker:workspace.broker};
 }
 return {account:selectedAccount,broker:selectedAccount?.broker||selectedBroker};
}
if(typeof window==='undefined'&&typeof module!=='undefined'&&module.exports){module.exports={connectionSelection};return;}
let key='',version=0,last=0,connectionContext=null,contextRequest=null;
let dhanPending='',lastSelectedAccountId='';
const reauthShown=new Set();
function promptKey(account){
 const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 return 'sector-pulse:reauth:'+account.id+':'+day;
}
function alreadyPrompted(account){
 const id=promptKey(account);
 try{return reauthShown.has(id)||root.sessionStorage.getItem(id)==='shown';}catch{return reauthShown.has(id);}
}
function clearPrompt(account){
 const id=promptKey(account);reauthShown.delete(id);
 try{root.sessionStorage.removeItem(id);}catch{}
 for(const dialog of document.querySelectorAll('dialog[data-broker-reauth]')){if(dialog.dataset.brokerReauth===account.id){if(dialog.open&&typeof dialog.close==='function')dialog.close();dialog.remove();}}
}
function offerReauthentication(account,broker){
 if(document.querySelector('#sp-chart-workspace[open], #chart-workspace.view.active'))return;
 if(alreadyPrompted(account)||document.visibilityState==='hidden')return;
 const id=promptKey(account);reauthShown.add(id);
 try{root.sessionStorage.setItem(id,'shown');}catch{}
 const name=broker==='FYERS'?'FYERS':'Dhan';
 const dialog=document.createElement('dialog');dialog.dataset.brokerReauth=account.id;
 const heading=document.createElement('h3');heading.textContent=name+' sign-in required';
 const text=document.createElement('p');text.textContent='The latest saved authorization for '+account.label+' was rejected by '+name+'. Sign in once to restore access across this account’s sections.';
 const link=document.createElement('a');link.className='button';link.textContent='Reauthenticate '+name;
 if(broker==='FYERS')fyersConnect(link,account);
 else link.href='/accounts?reauth_dhan='+encodeURIComponent(account.id);
 const later=document.createElement('button');later.textContent='Later';later.onclick=()=>{dialog.close();dialog.remove();};
 dialog.append(heading,text,link,later);document.body.append(dialog);dialog.showModal();
}

function selection(){
 const context=root.BrokerForms?.context?.()||root.SectorPulseWorkspace||connectionContext;
 const params=new URLSearchParams(location.search);
 const view=document.querySelector('.view.active')?.id;
 const accounts=root.BrokerForms?.accounts?.()||context?.accounts||[];
 const chartSource=view==='chart-workspace'?params.get('chartSource'):null;
 if(chartSource==='yahoo')return {account:null,broker:'YAHOO'};
 const sharedId=chartSource||params.get('brokerAccount')||context?.workspace?.id;
 if(sharedId){
  const account=accounts.find(a=>a.id===sharedId)||(context?.workspace?.id===sharedId?context.workspace:null);
  return {account,broker:account?.broker||'UNKNOWN'};
 }
 if(context?.workspace?.id)return connectionSelection({workspace:context.workspace,accounts:root.BrokerForms?.accounts?.()||[]});
 const kind={ holdings:'holdings', 'trade-parser':'parser',sectors:'sector', handoff:'handoff',broker:'account',screener:'screener', 'ema-band':'band','ema-cross':'rsi',kama:'kama','renko-supertrend':'renko'}[view]||(view?.includes('renko')?'renko':null);
 let account=view==='renko-engine'?root.RenkoEngine?.selectedAccount?.():kind?root.BrokerForms?.account(kind):null;
 let broker=account?.broker||'FYERS';
 if(kind==='renko'&&view!=='renko-engine')broker=document.getElementById('renko-broker')?.value||broker;
 if(view==='delta-india')broker='DELTA_INDIA';
 if(!account&&!kind&&view!=='renko-engine'){
  const owned=accounts;
  account=owned.find(a=>a.id===lastSelectedAccountId&&a.configured)||owned.find(a=>a.configured)||null;
  broker=account?.broker||broker;
 }
 if(account)lastSelectedAccountId=account.id;
 if(broker.startsWith('account:'))broker=account?.broker||'UNKNOWN';
 return {account,broker};
}
function fyersConnect(connect,account){
 const scoped=location.pathname.match(/^\/broker-workspace\/([a-f0-9]{32})\//);
 const id=account?.id||scoped?.[1];
 if(!id)return;
 connect.href='/broker-workspace/'+id+'/api/auth/start';
 connect.onclick=async event=>{
  event.preventDefault();connect.textContent='Connecting to FYERS…';
  try{
   const response=await fetch('/broker-workspace/'+id+'/api/auth/start');
   const data=await response.json();
   if(response.ok&&data.authenticated===true){
    const status=document.getElementById('selected-broker-connection');
    if(status)status.textContent='FYERS · Connected';
    connect.hidden=true;connect.textContent='Connect to FYERS';
    return;
   }
   if(!response.ok||!data.url)throw Error(data.error||'Unable to start FYERS login');
   location.assign(data.url);
  }catch(error){connect.textContent='Connect to FYERS';const panel=document.getElementById('selected-broker-connection');if(panel){panel.hidden=false;panel.textContent=error.message;}}
 };
}
async function update(){
 const card=document.querySelector('.broker-card');if(!card)return;
 if(!root.BrokerForms?.context?.()&&!root.SectorPulseWorkspace&&!connectionContext){
  contextRequest=contextRequest||fetch('/api/workspace-context',{cache:'no-store'}).then(async r=>{if(!r.ok)throw Error('Workspace identity unavailable');return r.json();}).finally(()=>{contextRequest=null;});
  try{connectionContext=await contextRequest;}catch(error){return;}
 }
 const {account,broker}=selection(),next=broker+'|'+(account?.id||'');
 if(broker==='DHAN'&&dhanPending===next)return;
 if(next===key&&Date.now()-last<30000)return;key=next;last=Date.now();const generation=++version;
 const legacy=false;
 const state=document.getElementById('broker-state')?.closest('b'),refresh=document.getElementById('reauth'),label=card.querySelector('.label');
 const help=document.getElementById('reauth-help');if(help)help.hidden=true;
 if(!document.getElementById('broker-status-hidden-style')){const style=document.createElement('style');style.id='broker-status-hidden-style';style.textContent='.broker-card{display:flex!important;flex-direction:column!important;align-items:stretch!important;height:auto!important;min-width:0;gap:8px!important}.broker-card .label,.broker-card #selected-broker-connection,.broker-card #selected-broker-connect{position:static!important;width:auto!important;max-width:100%;height:auto!important;min-height:0;white-space:normal!important;overflow-wrap:anywhere;line-height:1.45!important;margin:0!important;box-sizing:border-box}.broker-card #selected-broker-connect{display:block;padding:9px 12px;text-align:center}.broker-card > b[role=status],.broker-card [hidden],.broker-card #configured-broker-accounts,.broker-card #reauth,.broker-card #reauth-help{display:none!important}';document.head.append(style);}
 const inventory=document.getElementById('configured-broker-accounts');if(inventory)inventory.hidden=true;
 if(state)state.hidden=!legacy;if(refresh)refresh.hidden=true;if(label)label.textContent='BROKER CONNECTION';
 let panel=document.getElementById('selected-broker-connection');
 if(!panel){panel=document.createElement('div');panel.id='selected-broker-connection';panel.setAttribute('role','status');panel.style.cssText='display:grid;gap:6px;margin:8px 0';card.insertBefore(panel,document.getElementById('configured-broker-accounts'));}
 let connect=document.getElementById('selected-broker-connect');if(!connect){connect=document.createElement('a');connect.id='selected-broker-connect';connect.className='button';connect.textContent='Connect';panel.after(connect);}connect.hidden=true;connect.href='/accounts';connect.onclick=null;
 panel.hidden=false;
 if(broker==='YAHOO'){panel.textContent='Yahoo Finance · Historical data';return;}
 if(!account){
  const owned=root.BrokerForms?.accounts?.()||connectionContext?.accounts||[];
  panel.textContent=owned.length?'Select a saved broker account':'Loading broker accounts…';
  return;
 }
 if(account.configured===false){
  panel.textContent='Broker account setup is incomplete';connect.hidden=false;connect.textContent='Configure broker account';return;
 }
 const name={DHAN:'Dhan',DELTA_INDIA:'Delta India',FYERS:'FYERS',MOTILAL_OSWAL:'Motilal Oswal'}[broker]||broker;
 connect.textContent='Connect to '+name;if(broker==='FYERS')fyersConnect(connect,account);
 panel.textContent=name+' · Checking…';
 try{
  let message;
  if(broker==='MOTILAL_OSWAL'){
   connect.href='/broker-workspace/'+account.id+'/workspace-entry';
   const response=await fetch('/api/motilal/status?account_id='+encodeURIComponent(account.id),{cache:'no-store'});if(!response.ok)throw Error('Native connection unavailable');
   const data=await response.json();message=data.authenticated?'Connected':'Sign-in required';
  }else if(broker==='DHAN'&&account){
   dhanPending=next;
   const controller=new AbortController();
   const timeout=setTimeout(()=>controller.abort(),12000);
   try{
    const response=await fetch('/api/dhan/status?account_id='+encodeURIComponent(account.id),{signal:controller.signal});if(!response.ok)throw Error();
    const data=await response.json();message=data.authenticated?'Connected':data.reauthentication_required?'Sign-in required':'Not connected';
    if(generation===version&&data.reauthentication_required){connect.href='/accounts?reauth_dhan='+encodeURIComponent(account.id);connect.textContent='Reauthenticate Dhan';offerReauthentication(account,broker);}
    if(data.authenticated)clearPrompt(account);
   }finally{clearTimeout(timeout);if(dhanPending===next)dhanPending='';}
  }else if(broker==='DELTA_INDIA'){
   const response=await fetch((account?'/broker-workspace/'+account.id:'')+'/api/delta-india/status');if(!response.ok)throw Error();
   const data=await response.json();if(data.credentials==='CONFIGURED'){const auth=await fetch((account?'/broker-workspace/'+account.id:'')+'/api/delta-india/verify-auth',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});message=auth.ok?'Connected':'Not connected';}else message='Not connected';
  }else{
   const response=await fetch('/broker-workspace/'+account.id+'/api/auth/status');if(!response.ok)throw Error();
   const data=await response.json();
   if(generation===version&&data.reauthentication_required===true)offerReauthentication(account,broker);
   if(data.authenticated===true)clearPrompt(account);
   message=data.connected===true||data.authenticated===true?'Connected'
    :data.reauthentication_required===true||String(data.message).includes('no current access token')?'Sign-in required'
    :'Status unavailable — retrying';
  }
  if(generation===version){panel.textContent=name+' · '+message;connect.hidden=message==='Connected'||message.startsWith('Status unavailable');}
 }catch(error){if(generation===version){panel.textContent=name+' · Status unavailable — retrying';connect.hidden=true;}}
}
root.addEventListener('broker-account-change',()=>{key='';update();});
root.addEventListener('broker-accounts-ready',()=>{key='';update();});
root.addEventListener('chart-source-change',()=>{key='';update();});
document.addEventListener('change',()=>{if(selection().broker!=='DHAN')key='';update();});
document.addEventListener('click',()=>queueMicrotask(update));
update();
setInterval(update,3000);
})(typeof window==='undefined'?globalThis:window);
