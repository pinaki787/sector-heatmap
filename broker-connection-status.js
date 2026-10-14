/* Selected broker status; read-only, account-bound and stale-response safe. */
(function(root){
'use strict';
let key='',version=0,last=0;
let dhanPending='';
const reauthShown=new Set();
function offerDhanReauthentication(account){
 if(reauthShown.has(account.id)||document.visibilityState==='hidden')return;
 reauthShown.add(account.id);
 const dialog=document.createElement('dialog');
 const heading=document.createElement('h3');heading.textContent='Dhan sign-in required';
 const text=document.createElement('p');text.textContent='Dhan authorization expired or is invalid for '+account.label+'. Sign in again to restore broker access. This does not start a runner or retry an order.';
 const link=document.createElement('a');link.className='button';link.textContent='Reauthenticate Dhan';link.href='/accounts?reauth_dhan='+encodeURIComponent(account.id);
 const later=document.createElement('button');later.textContent='Later';later.onclick=()=>{dialog.close();dialog.remove();};
 dialog.append(heading,text,link,later);document.body.append(dialog);dialog.showModal();
}

function selection(){
 const view=document.querySelector('.view.active')?.id;
 const kind={ sectors:'sector', handoff:'handoff',broker:'account', 'ema-band':'band','ema-cross':'rsi',kama:'kama','renko-supertrend':'renko'}[view]||(view?.includes('renko')?'renko':null);
 let account=view==='renko-engine'?root.RenkoEngine?.selectedAccount?.():kind?root.BrokerForms?.account(kind):null;
 let broker=account?.broker||'FYERS';
 if(kind==='renko'&&view!=='renko-engine')broker=document.getElementById('renko-broker')?.value||broker;
 if(view==='delta-india')broker='DELTA_INDIA';
 if(!account&&!kind&&view!=='renko-engine'){account=root.BrokerForms?.accounts?.().find(a=>a.broker===broker&&a.configured)||null;}
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
   if(!response.ok||!data.url)throw Error(data.error||'Unable to start FYERS login');
   location.assign(data.url);
  }catch(error){connect.textContent='Connect to FYERS';const panel=document.getElementById('selected-broker-connection');if(panel){panel.hidden=false;panel.textContent=error.message;}}
 };
}
async function update(){
 const card=document.querySelector('.broker-card');if(!card||!root.BrokerForms)return;
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
 if(!account){panel.textContent='Select a saved broker account';connect.hidden=false;connect.textContent='Configure broker account';return;}
 const name={DHAN:'Dhan',DELTA_INDIA:'Delta India',FYERS:'FYERS'}[broker]||broker;
 connect.textContent='Connect to '+name;if(broker==='FYERS')fyersConnect(connect,account);
 panel.textContent=name+' · Checking…';
 try{
  let message;
  if(broker==='DHAN'&&account){
   dhanPending=next;
   const controller=new AbortController();
   const timeout=setTimeout(()=>controller.abort(),12000);
   try{
    const response=await fetch('/api/dhan/status?account_id='+encodeURIComponent(account.id),{signal:controller.signal});if(!response.ok)throw Error();
    const data=await response.json();message=data.authenticated?'Connected':data.reauthentication_required?'Sign-in required':'Not connected';
    if(generation===version&&data.reauthentication_required){connect.href='/accounts?reauth_dhan='+encodeURIComponent(account.id);connect.textContent='Reauthenticate Dhan';offerDhanReauthentication(account);}
    if(data.authenticated)reauthShown.delete(account.id);
   }finally{clearTimeout(timeout);if(dhanPending===next)dhanPending='';}
  }else if(broker==='DELTA_INDIA'){
   const response=await fetch((account?'/broker-workspace/'+account.id:'')+'/api/delta-india/status');if(!response.ok)throw Error();
   const data=await response.json();if(data.credentials==='CONFIGURED'){const auth=await fetch((account?'/broker-workspace/'+account.id:'')+'/api/delta-india/verify-auth',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});message=auth.ok?'Connected':'Not connected';}else message='Not connected';
  }else{
   const response=await fetch('/broker-workspace/'+account.id+'/api/auth/status');if(!response.ok)throw Error();
   const data=await response.json();message=data.connected===true||data.authenticated===true?'Connected':'Not connected';
  }
  if(generation===version){panel.textContent=name+' · '+message;connect.hidden=message==='Connected';}
 }catch(error){if(generation===version){panel.textContent=name+(broker==='DHAN'?' · Status unavailable — retrying':' · Not connected');connect.hidden=broker==='DHAN';}}
}
root.addEventListener('broker-account-change',()=>{key='';update();});
root.addEventListener('broker-accounts-ready',update);
document.addEventListener('change',()=>{if(selection().broker!=='DHAN')key='';update();});
document.addEventListener('click',()=>queueMicrotask(update));
setInterval(update,3000);
})(window);
