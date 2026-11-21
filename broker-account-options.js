/* User-owned account inventory shared by execution forms. No broker mutations. */
(function(root){
  'use strict';
  const NAMES={FYERS:'FYERS',DHAN:'Dhan',MOTILAL_OSWAL:'Motilal Oswal',DELTA_INDIA:'Delta India'};
  function choices(accounts,{kind='strategy',currentBroker='FYERS',workspaceId=null}={}){
    return accounts.filter(account=>kind!=='sector'||account.broker!=='DELTA_INDIA').map(account=>{
      const same=!!workspaceId&&account.id===workspaceId;
      const supported=kind==='parser'?(account.broker==='FYERS'||account.parser_supported===true):account.broker==='MOTILAL_OSWAL'?['renko','sector','screener','manual','account','parser'].includes(kind):kind==='screener'&&account.broker==='DHAN'?account.screener_read_only===true:kind==='parser'?account.broker==='FYERS':kind==='sector'?Object.prototype.hasOwnProperty.call(NAMES,account.broker):kind==='account'?['FYERS','DHAN'].includes(account.broker):['strategy','delta-manual'].includes(kind)?same&&account.broker===currentBroker:(kind==='manual'||['renko','rsi','band','kama'].includes(kind)&&(account.strategy_routes||[]).includes(kind))&&account.broker==='DHAN'||['FYERS','DELTA_INDIA'].includes(account.broker)&&(account.broker===currentBroker||kind==='renko')||same&&account.broker===currentBroker;
      const reason=account.disconnected?'account disconnected':!account.configured?'connection settings incomplete':supported?'':kind==='parser'?'parser backend activation pending':account.broker==='DHAN'&&kind==='screener'?'read-only screener backend unavailable':account.broker==='DHAN'&&kind!=='manual'?'manual orders only; strategy routing unavailable':account.broker!==currentBroker?'not supported by this form':'open this account workspace to use its credentials';
      return {id:account.id,broker:account.broker,value:kind==='manual'&&account.broker==='DHAN'?'dhan:'+account.id:'account:'+account.id,
        label:(NAMES[account.broker]||account.broker)+' · '+account.label+(reason?' — '+reason:''),disabled:!!reason,same};
    });
  }
  function sectorSelection(rows,{requestedId,previousId,previousValue,workspaceId,preferredId,currentBroker='FYERS'}={}){
    const available=rows.filter(row=>!row.disabled);
    const requested=available.find(row=>row.id===requestedId);
    if(requestedId)return requested||null;
    const previous=available.find(row=>row.id===previousId)||available.find(row=>row.value===previousValue||(row.same&&row.broker===previousValue));
    if(previous)return previous;
    // Preserve unavailable explicit selections for review; default only an unset form.
    if(requestedId||previousId||previousValue)return null;
    if(workspaceId){
      const workspace=available.find(row=>row.id===workspaceId);
      if(workspace)return workspace;
    }
    const preferred=available.find(row=>row.id===preferredId);
    if(preferred)return preferred;
    const fyers=available.find(row=>row.broker==='FYERS');
    if(fyers)return fyers;
    if(workspaceId)return null;
    return available.find(row=>row.broker===currentBroker)||(available.length===1?available[0]:null);
  }
  function accountSelection(rows,{requestedId,previousId,previousValue,workspaceId}={}){
    const available=rows.filter(row=>!row.disabled);
    if(requestedId)return available.find(row=>row.id===requestedId)||null;
    if(previousId||previousValue)return available.find(row=>row.id===previousId||row.value===previousValue||(row.same&&row.broker===previousValue))||null;
    if(workspaceId)return available.find(row=>row.id===workspaceId)||null;
    return available.length===1?available[0]:null;
  }
  function retryInventory(load,onError,schedule=setTimeout){
    let failures=0;
    async function attempt(){
      try{await load();}
      catch(error){onError(error);schedule(attempt,Math.min(30000,1000*2**Math.min(failures++,5)));}
    }
    return attempt();
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={choices,sectorSelection,accountSelection,retryInventory};return;}
  root.BrokerAccountOptions={choices,accountSelection,preferredChartAccount};
  let accounts=[],context=null,ready=false;
  const registry=new WeakMap();
  function preferredChartAccount(username,params=new URLSearchParams(location.search)) {
    const explicit=params.get('chartSource');
    if(explicit)return explicit;
    if(!username)return undefined;
    try{
      return JSON.parse(localStorage.getItem('sector-pulse:chart-source:'+username))?.source;
    }catch{return undefined;}
  }
  function fill(select,kind,currentBroker){
    const signature=JSON.stringify([accounts,kind,currentBroker,context?.workspace?.id]);
    if(registry.get(select)===signature)return;
    registry.set(select,signature);
    const previousId=select.selectedOptions?.[0]?.dataset.savedBrokerAccount;
    const savedValue=['screener','parser','account'].includes(kind)
      ? (['parser','account'].includes(kind)?localStorage:sessionStorage).getItem(kind+'-account:'+context?.username)||sessionStorage.getItem(kind+'-account:'+context?.username)
      : null;
    const previousValue=previousId?select.value:savedValue;
    select.replaceChildren();
    const rows=choices(accounts,{kind,currentBroker,workspaceId:context?.workspace?.id});
    for(const row of rows){
      const option=document.createElement('option');
      option.value=row.same?row.broker:row.value;
      option.textContent=row.label+(row.same?' · this account':'');
      option.disabled=row.disabled;option.dataset.savedBrokerAccount=row.id;select.append(option);
    }
    const params=new URLSearchParams(location.search);
    const requested=kind==='sector'
      ? params.get('sectorAccount')||(context?.workspace?null:params.get('brokerAccount'))
      : root.BrokerForms?.initial(kind)||context?.workspace?.id;
    const explicitRenkoBroker=kind==='renko'&&params.get('renkoBroker');
    const defaultRows=explicitRenkoBroker&&!requested&&!previousId
      ? rows.filter(row=>row.broker===explicitRenkoBroker)
      : rows;
    const target=kind==='sector'
      ? sectorSelection(rows,{requestedId:requested,previousId,previousValue,workspaceId:context?.workspace?.id,
        currentBroker,preferredId:preferredChartAccount(context?.username,params)})
      : accountSelection(defaultRows,{requestedId:requested,previousId,previousValue});
    if(target)select.value=target.same?target.broker:target.value;
    else{const empty=document.createElement('option');empty.value='';empty.textContent=kind==='sector'?(rows.some(row=>!row.disabled)?'Select an account for Sector Rotation':'Sector Rotation unavailable · no supported configured account'):(rows.some(row=>!row.disabled)?'Select a broker account':rows.length?'No saved account is available for this section':'No saved broker accounts');empty.disabled=true;empty.selected=true;select.prepend(empty);select.value='';}
    if(kind==='screener'){const note=select.closest('label')?.querySelector('small');if(note)note.textContent=target?.broker==='DHAN'?'Dhan account data only · read-only screening and analysis. Execution is unavailable here.':'Choose the account used for source quotes and analysis.';}
    if(kind==='sector'){const note=select.closest('label')?.querySelector('small');if(note){note.setAttribute('role','status');note.textContent=target?'Sector Rotation uses this data account only. Trading account selections stay unchanged. Motilal native candles require warmup.':rows.some(row=>!row.disabled)?'Select a FYERS, Dhan or Motilal Oswal data account for Sector Rotation. Delta India is not applicable; trading account selections stay unchanged.':'Sector Rotation is unavailable: no supported configured data account. Delta India is not applicable; trading account selections stay unchanged.';}}
    if(requested&&target?.id===requested)select.dataset.initialAccountApplied='true';
    if(!select.dataset.accountsBound){
      select.dataset.accountsBound='true';
      select.addEventListener('change',event=>{
        const saved=accounts.find(a=>select.selectedOptions[0]?.dataset.savedBrokerAccount===a.id);
        if(kind==='sector'&&saved){const note=select.closest('label')?.querySelector('small');if(note)note.textContent='Sector Rotation uses this data account only. Trading account selections stay unchanged. Motilal native candles require warmup.';}
        if(['screener','parser','account'].includes(kind)&&saved)(['parser','account'].includes(kind)?localStorage:sessionStorage).setItem(kind+'-account:'+context?.username,'account:'+saved.id);
        if(saved&&['account','sector','screener','renko','rsi','band','kama','manual','parser'].includes(kind)){
          event.stopImmediatePropagation();
          root.BrokerForms.onChange(kind,saved);
        }else if(['account','sector','screener','rsi','band','kama','manual','parser'].includes(kind)){
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
    ['#screener-analysis','screener-analysis-broker-account','FYERS','screener'],
    ['#straddle-options','sensex-broker-account','FYERS','strategy'],
    ['#nifty-straddle-options','nifty-broker-account','FYERS','strategy'],
    ['#ema-band-mode','ema-band-broker-account','FYERS','band'],
    ['#cross-mode','cross-broker-account','FYERS','rsi'],
    ['#kama-mode','kama-broker-account','FYERS','kama'],
    ['#trade-parser-input','parser-broker-account','FYERS','parser'],
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

        const note=document.createElement('small');note.textContent=kind==='sector'?'Select your data broker. Motilal uses only its captured native candles and requires warmup. Delta India sector data is unavailable.':'Your saved accounts are listed below. Unavailable routes are disabled; choosing a broker never starts a runner.';
        label.append(select,note);
        const field=anchor.closest('label');
        if(anchor.tagName==='FORM')anchor.prepend(label);
        else if(field)field.parentElement.prepend(label);
        else anchor.before(label);
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
        if(account.broker==='MOTILAL_OSWAL'&&account.configured){
          const connect=document.createElement('a');connect.textContent='Motilal Oswal connection details';connect.href='/broker-workspace/'+account.id+'/workspace-entry';line.append(' · ',connect);
        }

      }
      if(!accounts.length){const line=document.createElement('div');line.textContent='No saved accounts. Add accounts in User & broker setup.';panel.append(line);}
      const note=document.createElement('small');note.textContent='Saved settings do not confirm authentication or connection health.';panel.append(note);
      const link=document.createElement('a');link.textContent='Manage broker accounts';link.href=context?.portal_url||'/accounts';panel.append(link);card.append(panel);
      const style=document.createElement('style');style.textContent='#configured-broker-accounts{border-top:1px solid #334154;margin-top:12px;padding-top:10px;font-size:12px;display:grid;gap:7px}#configured-broker-accounts small,.broker-account-field small{color:#91a3ba;font-size:11px}.broker-account-field{max-width:100%;margin-bottom:12px}';document.head.append(style);
    }
  }
  async function load(){
      const response=await fetch('/api/workspace-context',{signal:AbortSignal.timeout(15000),cache:'no-store'});context=response.ok?await response.json():root.SectorPulseWorkspace;
      const inventory=await fetch('/api/workspaces/accounts',{signal:AbortSignal.timeout(15000),cache:'no-store'});
      if(inventory.ok)accounts=(await inventory.json()).accounts||[];
      else if(context?.workspace)accounts=[{...context.workspace,configured:true}];
      else throw Error('Saved broker account list unavailable');
      await Promise.all(accounts.filter(a=>a.broker==='DHAN').map(async account=>{
        try{const response=await fetch('/api/dhan/capabilities?account_id='+encodeURIComponent(account.id),{signal:AbortSignal.timeout(15000),cache:'no-store'});
          if(response.ok){const capability=await response.json();account.strategy_routes=capability.strategy_routes||[];account.screener_read_only=capability.screener_read_only===true;}
        }catch(error){account.strategy_routes=[];}
      }));
      for(const account of accounts)account.parser_supported=account.broker==='FYERS'||context?.parser_native_supported===true;
      root.BrokerForms?.setAccounts(accounts,context);ready=true;apply();root.dispatchEvent(new CustomEvent('broker-accounts-ready'));
  }
  new MutationObserver(()=>apply()).observe(document.body,{childList:true,subtree:true});
  retryInventory(load,error=>{
    console.warn('Broker account options temporarily unavailable; retrying: '+error.message);
    root.dispatchEvent(new CustomEvent('broker-accounts-retrying',{detail:{message:'Broker account list unavailable; reconnecting automatically.'}}));
  });
})(typeof window!=='undefined'?window:globalThis);
