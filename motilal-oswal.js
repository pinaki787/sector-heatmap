(function(){
'use strict';
const $=id=>document.getElementById(id);
const prefix=location.pathname.match(/^\/broker-workspace\/[a-f0-9]{32}/)?.[0]||'';
let context,busy=false;
const message=text=>{$('message').textContent=text;};
async function api(path,body){
 const response=await fetch(prefix+path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':context.csrf},body:JSON.stringify(body)});
 const value=await response.json();if(!response.ok)throw Error(value.error||'Motilal connection request failed.');return value;
}
async function run(button,task){if(busy)return;busy=true;button.disabled=true;message('');try{await task();}catch(error){message(error.message);}finally{busy=false;button.disabled=false;}}
$('connect').onclick=event=>run(event.target,async()=>{const value=await api('/api/motilal/login-start',{});location.assign(value.url);});
$('status').onclick=event=>run(event.target,async()=>{$('connection').textContent=JSON.stringify(await api('/api/motilal/status'),null,2);});
(async()=>{
 const params=new URLSearchParams(location.search),auth=params.get('authtoken');if(auth)history.replaceState(null,'',location.pathname);
 context=await api('/api/workspace-context');$('account').textContent=context.workspace.label+' · '+context.workspace.account_ref+' · '+(context.workspace.live_enabled?'Live capability enabled':'Paper / read-only');
 if(!context.visible||!context.permitted){message('Broker connection is hidden or not assigned in User Master.');return;}$('broker-panel').hidden=false;
 for(const [label,kind] of [['Renko Supertrend','renko'],['Analysis handoff','handoff'],['Screener','screener'],['Sector rotation','sector']]){
  const link=document.createElement('a');link.textContent=label;link.href='/?'+new URLSearchParams({brokerForm:kind,brokerAccount:context.workspace.id,[kind+'Account']:context.workspace.id,...(kind==='renko'?{renkoBroker:'MOTILAL_OSWAL'}:{})});$('workflow-links').append(link,document.createElement('br'));
 }
 if(auth){const result=await api('/api/motilal/login-complete',{auth_token:auth});message('Authenticated '+result.client_id+'. No order submitted.');}
 $('connection').textContent=JSON.stringify(await api('/api/motilal/status'),null,2);
})().catch(error=>message(error.message));
})();
