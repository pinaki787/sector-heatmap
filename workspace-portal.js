/* Read-only validation of the selected user's saved broker credentials. */
(function(root){
'use strict';
async function testConnection(account,request){
 if(!account?.id||!['FYERS','DHAN','DELTA_INDIA','MOTILAL_OSWAL'].includes(account.broker))throw Error('Select a saved broker account.');
 const prefix='/broker-workspace/'+encodeURIComponent(account.id);
 const url=account.broker==='DHAN'?'/api/dhan/status?account_id='+encodeURIComponent(account.id):prefix+(account.broker==='MOTILAL_OSWAL'?'/api/motilal/status':account.broker==='FYERS'?'/api/account':'/api/delta-india/verify-auth');
 const response=await request(url,account.broker==='DELTA_INDIA'?{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}:{cache:'no-store'});
 const data=await response.json();
 if(!response.ok)throw Error(String(data.error||data.message||'Broker rejected the connection test.').replace(' Do not retry an uncertain order submission.',''));
 const connected=account.broker==='FYERS'?data.connected===true:account.broker==='DHAN'?data.authenticated===true:data.authenticated===true||data.authentication==='VERIFIED_READ_ONLY';
 if(!connected)throw Error(data.error||data.message||'Authentication not confirmed. Complete broker login or renew the saved credentials.');
 return {connected:true};
}
root.testBrokerConnection=account=>testConnection(account,root.fetch.bind(root));
if(typeof module!=='undefined')module.exports=testConnection;
})(typeof window==='undefined'?globalThis:window);

