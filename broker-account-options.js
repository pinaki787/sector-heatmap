/* User-owned account inventory shared by execution forms. No broker mutations. */
(function(root){
  'use strict';
  const NAMES={FYERS:'FYERS',DHAN:'Dhan',DELTA_INDIA:'Delta India'};
  function choices(accounts,{kind='strategy',currentBroker='FYERS',workspaceId=null}={}){
    return accounts.map(account=>{
      const same=!!workspaceId&&account.id===workspaceId;
      const supported=kind==='sector'?Object.prototype.hasOwnProperty.call(NAMES,account.broker):kind==='account'?['FYERS','DHAN'].includes(account.broker):['strategy','delta-manual'].includes(kind)?same&&account.broker===currentBroker:(kind==='manual'||['renko','rsi','band','kama'].includes(kind)&&(account.strategy_routes||[]).includes(kind))&&account.broker==='DHAN'||['FYERS','DELTA_INDIA'].includes(account.broker)&&(account.broker===currentBroker||kind==='renko')||same&&account.broker===currentBroker;
      const reason=!account.configured?'connection settings incomplete':supported?'':account.broker==='DHAN'&&kind!=='manual'?'manual orders only; strategy routing unavailable':account.broker!==currentBroker?'not supported by this form':'open this account workspace to use its credentials';
      return {id:account.id,broker:account.broker,value:kind==='manual'&&account.broker==='DHAN'?'dhan:'+account.id:'account:'+account.id,
        label:(NAMES[account.broker]||account.broker)+' · '+account.label+(reason?' — '+reason:''),disabled:!!reason,same};
    });
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={choices};return;}
  let accounts=[],context=null,ready=false;
  const registry=new WeakMap();
  function fill(select,kind,currentBroker){
    const signature=JSON.stringify([accounts,kind,currentBroker,context?.workspace?.id]);
    if(registry.get(select)===signature)return;
    registry.set(select,signature);
    const before=select.value;
    const previousId=select.selectedOptions?.[0]?.dataset.savedBrokerAccount;
    select.replaceChildren();
    const rows=choices(accounts,{kind,currentBroker,workspaceId:context?.workspace?.id});
    for(const row of rows){
      const option=document.createElement('option');
      option.value=row.same?row.broker:row.value;
      option.textContent=row.label+(row.same?' · this account':'');
      option.disabled=row.disabled;option.dataset.savedBrokerAccount=row.id;select.append(option);
    }
    const requested=root.BrokerForms?.initial(kind);
    const target=rows.find(r=>r.id===(requested||previousId)&&!r.disabled)
      ||rows.find(r=>r.same&&!r.disabled)
      ||rows.find(r=>r.value===before&&!r.disabled)
      ||(kind==='manual'?rows.find(r=>r.broker==='DHAN'&&!r.disabled):null)
      ||rows.find(r=>r.broker===currentBroker&&!r.disabled)
      ||(kind==='sector'?rows.find(r=>['FYERS','DHAN'].includes(r.broker)&&!r.disabled):null);
    if(target)select.value=target.same?target.broker:target.value;
    else{const empty=document.createElement('option');empty.value='';empty.textContent='Select a configured broker account';empty.disabled=true;empty.selected=true;select.prepend(empty);}
    if(requested&&target?.id===requested)select.dataset.initialAccountApplied='true';
    if(!select.dataset.accountsBound){
      select.dataset.accountsBound='true';
      select.addEventListener('change',event=>{
        const saved=accounts.find(a=>select.selectedOptions[0]?.dataset.savedBrokerAccount===a.id);
        if(saved&&['account','sector','renko','rsi','band','kama','manual'].includes(kind)){
          event.stopImmediatePropagation();
          root.BrokerForms.onChange(kind,saved);
        }else if(['account','sector','rsi','band','kama','manual'].includes(kind)){
          root.BrokerForms.onChange(kind,null);
        }
        if(kind==='manual'){
          for(const id of ['submit-ticket','submit-handoff-batch','submit-screener-order']){const button=document.getElementById(id);if(button)button.disabled=true;}
          for(const id of ['ticket-review','handoff-batch-review','screener-order-review']){const panel=document.getElementById(id);if(panel)panel.hidden=true;}
        }
      },true);
    }
  }
  const forms=[
    ['#open-positions','live-feed-broker-account','FYERS','account'],
    ['#sector-filter','sector-broker-account','FYERS','sector'],
    ['#straddle-options','sensex-broker-account','FYERS','strategy'],
    ['#nifty-straddle-options','nifty-broker-account','FYERS','strategy'],
    ['#ema-band-mode','ema-band-broker-account','FYERS','band'],
    ['#cross-mode','cross-broker-account','FYERS','rsi'],
    ['#kama-mode','kama-broker-account','FYERS','kama'],
    ['#trade-parser-entry-mode','parser-broker-account','FYERS','strategy'],
    ['#delta-ticket-mode','delta-ticket-broker-account','DELTA_INDIA','delta-manual'],
    ['#delta-strategy-mode','delta-strategy-broker-account','DELTA_INDIA','strategy']
  ];
  function apply(){
    if(!ready)return;
    for(const select of document.querySelectorAll('.order-account'))fill(select,'manual','FYERS');
    const renko=document.getElementById('renko-broker');if(renko)fill(renko,'renko',context?.workspace?.broker||new URLSearchParams(location.search).get('renkoBroker')||'FYERS');
    for(const [selector,id,broker,kind] of forms){
      const anchor=document.querySelector(selector);if(!anchor)continue;
      let select=document.getElementById(id);
      if(!select){
        const label=document.createElement('label');label.className='field broker-account-field';label.textContent=kind==='sector'?'Sector Rotation broker account':'Broker account';
        select=document.createElement('select');select.id=id;select.setAttribute('aria-label','Broker account');

        const note=document.createElement('small');note.textContent=kind==='sector'?'Select FYERS or Dhan for sector market data. Dhan requires an active Data API subscription. Delta India sector data is unavailable.':'Your saved accounts are listed below. Unavailable routes are disabled; choosing a broker never starts a runner.';
        label.append(select,note);
        if(anchor.tagName==='FORM')anchor.prepend(label);else (anchor.closest('label')||anchor).before(label);
      }
      fill(select,kind,broker);
    }
    const card=document.querySelector('.broker-card');
    if(card&&!document.getElementById('configured-broker-accounts')){
      const label=Array.from(card.querySelectorAll('*')).find(n=>n.children.length===0&&n.textContent.trim()==='BROKER CONNECTION');if(label)label.textContent='SERVER MARKET DATA';
      const panel=document.createElement('div');panel.id='configured-broker-accounts';panel.setAttribute('aria-label','Your configured broker accounts');
      const heading=document.createElement('b');heading.textContent='Your broker accounts';panel.append(heading);
      for(const account of accounts){
        const line=document.createElement('div');line.textContent=(NAMES[account.broker]||account.broker)+' · '+account.label+' · '+(account.configured?'settings saved':'setup incomplete');panel.append(line);
        if(account.broker==='DHAN'&&account.configured){
          fetch('/api/dhan/status?account_id='+encodeURIComponent(account.id)).then(async response=>{
            if(!response.ok)throw Error('Connection unverified');
            const value=await response.json();
            line.textContent='Dhan · '+account.label+' · '+(value.authenticated?'authenticated':'connection unverified')+' · Data API '+(value.data_plan||'unverified');
          }).catch(()=>{line.textContent='Dhan · '+account.label+' · connection unverified';});
        }
      }
      if(!accounts.length){const line=document.createElement('div');line.textContent='No saved accounts. Add accounts in User & broker setup.';panel.append(line);}
      const note=document.createElement('small');note.textContent='Saved settings do not confirm authentication or connection health.';panel.append(note);
      const link=document.createElement('a');link.textContent='Manage broker accounts';link.href=context?.portal_url||'/accounts';panel.append(link);card.append(panel);
      const style=document.createElement('style');style.textContent='#configured-broker-accounts{border-top:1px solid #334154;margin-top:12px;padding-top:10px;font-size:12px;display:grid;gap:7px}#configured-broker-accounts small,.broker-account-field small{color:#91a3ba;font-size:11px}.broker-account-field{max-width:100%;margin-bottom:12px}';document.head.append(style);
    }
  }
  async function load(){
    try{
      const response=await fetch('/api/workspace-context');context=response.ok?await response.json():root.SectorPulseWorkspace;
      const inventory=await fetch('/api/workspaces/accounts');
      if(inventory.ok)accounts=(await inventory.json()).accounts||[];
      else if(context?.workspace)accounts=[{...context.workspace,configured:true}];
      else throw Error('Saved broker account list unavailable');
      await Promise.all(accounts.filter(a=>a.broker==='DHAN').map(async account=>{
        try{const response=await fetch('/api/dhan/capabilities?account_id='+encodeURIComponent(account.id));
          if(response.ok)account.strategy_routes=(await response.json()).strategy_routes||[];
        }catch(error){account.strategy_routes=[];}
      }));
      root.BrokerForms?.setAccounts(accounts);ready=true;apply();root.dispatchEvent(new CustomEvent('broker-accounts-ready'));
    }catch(error){root.BrokerForms?.fail(error);console.warn('Broker account options: '+error.message);}
  }
  new MutationObserver(()=>apply()).observe(document.body,{childList:true,subtree:true});
  load();
})(typeof window!=='undefined'?window:globalThis);
