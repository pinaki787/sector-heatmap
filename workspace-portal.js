'use strict';
let currentUser = null, currentAccount = null;
const $ = id => document.getElementById(id);
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
  $('owner-dashboard-link').hidden = !currentUser.admin;
  $('user-list').replaceChildren();
  if(currentUser.admin){
    const {users,sections}=await api('users');
    const table=document.createElement('table');table.style.width='100%';
    const head=table.createTHead().insertRow();for(const name of ['Username','Role']){const th=document.createElement('th');th.textContent=name;head.append(th);}
    head.append(Object.assign(document.createElement('th'),{textContent:'Visible sections'}));
    head.append(Object.assign(document.createElement('th'),{textContent:'Password'}));
    const body=table.createTBody();for(const user of users){
      const row=body.insertRow();row.insertCell().textContent=user.username;row.insertCell().textContent=user.admin?'Administrator':'User';
      const cell=row.insertCell();
      const passwordCell=row.insertCell(), reset=document.createElement('button');
      reset.type='button';reset.textContent='Reset password';
      reset.onclick=()=>{
        $('reset-user-password').reset();$('reset-username').value=user.username;
        $('reset-password-panel').hidden=false;$('reset-new-password').focus();
      };
      passwordCell.append(reset);
      if(user.admin){cell.textContent='All sections';continue;}
      const assigned=new Set(user.features);const controls=[];
      for(const [key,name] of Object.entries(sections)){const label=document.createElement('label');label.style.display='inline-flex';label.style.gap='6px';label.style.margin='6px 14px 6px 0';const check=document.createElement('input');check.type='checkbox';check.checked=assigned.has(key);check.value=key;label.append(check,document.createTextNode(name));cell.append(label);controls.push(check);}
      const save=document.createElement('button');save.type='button';save.textContent='Save sections';save.onclick=async()=>{save.disabled=true;try{await api('user-sections',{username:user.username,features:controls.filter(c=>c.checked).map(c=>c.value)});message('Sections saved for '+user.username+'.');}catch(e){message(e.message);}finally{save.disabled=false;}};cell.append(save);
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
    meta.textContent = `${account.broker === 'FYERS' ? 'FYERS' : 'Delta India'} · ${account.account_ref} · ${account.configured ? 'Connection saved' : 'Connection needed'} · ${account.live_enabled ? 'Live capability enabled' : 'Paper / read-only'} · ${account.running ? 'Dashboard process running' + (account.dashboard_pid ? ' · PID ' + account.dashboard_pid : '') : 'Dashboard stopped'}`;
    detail.append(title, meta);
    const actions = document.createElement('div'); actions.className = 'actions';
    const configure = document.createElement('button'); configure.type = 'button'; configure.className = 'quiet'; configure.textContent = 'Connection settings'; configure.disabled = account.running;
    configure.onclick = () => edit(account);
    const open = document.createElement('button'); open.type = 'button'; open.textContent = account.running ? 'Open dashboard' : 'Launch dashboard';
    open.onclick = async () => {
      open.disabled = true; message('Opening ' + account.label + '…');
      // Open during the user gesture, before awaiting the server, to avoid popup blocking.
      const tab = window.open('about:blank', '_blank');
      if (tab) tab.opener = null;
      try {
        const result = await api('open', {account_id: account.id});
        if (result.status === 'STARTING') { if (tab) tab.close(); await refresh(); message('Dashboard is still initializing. Wait a few seconds, then open it from the account row.'); return; }
        if (result.status === 'FAILED') throw new Error('Dashboard did not start. Review its local log.');
        // The dashboard may need a few seconds to initialize data services.
        if (tab) tab.location.href = result.url + 'workspace-entry';
        message('Dashboard launching. Its strategy runners require their own deliberate Start.');
        await refresh();
      } catch (e) { if (tab) tab.close(); message(e.message); }
      finally { open.disabled = false; }
    };
    if (currentUser.admin) {
      const bounce = document.createElement('button');
      bounce.type = 'button'; bounce.className = 'quiet';
      bounce.textContent = 'Rolling bounce';
      bounce.title = 'Restart only this broker dashboard. Active runners, owned positions or pending orders block restart.';
      bounce.disabled = !account.running;
      bounce.onclick = async () => {
        if (!window.confirm(`Restart ${account.label} dashboard? All strategy runners must be stopped and will remain stopped.`)) return;
        bounce.disabled = true;
        try {
          let job = await api('bounce', {account_id: account.id});
          for (let attempt = 0; attempt < 45; attempt++) {
            message(`${account.label} · ${job.tag || 'Broker rolling bounce'} · ${job.message}`);
            if (job.status === 'READY') { await refresh(); return; }
            if (job.status === 'FAILED') throw new Error(job.message);
            await new Promise(resolve => setTimeout(resolve, 1500));
            job = await api('bounce-status', {account_id: account.id});
          }
          message('Readiness is not confirmed yet. Check the account status; no automatic second bounce was sent.');
        } catch (error) { message(error.message); }
        finally { bounce.disabled = false; }
      };
      actions.append(bounce);
    }
    actions.append(configure, open); section.append(detail, actions); $('accounts').append(section);
  }
}
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

  currentAccount = account; $('configuration').hidden = false;
  $('configuration-title').textContent = 'Connect ' + account.label;
  $('callback').textContent = account.broker === 'FYERS' ? `Register FYERS redirect URI: http://127.0.0.1:${account.port}/callback. Complete browser login inside this account’s dashboard after saving.` : 'Use your Delta India application key and secret. Configure its allowed IP and permissions in Delta.';
  $('key-label').firstChild.textContent = account.broker === 'FYERS' ? 'Application ID' : 'India API key';
  $('secret-label').firstChild.textContent = account.broker === 'FYERS' ? 'Application secret' : 'India API secret';
  $('credential-key').value = ''; $('credential-key').required = !account.configured;
  $('credential-secret').value = ''; $('credential-secret').required = !account.configured;
  $('live-enabled').checked = !!account.live_enabled;
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
bind('add-account', async data => { await api('accounts', Object.fromEntries(data)); $('add-account').reset(); await refresh(); message('Workspace created. Save its connection settings before broker login.'); });
bind('add-user', async data => { await api('users', Object.fromEntries(data)); $('add-user').reset(); await refresh(); message('User created. They can sign in and add their own broker accounts.'); });
bind('reset-user-password', async data => {
  const values=Object.fromEntries(data);
  if(values.new_password!==values.confirm_password)throw new Error('Passwords do not match.');
  const result=await api('reset-password',{username:values.username,new_password:values.new_password});
  $('reset-user-password').reset();$('reset-password-panel').hidden=true;
  if(result.signed_out){currentUser=null;$('workspace').hidden=true;$('signin').hidden=false;}
  message('Password reset for '+result.username+'. All their sessions were signed out.');
});
$('cancel-password-reset').onclick=()=>{$('reset-user-password').reset();$('reset-password-panel').hidden=true;};
bind('change-password', async data => {
  await api('password', Object.fromEntries(data)); $('change-password').reset(); currentUser = null;
  $('accounts').replaceChildren(); $('workspace').hidden = true; $('signin').hidden = false;
  message('Password updated. All your sessions were signed out. Background strategies continue their existing lifecycle.');
});
bind('configure', async () => {
  const credentials = currentAccount.broker === 'MOTILAL_OSWAL' ? {MO_CLIENT_ID:currentAccount.account_ref,MO_API_KEY:$('credential-key').value,MO_API_SECRET:$('credential-secret').value} : currentAccount.broker === 'FYERS' ? {FYERS_APP_ID: $('credential-key').value, FYERS_SECRET_KEY: $('credential-secret').value} : {DELTA_INDIA_API_KEY: $('credential-key').value, DELTA_INDIA_API_SECRET: $('credential-secret').value};
  await api('configure', {account_id: currentAccount.id, credentials, live_enabled: $('live-enabled').checked});
  $('configure').reset(); $('configuration').hidden = true; currentAccount = null;
  await refresh(); message('Connection saved. Launch the account dashboard when ready.');
});
$('cancel-config').onclick = () => { $('configure').reset(); $('configuration').hidden = true; currentAccount = null; };
$('logout').onclick = async () => {
  try { await api('logout', {}); currentUser = null; currentAccount = null; $('accounts').replaceChildren(); $('workspace').hidden = true; $('configuration').hidden = true; $('signin').hidden = false; message('Signed out. This does not stop any existing background strategy.'); }
  catch (e) { message(e.message); }
};
refresh().catch(() => { currentUser = null; $('signin').hidden = false; $('workspace').hidden = true; });