'use strict';
let currentUser = null, currentAccount = null;
const $ = id => document.getElementById(id);
function updateAccountLabelHint() {
  const form = $('add-account');
  const broker = form.elements.namedItem('broker').value;
  form.elements.namedItem('label').placeholder = 'Personal · ' + ({FYERS: 'FYERS', DHAN: 'Dhan', MOTILAL_OSWAL: 'Motilal Oswal', DELTA_INDIA: 'Delta India'}[broker] || 'Broker');
}
$('add-account').elements.namedItem('broker').addEventListener('change', updateAccountLabelHint);
updateAccountLabelHint();
function message(text) { $('message').textContent = text; }
async function api(path, data) {
  const response = await fetch('/api/workspaces/' + path, data === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': currentUser?.csrf || ''}, body: JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed.');
  return result;
}
async function refresh() {
  currentUser = await api('me');
  $('signin').hidden = true; $('workspace').hidden = false;
  $('user').textContent = currentUser.username + (currentUser.admin ? ' · ADMINISTRATOR' : '');
  $('admin').hidden = !currentUser.admin;
  $('user-master-link').hidden = !currentUser.admin;
  $('owner-dashboard-link').hidden = false;
  try {
    const ref=new URL(document.referrer||location.origin);
    const valid=u=>u.origin===location.origin&&(u.pathname==='/'||/^\/broker-workspace\/[a-f0-9]{32}\/$/.test(u.pathname));
    const storageKey='sector-dashboard-return:'+currentUser.username;
    if(document.referrer&&valid(ref))sessionStorage.setItem(storageKey,ref.pathname+ref.search+ref.hash);
    const back=new URL(sessionStorage.getItem(storageKey)||'/',location.origin);
    $('owner-dashboard-link').href=valid(back)?back.pathname+back.search+back.hash:'/';
  } catch { $('owner-dashboard-link').href='/'; }
  $('user-list').replaceChildren();
  if(currentUser.admin){
    const {users,sections}=await api('users');
    const sidebar=await api('sidebar-visibility');$('sidebar-choices').replaceChildren();
    for(const [key,value] of Object.entries(sidebar)){const label=document.createElement('label');label.className='permission-option';const check=document.createElement('input');check.type='checkbox';check.name=key;check.checked=value;label.append(check,document.createTextNode(sections[key]||({'renko-engine':'Renko Engine','broker-connection':'Broker connection'})[key]||key));$('sidebar-choices').append(label);}

    const visibility=await api('renko-visibility');for(const [key,value] of Object.entries(visibility))$('renko-visibility').elements.namedItem(key).checked=value;
    const table=document.createElement('table');table.className='user-table';
    const head=table.createTHead().insertRow();for(const name of ['Username','Role']){const th=document.createElement('th');th.textContent=name;head.append(th);}
    head.append(Object.assign(document.createElement('th'),{textContent:'Visible sections'}));
    const body=table.createTBody();for(const user of users){
      const row=body.insertRow();row.insertCell().textContent=user.username;row.insertCell().textContent=user.admin?'Administrator':'User';
      const cell=row.insertCell();cell.className='user-permissions';if(user.admin){cell.textContent='All sections';continue;}
      const assigned=new Set(user.features);const controls=[];const choices=document.createElement('div');choices.className='permission-grid';cell.append(choices);
      for(const [key,name] of Object.entries(sections)){const label=document.createElement('label');label.className='permission-option';const check=document.createElement('input');check.type='checkbox';check.checked=assigned.has(key);check.value=key;label.append(check,document.createTextNode(name));choices.append(label);controls.push(check);}
      const save=document.createElement('button');save.type='button';save.textContent='Save sections';save.className='permission-save';save.onclick=async()=>{save.disabled=true;try{await api('user-sections',{username:user.username,features:controls.filter(c=>c.checked).map(c=>c.value)});message('Sections saved for '+user.username+'.');}catch(e){message(e.message);}finally{save.disabled=false;}};cell.append(save);
    }
    $('user-list').append(table);
    if(location.pathname==='/user-master')$('admin').scrollIntoView({block:'start'});
  }
  const {accounts} = await api('accounts');
  $('accounts').replaceChildren();
  if (!accounts.length) {
    const p = document.createElement('p'); p.textContent = 'No broker accounts yet. Add your first account below.'; $('accounts').append(p);
  }
  for (const account of accounts) {
    const section = document.createElement('section'); section.className = 'panel account'; section.dataset.broker = account.broker;
    const detail = document.createElement('div'), title = document.createElement('strong'), meta = document.createElement('small');
    title.textContent = account.label;
    meta.textContent = `${({FYERS:'FYERS',DHAN:'Dhan',MOTILAL_OSWAL:'Motilal Oswal',DELTA_INDIA:'Delta India'})[account.broker]} · ${account.account_ref} · ${account.configured ? 'Connection saved' : 'Connection needed'} · ${account.live_enabled ? 'Live capability enabled' : 'Paper / read-only'} · ${account.running ? 'Dashboard process running' + (account.dashboard_pid ? ' · PID ' + account.dashboard_pid : '') : 'Dashboard stopped'}`;
    detail.append(title, meta);
    const actions = document.createElement('div'); actions.className = 'actions';
    const configure = document.createElement('button'); configure.type = 'button'; configure.className = 'quiet'; configure.textContent = 'Connection settings'; configure.disabled = false;
    configure.onclick = () => edit(account);
    const open = document.createElement('button'); open.type = 'button'; open.textContent = 'Open dashboard';
    open.onclick = async () => {
      if (account.broker === 'DHAN') {
        window.open('/?brokerForm=rsi&brokerAccount=' + encodeURIComponent(account.id), '_blank', 'noopener');
        return;
      }
      open.disabled = true; message('Opening ' + account.label + '…');
      // Open during the user gesture, before awaiting the server, to avoid popup blocking.
      const tab = window.open('about:blank', '_blank');
      if (tab) tab.opener = null;
      try {
        const result = await api('open', {account_id: account.id});
        if (result.status === 'STARTING') { if (tab) tab.close(); await refresh(); message('Dashboard is still initializing. Wait a few seconds, then open it from the account row.'); return; }
        if (result.status === 'FAILED') throw new Error('Dashboard did not start. Review its local log.');
        // The dashboard may need a few seconds to initialize data services.
        if (tab) tab.location.href = '/broker-workspace/' + encodeURIComponent(account.id) + '/workspace-entry';
        message('Dashboard launching. Its strategy runners require their own deliberate Start.');
        await refresh();
      } catch (e) { if (tab) tab.close(); message(e.message); }
      finally { open.disabled = false; }
    };
    const test=document.createElement('button');test.type='button';test.className='quiet';test.textContent='Test Connection';test.disabled=!account.configured;
    const result=document.createElement('p');result.setAttribute('role','status');
    test.onclick=()=>runConnectionTest(account,test,result);
    if(currentUser?.account_disconnect){
      const disconnect=document.createElement('button');disconnect.type='button';disconnect.className='quiet';
      disconnect.textContent=account.disconnected?'Reconnect':'Disconnect';
      disconnect.onclick=async()=>{
        disconnect.disabled=true;
        try{
          await api(account.disconnected?'reconnect':'disconnect',{account_id:account.id});
          if(account.broker==='DHAN')sessionStorage.removeItem('dhan-login-account');
          result.textContent='';
          await refresh();
          if(account.disconnected){edit(account);message('Reconnect enabled. Authorize or test the saved broker connection.');}
          else message('Disconnected. Temporary account login data cleared; saved keys and strategy records retained.');
        }catch(error){result.textContent=error.message;}
        finally{disconnect.disabled=false;}
      };
      actions.append(disconnect);
      if(account.disconnected){test.disabled=true;open.disabled=true;result.textContent='Disconnected';}
    }
    if (currentUser.admin) {
      const restart = document.createElement('a');
      restart.className = 'quiet';restart.href='/?serverResources=1';
      restart.textContent='Restart in Server resources';
      actions.append(restart);
    }
    actions.prepend(configure, test, open);result.className='account-status';section.append(detail, actions, result); $('accounts').append(section);
  }
}
async function runConnectionTest(account,button,result){
 button.disabled=true;result.textContent='Testing saved connection…';
 try{await window.testBrokerConnection(account);result.textContent=account.broker.replace('DELTA_INDIA','Delta India')+' · Connected · verified '+new Date().toLocaleTimeString();}
 catch(error){result.textContent='Not connected · '+error.message;}
 finally{button.disabled=false;}
}
$('test-connection').onclick=()=>runConnectionTest(currentAccount,$('test-connection'),$('connection-test-result'));
function edit(account) {
 if(account.broker==='MOTILAL_OSWAL'){
  currentAccount=account;$('configuration').hidden=false;
  if($('connection-name-controls'))$('connection-name-controls').hidden=true;
  if($('dhan-api-fields'))$('dhan-api-fields').hidden=true;
  $('configuration-title').textContent='Connect '+account.label;
  $('callback').textContent='Client code: '+account.account_ref+'. Register this redirect URL in your Motilal API application: '+(location.protocol==='https:'?location.origin+'/broker-workspace/'+account.id+'/workspace-entry':'http://127.0.0.1:'+account.port+'/workspace-entry')+'. Save API credentials, open this account dashboard and connect to Motilal. Register server static IP '+(account.server_public_ip||'(shown after saving)')+' in the broker portal before Live orders.';
  $('key-label').firstChild.textContent='Motilal API key';$('secret-label').firstChild.textContent='Motilal API secret';
  $('credential-key').value=account.credential_key||'';$('credential-key').required=!account.configured;
  $('credential-secret').value='';$('credential-secret').required=!account.configured;$('credential-secret').placeholder=account.configured?'Saved securely · leave blank to keep':'Enter API secret';
  if($('redirect-label'))$('redirect-label').hidden=true;
  if($('credential-redirect'))$('credential-redirect').required=false;
  $('live-enabled').checked=!!account.live_enabled;
  for(const id of ['credential-key','credential-secret','live-enabled'])$(id).disabled=!!account.running;
  $('test-connection').disabled=!account.running;
  $('connection-test-result').textContent='Open the dashboard and complete Motilal login before testing.';
  $('configuration').scrollIntoView({behavior:'smooth',block:'start'});return;
 }

 $('connection-test-result').textContent='Tests saved credentials. Save any changes first.';
 $('test-connection').disabled=!account.configured;
  currentAccount = account; $('connection-name-controls').hidden=!currentUser?.account_rename; $('connection-name').value=account.label; $('configuration').hidden = false;
  $('dhan-api-fields').hidden=account.broker!=='DHAN'||!currentUser?.dhan_api_login;
  $('dhan-api-key').value=account.dhan_api_key||'';$('dhan-api-secret').value='';
  $('dhan-api-secret').placeholder=account.dhan_api_secret_saved?'Saved securely · leave blank to keep':'Enter API secret';
  $('dhan-redirect-hint').textContent='Dhan client ID must be '+account.account_ref+'. Register this Redirect URL in your Dhan API application: '+location.origin+'/accounts';
  $('dhan-connect').disabled=!account.configured;
  $('dhan-api-key').disabled=!!account.running;$('dhan-api-secret').disabled=!!account.running;
  $('configuration-title').textContent = 'Connect ' + account.label;
  $('callback').textContent = account.broker === 'FYERS' ? `Register the exact FYERS Redirect URL shown below in your FYERS application. Complete browser login inside this account’s dashboard after saving.` : account.broker === 'DHAN' ? 'Enter your Dhan client ID and API key/secret for browser login, or use a manually generated access token. The client ID must match this account. Whitelist this server IP before live execution.' : 'Use your Delta India application key and secret. Configure its allowed IP and permissions in Delta.';
  $('key-label').firstChild.textContent = account.broker === 'FYERS' ? 'FYERS client ID (App ID)' : account.broker === 'DHAN' ? 'Dhan client ID' : 'India API key';
  $('secret-label').firstChild.textContent = account.broker === 'FYERS' ? 'FYERS secret key' : account.broker === 'DHAN' ? 'Dhan access token (optional with API key login)' : 'India API secret';
  $('credential-key').value = account.credential_key || (account.broker==='DHAN'?account.account_ref:''); $('credential-key').required = !account.configured;
  $('credential-secret').value = ''; $('credential-secret').placeholder=account.secret_saved?'Saved securely · leave blank to keep':'Enter credential'; $('credential-secret').required = !account.configured && !(account.broker === 'DHAN' && currentUser?.dhan_api_login);
  $('redirect-label').hidden = account.broker !== 'FYERS';
  $('credential-redirect').required = account.broker === 'FYERS';
  $('credential-redirect').value = account.broker === 'FYERS' ? (account.redirect_uri || (location.protocol==='https:'?location.origin+'/broker-workspace/'+account.id+'/callback':'http://127.0.0.1:'+account.port+'/callback')) : '';
  $('live-enabled').checked = !!account.live_enabled;
  for(const id of ['credential-key','credential-secret','live-enabled'])$(id).disabled=!!account.running;
  $('configuration').scrollIntoView({behavior: 'smooth', block: 'start'});
}
function bind(form, task) {
  $(form).onsubmit = async event => {
    event.preventDefault(); const button = event.submitter; button.disabled = true; message('');
    try { await task(new FormData(event.target)); }
    catch (e) { message(e.message); }
    finally { button.disabled = false; }
  };
}
bind('login', async data => { currentUser = await api('login', Object.fromEntries(data)); $('login').reset(); await refresh(); });
bind('add-account', async data => { await api('accounts', Object.fromEntries(data)); $('add-account').reset(); updateAccountLabelHint(); await refresh(); message('Workspace created. Save its connection settings before broker login.'); });
bind('sidebar-visibility',async()=>{const settings=Object.fromEntries([...$('sidebar-choices').querySelectorAll('input')].map(c=>[c.name,c.checked]));await api('sidebar-visibility',{settings});message('Sidebar visibility saved for everyone, including administrators. Refresh their dashboards to apply. Runners are unchanged.');});
bind('renko-visibility', async () => {
  const settings=Object.fromEntries(['entry_rules','exit_rules','settings'].map(key=>[key,$('renko-visibility').elements.namedItem(key).checked]));
  await api('renko-visibility',{settings});
  message('Global Renko visibility saved for all regular users. Existing runners are unchanged.');
});
bind('add-user', async data => { await api('users', Object.fromEntries(data)); $('add-user').reset(); await refresh(); message('User created. They can sign in and add their own broker accounts.'); });
bind('change-password', async data => {
  await api('password', Object.fromEntries(data)); $('change-password').reset(); currentUser = null;
  $('accounts').replaceChildren(); $('workspace').hidden = true; $('signin').hidden = false;
  message('Password updated. All your sessions were signed out. Background strategies continue their existing lifecycle.');
});
async function saveAccountCredentials(){
  const credentials = currentAccount.broker === 'MOTILAL_OSWAL' ? {MO_CLIENT_ID:currentAccount.account_ref,MO_API_KEY:$('credential-key').value,MO_API_SECRET:$('credential-secret').value} : currentAccount.broker === 'FYERS' ? {FYERS_APP_ID: $('credential-key').value, FYERS_SECRET_KEY: $('credential-secret').value, FYERS_REDIRECT_URI: $('credential-redirect').value} : currentAccount.broker === 'DHAN' ? {DHAN_CLIENT_ID: $('credential-key').value, DHAN_ACCESS_TOKEN: $('credential-secret').value, ...(currentUser?.dhan_api_login?{DHAN_API_KEY:$('dhan-api-key').value,DHAN_API_SECRET:$('dhan-api-secret').value}:{})} : {DELTA_INDIA_API_KEY: $('credential-key').value, DELTA_INDIA_API_SECRET: $('credential-secret').value};
  await api('configure', {account_id: currentAccount.id, credentials, live_enabled: $('live-enabled').checked});
}
bind('configure', async () => {
  await saveAccountCredentials();
  const savedId=currentAccount.id;
  await refresh();
  const saved=(await api('accounts')).accounts.find(a=>a.id===savedId);
  if(saved)edit(saved);
  message('Connection saved privately. Saved identifiers remain visible; secrets are stored securely. For Dhan, click Connect to Dhan to authorize.');
});
$('cancel-config').onclick = () => { $('configure').reset(); $('configuration').hidden = true; currentAccount = null; };
$('logout').onclick = async () => {
  try { await api('logout', {}); currentUser = null; currentAccount = null; $('accounts').replaceChildren(); $('workspace').hidden = true; $('configuration').hidden = true; $('signin').hidden = false; message('Signed out. This does not stop any existing background strategy.'); }
  catch (e) { message(e.message); }
};
$('dhan-connect').onclick=async()=>{
 const button=$('dhan-connect');button.disabled=true;
 try{
  if($('credential-key').value.trim()!==currentAccount.account_ref)throw Error('Dhan client ID must match this saved account: '+currentAccount.account_ref+'. Correct the client ID before connecting.');
  if(!currentAccount.running)await saveAccountCredentials();
  const result=await api('dhan-login-start',{account_id:currentAccount.id});
  sessionStorage.setItem('dhan-login-account',currentAccount.id);
  location.assign(result.url);
 }catch(e){message(e.message);button.disabled=false;}
};
async function completeDhanLogin(){
 const token=new URLSearchParams(location.search).get('tokenId');
 if(!token)return;
 const aid=sessionStorage.getItem('dhan-login-account');
 history.replaceState(null,'',location.pathname);
 if(!aid)throw Error('Dhan callback has no pending account. Open account setup and connect again.');
 const result=await api('dhan-login-complete',{account_id:aid,token_id:token});
 sessionStorage.removeItem('dhan-login-account');
 message('Dhan authentication completed. Token saved privately for your account'+(result.expiry?' · expires '+result.expiry:'')+'. Use Test Connection to verify API access.');
 await refresh();
}
refresh().then(async()=>{await completeDhanLogin().catch(e=>message(e.message));const aid=new URLSearchParams(location.search).get('reauth_dhan');if(aid){const {accounts}=await api('accounts');const account=accounts.find(a=>a.id===aid&&a.broker==='DHAN');if(!account)throw Error('Select your own saved Dhan account.');edit(account);$('dhan-connect').click();}}).catch(() => { currentUser = null; $('signin').hidden = false; $('workspace').hidden = true; });

$('save-connection-name').onclick=async()=>{
 const button=$('save-connection-name');button.disabled=true;
 try{
  const saved=await api('rename',{account_id:currentAccount.id,label:$('connection-name').value});
  currentAccount.label=saved.label;$('connection-name').value=saved.label;
  $('configuration-title').textContent='Connect '+saved.label;
  await refresh();message('Display name saved. Credentials and runners are unchanged.');
 }catch(error){message(error.message);}
 finally{button.disabled=false;}
};
