(() => {
  const form=document.querySelector('#dashboard-login');
  const api='/api/dashboard-auth/';
  if(!form){
    const dock=document.createElement('section');dock.className='account-dock';dock.setAttribute('aria-label','Your account');
    const identity=document.createElement('div');identity.className='account-identity';identity.textContent='Your account';
    const actions=document.createElement('div');actions.className='account-actions';dock.append(identity,actions);
    const button=document.createElement('button');button.className='account-action account-signout';button.type='button';button.textContent='Sign out';
    button.title='Sign out of the dashboard. Background strategies continue.';
    button.onclick=async()=>{button.disabled=true;try{const r=await fetch(api+'logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error('Sign-out failed.');location.assign('/auth/login');}catch(e){button.disabled=false;button.textContent=e.message;}};
    const side=document.querySelector('.side')||document.body;actions.append(button);side.append(dock);
    fetch(api+'status').then(r=>r.json()).then(user=>{identity.textContent=user.username||'Your account';identity.title=user.admin?'Administrator':'User';if(user.admin){const link=document.createElement('a');link.href='/user-master';link.className='account-action';link.textContent='User Master';actions.prepend(link);}});return;
  }
  const message=document.querySelector('#message'),submit=document.querySelector('#submit');let setup=false;
  fetch(api+'status').then(r=>{if(!r.ok)throw Error('Sign-in status unavailable.');return r.json();}).then(s=>{
    setup=s.setup_required;
    if(setup){document.querySelector('#title').textContent='Create your dashboard sign-in.';document.querySelector('#intro').textContent='Choose your username and a password of at least 12 characters. Your existing dashboard and broker settings stay in place.';form.elements.password.minLength=12;form.elements.password.autocomplete='new-password';submit.textContent='Create sign-in';}
    submit.disabled=false;
  }).catch(e=>message.textContent=e.message);
  form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;message.textContent='';try{
    const r=await fetch(api+(setup?'setup':'login'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});const d=await r.json();if(!r.ok)throw Error(d.error||'Sign-in failed.');form.reset();const next=new URLSearchParams(location.search).get('next');const target=new URL(next||'/',location.origin);location.assign(target.origin===location.origin&&!target.pathname.startsWith('/auth/')?target.pathname+target.search:'/');
  }catch(e){message.textContent=e.message;}finally{submit.disabled=false;}};
})();
