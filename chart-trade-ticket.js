/* Chart trade ticket: explicit review, independent from runner controls. */
(function (root) {
  'use strict';
  const prices = (() => {
    function parts(value) {
      const match=/^\+?(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i.exec(String(value).trim());
      if(!match)throw Error('Enter a positive exact price.');
      let scale=(match[2]||'').length-Number(match[3]||0);
      if(!Number.isSafeInteger(scale)||Math.abs(scale)>1000)throw Error('The price exponent is outside broker numeric precision.');
      let n=BigInt(match[1]+(match[2]||''));
      if(scale<0){n*=10n**BigInt(-scale);scale=0;}
      while(scale>0 && n%10n===0n){n/=10n;scale--;}
      return {n,scale};
    }
    function decimal(n,scale) {
      let text=n.toString().padStart(scale+1,'0');
      if(scale)text=text.slice(0,-scale)+'.'+text.slice(-scale);
      return text.replace(/(\.\d*?)0+$/,'$1').replace(/\.$/,'');
    }
    function canonical(value){const p=parts(value);return decimal(p.n,p.scale);}
    function aligned(a,b) {
      a=parts(a);b=parts(b);const scale=Math.max(a.scale,b.scale);
      return [a.n*10n**BigInt(scale-a.scale),b.n*10n**BigInt(scale-b.scale)];
    }
    function equal(a,b){try{return canonical(a)===canonical(b);}catch{return false;}}
    function compare(a,b){const [x,y]=aligned(a,b);return x<y?-1:x>y?1:0;}
    function ticks(value,tick) {
      const [a,b]=aligned(value,tick);
      if(b<=0n||a%b!==0n)throw Error('The marked price must match the broker tick.');
      return (a/b).toString();
    }
    function fromTicks(value,tick) {
      const count=parts(value),unit=parts(tick);
      if(count.scale!==0 || unit.n<=0n)throw Error('Enter a whole number of broker ticks.');
      return decimal(count.n*unit.n,unit.scale);
    }
    function snap(value,tick) {
      const [a,b]=aligned(value,tick);
      if(b<=0n)throw Error('A verified broker tick is required.');
      return fromTicks(((a+b/2n)/b).toString(),tick);
    }
    function format(value) {
      const p=parts(value);
      if(p.scale>2)return p.n.toLocaleString('en-IN')+' / '+(10n**BigInt(p.scale)).toLocaleString('en-IN');
      const unit=10n**BigInt(p.scale),whole=p.n/unit,fraction=(p.n%unit).toString().padStart(p.scale,'0');
      return whole.toLocaleString('en-IN')+(p.scale?'.'+fraction:'');
    }
    function rewardRisk(entry,stop,target) {
      const values=[entry,stop,target].map(parts),scale=Math.max(...values.map(p=>p.scale));
      const [e,s,t]=values.map(p=>p.n*10n**BigInt(scale-p.scale));
      const risk=e>s?e-s:s-e,reward=t>e?t-e:e-t;
      if(!risk)return '';
      const hundredths=(reward*100n+risk/2n)/risk;
      return (hundredths/100n).toString()+'.'+(hundredths%100n).toString().padStart(2,'0');
    }
    return {canonical,equal,compare,ticks,fromTicks,snap,format,rewardRisk,precision:value=>parts(value).scale};
  })();
  root.SectorPulseChartTradePrices=prices;
  function mount(host, hooks) {
    const ticket = document.createElement('aside');
    ticket.className = 'sp-chart-trade-ticket';
    ticket.setAttribute('aria-label', 'Chart order ticket');
    ticket.hidden = true;
    ticket.innerHTML = `<header><div><strong data-trade-title>Chart order</strong><small data-trade-account></small></div>
      <button type="button" data-trade-close aria-label="Close chart order ticket">×</button></header>
      <p data-trade-instrument></p><form>
      <label>Quantity <input name="quantity" type="number" min="1" step="1" required placeholder="Units"></label>
      <label>Entry type <select name="entry_type"><option value="LIMIT">Limit</option><option value="STOP_LIMIT">Stop-limit</option></select></label>
      <label>Product <select name="product" required></select></label>
      <label data-trade-exit-trigger hidden>Exit trigger price <select name="exit_trigger_method">
        <option value="last_traded_price">Last Traded Price</option><option value="mark_price">Mark Price</option>
      </select></label>
      <div class="sp-chart-trade-levels">
      <label><span data-trade-caption="entry">Entry</span><span><input name="entry" type="number" min="0" step="any" required>
        <button type="button" data-trade-pick="entry" aria-label="Mark entry on chart">⌖</button></span></label>
      <label><span data-trade-caption="stop_loss">Stop loss</span><span><input name="stop_loss" type="number" min="0" step="any" required>
        <button type="button" data-trade-pick="stop_loss" aria-label="Mark stop loss on chart">⌖</button></span></label>
      <label><span data-trade-caption="target">Target</span><span><input name="target" type="number" min="0" step="any" required>
        <button type="button" data-trade-pick="target" aria-label="Mark target on chart">⌖</button></span></label></div>
      <label data-trade-limit hidden><span data-trade-caption="limit_price">Entry limit</span><input name="limit_price" type="number" min="0" step="any"></label>
      <small data-trade-tick-unit hidden></small>
      <output data-trade-rr aria-label="Reward to risk"></output>
      <p data-trade-status role="status"></p><button type="button" data-trade-check hidden>Refresh broker status</button>
      <button type="button" data-trade-cancel-condition hidden>Cancel waiting trigger</button>
      <button type="submit" data-trade-preview>Review broker order</button>
      <section data-trade-review hidden><h3>Broker order preview</h3><dl data-trade-summary></dl><p data-trade-notice hidden></p>
        <label><input type="checkbox" data-trade-confirm> I confirm this entry, stop loss and target for the selected broker account.</label>
        <button type="button" data-trade-arm disabled>Place entry with linked exits</button>
      </section></form>`;
    host.append(ticket);
    const field = name => ticket.querySelector('[name="'+name+'"]');
    const status = ticket.querySelector('[data-trade-status]');
    const review = ticket.querySelector('[data-trade-review]');
    const previewButton = ticket.querySelector('[data-trade-preview]');
    const armButton = ticket.querySelector('[data-trade-arm]');
    const confirm = ticket.querySelector('[data-trade-confirm]');
    let context, revision = 0, preview, previewRequest, busy = false, submitted = false, submittedReview, statusTimer, protectionTimer, statusRequest, cancelRequest, tickMode=false;
    const checkButton=ticket.querySelector('[data-trade-check]');
    const cancelButton=ticket.querySelector('[data-trade-cancel-condition]');
    function showCancellation(result){
      cancelButton.hidden=!(context?.broker==='DHAN' && hooks.cancelCondition &&
        ['WAITING_FOR_TRIGGER','TRIGGERED','REVIEW_REQUIRED'].includes(result.status));
    }
    function publishStatus(result,reviewed){
      showCancellation(result);hooks.onStatus?.(result,reviewed);
    }

    function stopStatus(){clearTimeout(statusTimer);clearTimeout(protectionTimer);submittedReview=undefined;statusRequest=undefined;cancelRequest=undefined;cancelButton.hidden=true;cancelButton.disabled=false;checkButton.disabled=false;checkButton.hidden=true;}
    async function checkStatus(){
      if(!submittedReview || statusRequest || cancelRequest || !hooks.status)return;
      const reviewed=submittedReview, currentRevision=revision;
      const requestToken={};statusRequest=requestToken;checkButton.disabled=true;
      try {
        const record=await hooks.status({preview_id:reviewed.preview_id,account_id:reviewed.plan.account_id,broker:reviewed.plan.broker});
        if(currentRevision!==revision || submittedReview!==reviewed)return;
        const result=record.result||record;
        status.textContent=result.message||result.status||'Broker status is unavailable.';
        clearTimeout(protectionTimer);
        publishStatus(result,reviewed);
        if(result.protection_confirmed===true && !['CLOSED','CANCELLED','REJECTED','EXPIRED'].includes(result.status)){
          protectionTimer=setTimeout(()=>{
            if(currentRevision!==revision || submittedReview!==reviewed)return;
            const message='Broker protection status needs a fresh check. No order was resent.';
            status.textContent=message;
            publishStatus({status:'BROKER_STATUS_STALE',protection_confirmed:false,message},reviewed);
          },20000);
        }
        if(!['CLOSED','CANCELLED','REJECTED','EXPIRED'].includes(result.status))
          statusTimer=setTimeout(checkStatus,15000);
      } catch(error){
        if(currentRevision===revision && submittedReview===reviewed){
          clearTimeout(protectionTimer);
          status.textContent=error.message||'Broker status unavailable. No order was resent.';
          publishStatus({status:'BROKER_STATUS_UNAVAILABLE',protection_confirmed:false,message:status.textContent},reviewed);
          statusTimer=setTimeout(checkStatus,30000);
        }
      } finally {if(statusRequest===requestToken){statusRequest=undefined;checkButton.disabled=false;}}
    }
    checkButton.addEventListener('click',()=>{clearTimeout(statusTimer);checkStatus();});
    cancelButton.addEventListener('click',async()=>{
      if(cancelRequest || !submittedReview || cancelButton.hidden || !hooks.cancelCondition)return;
      const reviewed=submittedReview,token={};cancelRequest=token;
      clearTimeout(statusTimer);clearTimeout(protectionTimer);statusRequest=undefined;
      const currentRevision=++revision;
      cancelButton.disabled=true;checkButton.disabled=true;
      status.textContent='Cancelling the waiting chart trigger…';
      let refresh=false;
      try{
        const record=await hooks.cancelCondition({preview_id:reviewed.preview_id,account_id:reviewed.plan.account_id,broker:reviewed.plan.broker});
        if(revision!==currentRevision || submittedReview!==reviewed)return;
        const result=record.result||record;
        status.textContent=result.message||result.status||'Check chart order status.';
        publishStatus(result,reviewed);
        refresh=!['CANCELLED','CLOSED','REJECTED','EXPIRED'].includes(result.status);
      }catch(error){
        if(revision===currentRevision && submittedReview===reviewed){
          status.textContent=error.message||'Cancellation is unconfirmed. Refreshing order status.';
          cancelButton.hidden=true;refresh=true;
        }
      }finally{
        if(cancelRequest===token){
          cancelRequest=undefined;cancelButton.disabled=false;checkButton.disabled=Boolean(statusRequest);
          if(refresh)checkStatus();
        }
      }
    });

    const text = (selector, value) => { ticket.querySelector(selector).textContent = value; };
    function level(name) {
      const value=field(name).value;
      if(!value)return '';
      return tickMode?prices.fromTicks(value,context.price_tick):prices.canonical(value);
    }
    function showLevel(name,value) {
      field(name).value=value==null||value===''?'':tickMode?prices.ticks(value,context.price_tick):prices.canonical(value);
    }
    function configurePriceUnit(tick,values) {
      context.price_tick=tick;
      tickMode=Boolean(tick && prices.precision(tick)>2);
      const unit=ticket.querySelector('[data-trade-tick-unit]');
      unit.hidden=!tickMode;
      unit.textContent=tickMode?'Price fields use whole ticks. One tick = '+prices.format(tick)+' price units.':'';
      for(const [name,caption]of [['entry','Entry'],['stop_loss','Stop loss'],['target','Target'],['limit_price','Entry limit']]){
        const label=caption+(tickMode?' (ticks)':'');
        text('[data-trade-caption="'+name+'"]',label);
        field(name).setAttribute('aria-label',label);
        field(name).step=tickMode?'1':'any';field(name).min=tickMode?'1':'0';
        showLevel(name,values[name]);
      }
    }
    function invalidate() {
      revision++; preview = undefined; review.hidden = true; confirm.checked = false; armButton.disabled = true;
      ticket.querySelector('[data-trade-limit]').hidden = field('entry_type').value !== 'STOP_LIMIT';
      field('limit_price').required = field('entry_type').value === 'STOP_LIMIT';
      try {
        const entry=level('entry'),stop=level('stop_loss'),target=level('target');
        const valid=[entry,stop,target].every(value=>value && prices.compare(value,'0')>0)
          && (context?.side==='BUY' ? prices.compare(stop,entry)<0 && prices.compare(entry,target)<0
                                  : prices.compare(target,entry)<0 && prices.compare(entry,stop)<0);
        text('[data-trade-rr]',valid?'Reward / risk · '+prices.rewardRisk(entry,stop,target)+' : 1':'');
        hooks.onChange?.({...context,entry,stop_loss:stop,target,exit_trigger_method:field('exit_trigger_method').value});
      } catch(error) {
        text('[data-trade-rr]','');status.textContent=error.message;
      }
    }
    function payload() {
      const values = Object.fromEntries(['quantity','entry','stop_loss','target','entry_type','product','limit_price','exit_trigger_method'].map(name=>[name,field(name).value]));
      for(const name of ['entry','stop_loss','target','limit_price'])values[name]=level(name);
      if (values.entry_type === 'LIMIT') values.limit_price = values.entry;
      const quantity=Number(values.quantity);
      if(!Number.isSafeInteger(quantity)||quantity<=0)throw Error('Quantity must be a positive whole number within broker numeric precision.');
      return {...context,...values,quantity};
    }
    function setBusy(value) {
      busy=value; previewButton.disabled=value || submitted;
      previewButton.hidden=submitted;armButton.hidden=submitted;confirm.closest('label').hidden=submitted;
      for (const control of ticket.querySelectorAll('input,select,[data-trade-pick]')) control.disabled=value || submitted;
      armButton.disabled=value || submitted || !preview || preview.live_submission_enabled !== true || !confirm.checked;
    }
    function summarize(plan,preflight={}) {
      const rows = [['Account',context.account_name],['Instrument',plan.symbol],['Side',plan.side],
        ['Quantity',plan.quantity],['Entry type',plan.entry_type],['Entry',plan.entry],
        ['Stop loss',plan.stop_loss],['Target',plan.target],['Entry limit',plan.limit_price],['Product',plan.product]];
      if(plan.lot_size)rows.push(['Lot size',plan.lot_size]);
      if(plan.broker==='DELTA_INDIA')rows.push(['Exit trigger',plan.exit_trigger_method==='mark_price'?'Mark Price':'Last Traded Price']);
      if(plan.exit_trigger_method==='mark_price'&&preflight.quote?.mark_price)rows.push(['Current Mark Price',prices.format(preflight.quote.mark_price)]);
      const money=value=>Number(value).toLocaleString('en-IN',{maximumFractionDigits:2})+' '+(preflight.settlement_currency||'');
      if(preflight.available_funds!==undefined)rows.push(['Available funds',money(preflight.available_funds)]);
      if(preflight.required_margin!==undefined)rows.push(['Required margin',money(preflight.required_margin)]);
      else if(preflight.margin_status==='BROKER_ENFORCED_ON_SUBMISSION')
        rows.push(['Margin check','Broker checks at submission or trigger']);
      const notice=ticket.querySelector('[data-trade-notice]');
      notice.hidden=!preflight.notice;notice.textContent=preflight.notice||'';
      armButton.textContent=plan.broker==='DHAN'&&plan.entry_type==='STOP_LIMIT'?'Arm conditional entry':'Place entry with linked exits';
      const dl=ticket.querySelector('[data-trade-summary]');dl.replaceChildren();
      for(const [label,value] of rows) {
        const dt=document.createElement('dt'),dd=document.createElement('dd');
        dt.textContent=label;
        dd.textContent=['Entry','Stop loss','Target','Entry limit'].includes(label)
          ? tickMode?prices.ticks(value,context.price_tick)+' ticks':prices.format(value) : String(value ?? '');
        dl.append(dt,dd);
      }
    }
    ticket.querySelector('form').addEventListener('submit',async event=>{
      event.preventDefault();
      if(busy || submitted || !context) return;
      invalidate(); const requestRevision=revision; let request;
      try{request=payload();}catch(error){status.textContent=error.message;return;}
      const requestToken={};previewRequest=requestToken;
      setBusy(true);
      status.textContent='Refreshing broker contract, quote and account state…';
      try {
        const result=await hooks.prepare(request);
        if(requestRevision!==revision || ticket.hidden) return;
        if(!result?.preview_id || !result.confirmation_phrase || !result.plan || result.plan.account_id!==context.account_id
          || result.plan.broker!==context.broker || result.plan.symbol!==context.symbol || result.plan.side!==context.side) {
          throw Error('Broker preview differs from the selected chart order. Prepare it again.');
        }
        if (['quantity','entry','stop_loss','target','limit_price'].some(name=>!prices.equal(result.plan[name],request[name]))
          || result.plan.entry_type!==request.entry_type || result.plan.product!==request.product || result.plan.exit_trigger_method!==request.exit_trigger_method) {
          throw Error('Broker preview changed the marked prices, quantity or product. Review the chart levels and prepare again.');
        }
        if(result.plan.tick_size && !prices.equal(result.plan.tick_size,context.price_tick)){
          configurePriceUnit(result.plan.tick_size,request);
          hooks.onChange?.({...context,entry:request.entry,stop_loss:request.stop_loss,target:request.target,exit_trigger_method:request.exit_trigger_method});
        }
        if(result.plan.lot_size){field('quantity').step=String(result.plan.lot_size);field('quantity').min=String(result.plan.lot_size);}
        preview=result;summarize(result.plan,result.preflight);review.hidden=false;
        review.scrollIntoView?.({block:'nearest'});
        status.textContent=result.live_submission_enabled === true
          ? (result.plan.broker==='DHAN' && result.plan.entry_type==='STOP_LIMIT'
            ? 'Preview only. After confirmation, Sector Pulse watches live broker ticks and submits the reviewed limit with linked exits when the entry triggers. Execution price can differ.'
            : 'Preview only. After confirmation, the broker triggers entry at the marked level and linked exits after fills. Execution price can differ from the marked price.')
          : 'Preview only. Live trading is disabled for this broker account.';
      } catch(error) {
        if(requestRevision===revision && !ticket.hidden) status.textContent=error.message || 'Broker preview unavailable.';
      } finally {
        if(previewRequest===requestToken){previewRequest=undefined;setBusy(false);}
      }
    });
    confirm.addEventListener('change',()=>{armButton.disabled=busy || submitted || !preview || preview.live_submission_enabled !== true || !confirm.checked;});
    armButton.addEventListener('click',async()=>{
      if(busy || submitted || !preview || preview.live_submission_enabled !== true || !confirm.checked) return;
      const reviewed=preview, submissionRevision=revision; submittedReview=reviewed; submitted=true;setBusy(true);
      status.textContent='Sending the confirmed entry and linked exits to the selected broker…';
      try {
        const result=await hooks.arm({preview_id:reviewed.preview_id,confirmation:reviewed.confirmation_phrase,
          account_id:context.account_id,broker:context.broker,mode:'LIVE'});
        if(submissionRevision!==revision)return;
        status.textContent=result.message || result.status || 'Broker status requires reconciliation.';
        text('[data-trade-arm]','Reconcile broker status');
        showCancellation(result);
        hooks.onSubmitted?.(result,reviewed);
      } catch(error) {
        if(submissionRevision===revision){
          status.textContent=error.message || 'Submission status is uncertain. Check broker orders before trying again.';
          hooks.onSubmitted?.({status:'SUBMISSION_UNCERTAIN',protection_confirmed:false,message:status.textContent},reviewed);
        }
      } finally {preview=undefined;setBusy(false);if(hooks.status && submittedReview){checkButton.hidden=false;checkStatus();}}
    });
    for (const name of ['input','change']) ticket.addEventListener(name,event=>{
      if(event.target.matches('[name]') && !busy && !submitted) {status.textContent='';invalidate();}
    });
    ticket.addEventListener('click',event=>{
      const pick=event.target.closest('[data-trade-pick]');
      if(pick && !busy && !submitted) hooks.pickLevel?.(pick.dataset.tradePick);
    });
    ticket.querySelector('[data-trade-close]').addEventListener('click',()=>{
      if(busy && !previewRequest) return;
      if(previewRequest){previewRequest=undefined;setBusy(false);}
      stopStatus();ticket.hidden=true;invalidate();hooks.cancelPick?.();
    });
    return {
      element:ticket,
      editable() { return !ticket.hidden && !busy && !submitted; },
      open(next) {
        if(busy) throw Error('Wait for the current broker request before changing the chart order.');
        stopStatus();context={...next};submitted=false;status.textContent='';ticket.hidden=false;
        text('[data-trade-title]',next.side+' · chart order');
        text('[data-trade-account]',next.account_name || next.broker);
        text('[data-trade-instrument]',next.symbol);
        field('product').replaceChildren(...next.products.map(product=>new Option(product,product)));
        configurePriceUnit(next.price_tick,next);
        field('quantity').step='1';field('quantity').min='1';
        field('quantity').value=next.quantity??'';
        for(const name of ['entry','stop_loss','target','limit_price'])showLevel(name,next[name]);
        field('entry_type').value=next.entry_type || 'LIMIT';
        ticket.querySelector('[data-trade-exit-trigger]').hidden=next.broker!=='DELTA_INDIA';
        field('exit_trigger_method').value=next.exit_trigger_method||'last_traded_price';
        if(next.product)field('product').value=next.product;
        invalidate();setBusy(false);
      },
      setLevel(name,value) {
        if(!['entry','stop_loss','target'].includes(name) || busy || submitted) return;
        showLevel(name,value);status.textContent='';invalidate();
      },
      invalidateSource() {
        stopStatus();ticket.hidden=true;revision++;preview=undefined;confirm.checked=false;armButton.disabled=true;hooks.cancelPick?.();
      },
      destroy() {stopStatus();revision++;ticket.remove();hooks.cancelPick?.();}
    };
  }
  root.SectorPulseChartTradeTicket={mount};
})(typeof window==='undefined'?globalThis:window);

