(function(){
'use strict';
const $=id=>document.getElementById(id);
const prefix=location.pathname.match(/^\/broker-workspace\/[a-f0-9]{32}/)?.[0]||'';
let context,busy=false,savedLogin=false,otpPending=false,loginNeeded=false;
const message=text=>{$('message').textContent=text;};
async function api(path,body){
 const response=await fetch(prefix+path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':context.csrf},body:JSON.stringify(body)});
 const value=await response.json();if(!response.ok){const error=Error(value.error||'Motilal connection request failed.');error.authRequired=value.auth_required===true;throw error;}return value;
}
async function run(button,task){if(busy)return;busy=true;button.disabled=true;message('');try{await task();}catch(error){message(error.message);}finally{busy=false;button.disabled=false;}}
const recoveryKey='motilal-login-recovery:'+prefix;
async function connect(){
 sessionStorage.setItem(recoveryKey,String(Date.now()));
 if(savedLogin){const value=await api('/api/motilal/saved-login-start',{require_otp:new URLSearchParams(location.search).get('challenge')==='otp'});$('otp-form').hidden=!value.otp_required;message(value.otp_required?'Motilal accepted the OTP request. Enter the code when it arrives on your registered mobile/email.':value.message);if(value.authenticated)await status(false);return;}
 const value=await api('/api/motilal/login-start',{});location.assign(value.url);
}
async function savedStatus(){
 const value=await api('/api/motilal/saved-login');savedLogin=value.configured;otpPending=value.otp_required;loginNeeded=value.reauthentication_required===true;if(value.otp_required)sessionStorage.setItem(recoveryKey,String(Date.now()));
 $('saved-client').value=value.client_id;$('forget-login').hidden=!savedLogin;$('otp-form').hidden=!value.otp_required;
 for(const id of ['saved-password','saved-pan']){const field=$(id);field.value='';field.placeholder=savedLogin?'•••••••• · Saved':'Enter '+(id==='saved-pan'?'PAN':'trading password');field.disabled=savedLogin;}
 $('saved-consent').checked=savedLogin;$('saved-consent').disabled=savedLogin;
 $('save-login').hidden=savedLogin;$('edit-login').hidden=!savedLogin;
 $('saved-login-state').textContent=savedLogin?'Encrypted trading login saved. OTP stays user-entered.':'No trading login saved.';
}
$('edit-login').onclick=()=>{
 for(const id of ['saved-password','saved-pan']){const field=$(id);field.disabled=false;field.placeholder='Enter replacement '+(id==='saved-pan'?'PAN':'trading password');}
 $('saved-consent').disabled=false;$('save-login').hidden=false;$('edit-login').hidden=true;
 message('Enter both replacement credentials. Existing saved login remains until you save successfully.');
};
$('saved-login-form').onsubmit=event=>{event.preventDefault();run($('save-login'),async()=>{
 const body={client_id:$('saved-client').value,password:$('saved-password').value,pan:$('saved-pan').value,consent:$('saved-consent').checked};
 $('saved-password').value='';$('saved-pan').value='';
 try{const value=await api('/api/motilal/saved-login',body);message(value.message);await savedStatus();sessionStorage.removeItem(recoveryKey);await status();}finally{body.password='';body.pan='';}
});};
$('forget-login').onclick=event=>run(event.target,async()=>{await api('/api/motilal/saved-login-forget',{});await savedStatus();message('Saved trading login removed. Existing broker session is unchanged.');});
$('resend-otp').onclick=event=>run(event.target,async()=>{const value=await api('/api/motilal/saved-login-resend',{});$('otp-form').hidden=false;message(value.message);});
$('otp-form').onsubmit=event=>{event.preventDefault();run($('verify-otp'),async()=>{
 const otp=$('login-otp').value;$('login-otp').value='';$('otp-form').hidden=true;
 const value=await api('/api/motilal/saved-login-verify',{otp});
 if(!value.authenticated)throw Error('OTP verification did not establish a broker connection.');
 renderConnection({authenticated:true,client_id:value.client_id,live_enabled:context.workspace.live_enabled});
 message('Connected to Motilal Oswal. OTP verified successfully. No runner started or order sent.');
 try{await savedStatus();await status(false);}catch(error){message('OTP verified and broker session saved, but connection details could not refresh: '+error.message);}
});};
function renderConnection(value){
 const table=document.createElement('table');table.className='connection-table';
 const rows=[['Authentication',value.authenticated?'Connected':'Sign-in required'],['Client code',value.client_id||'Unavailable'],['Live capability',value.live_enabled?'Enabled':'Disabled'],['Enabled segments',(value.exchanges||[]).join(', ')||'Unavailable'],['Supported products',(value.products||[]).join(', ')||'Unavailable'],['Data feed',value.feed_connected?'Connected':'Not connected'],['Session expires',value.session_expires_at?new Date(value.session_expires_at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'})+' IST':'Unavailable']];
 for(const [label,text] of rows){const row=document.createElement('tr'),heading=document.createElement('th'),cell=document.createElement('td');heading.scope='row';heading.textContent=label;cell.textContent=text;row.append(heading,cell);table.append(row);}
 $('connection').textContent='';$('connection').append(table);
}
async function status(allowRecovery=true){
 try{const value=await api('/api/motilal/status');renderConnection(value);if(value.authenticated)sessionStorage.removeItem(recoveryKey);}
 catch(error){
  if(!error.authRequired||!allowRecovery)throw error;
  message('Motilal session expired. Opening broker sign-in; no runner or order will be restarted.');
  const previous=Number(sessionStorage.getItem(recoveryKey)||0);
  if(previous&&Date.now()-previous<600000){message('Motilal sign-in is still required. Use Connect to retry; automatic redirects are paused.');return;}
  await connect();
 }
}
$('connect').onclick=event=>run(event.target,connect);
$('status').onclick=event=>run(event.target,()=>status());
(async()=>{
 const params=new URLSearchParams(location.search),auth=params.get('authtoken');if(auth)history.replaceState(null,'',location.pathname);
 context=await api('/api/workspace-context');$('account').textContent=context.workspace.label+' · '+context.workspace.account_ref+' · '+(context.workspace.live_enabled?'Live capability enabled':'Paper / read-only');
 if(!context.visible||!context.permitted){message('Broker connection is hidden or not assigned in User Master.');return;}$('broker-panel').hidden=false;
 for(const [label,kind] of [['Renko Supertrend','renko'],['Analysis handoff','handoff'],['Screener','screener'],['Sector rotation','sector']]){
  const link=document.createElement('a');link.textContent=label;link.href='/?'+new URLSearchParams({brokerForm:kind,brokerAccount:context.workspace.id,[kind+'Account']:context.workspace.id,...(kind==='renko'?{renkoBroker:'MOTILAL_OSWAL'}:{})});$('workflow-links').append(link,document.createElement('br'));
 }
 if(auth){const result=await api('/api/motilal/login-complete',{auth_token:auth});message('Authenticated '+result.client_id+'. No order submitted.');}
 await savedStatus();
 if(otpPending){renderConnection({authenticated:false,client_id:context.workspace.account_ref,live_enabled:context.workspace.live_enabled});message('A fresh OTP challenge is pending. Enter the code from your registered mobile/email.');}
 else if(loginNeeded&&savedLogin){renderConnection({authenticated:false,client_id:context.workspace.account_ref,live_enabled:context.workspace.live_enabled});await connect();}
 else await status(!auth);
})().catch(error=>message(error.message));
})();
