const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_TICKET_SOURCE||require.resolve('../chart-trade-ticket.js'),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(overrides={}) {
  const dom=new JSDOM('<main></main>',{runScripts:'outside-only'});
  dom.window.eval(source);
  const calls={prepare:0,arm:0};
  const hooks={
    async prepare(plan){calls.prepare++;return {preview_id:'review-1',confirmation_phrase:'CONFIRM review-1',live_submission_enabled:true,plan};},
    async arm(){calls.arm++;return {status:'BROKER_ACCEPTED',message:'Broker accepted. Fill and exits pending confirmation.'};},...overrides};
  const api=dom.window.SectorPulseChartTradeTicket.mount(dom.window.document.querySelector('main'),hooks);
  api.open({account_id:'account-a',broker:'FYERS',account_name:'FYERS · Algo',symbol:'NSE:TEST',side:'BUY',
            products:['INTRADAY'],product:'INTRADAY',quantity:65,entry:25,stop_loss:22,target:30});
  const el=api.element;
  const submit=()=>el.querySelector('form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
  const change=(name,value)=>{const field=el.querySelector('[name="'+name+'"]');field.value=value;field.dispatchEvent(new dom.window.Event('change',{bubbles:true}));};
  const confirm=()=>{const field=el.querySelector('[data-trade-confirm]');field.checked=true;field.dispatchEvent(new dom.window.Event('change',{bubbles:true}));};
  return {dom,api,el,calls,submit,change,confirm};
}
test('review uses exact levels and never submits an order',async()=>{
  const f=fixture();f.submit();await tick();
  assert.equal(f.calls.prepare,1);assert.equal(f.calls.arm,0);
  assert.equal(f.el.querySelector('[data-trade-review]').hidden,false);
  assert.equal(f.el.querySelector('[data-trade-arm]').disabled,true);
  assert.match(f.el.querySelector('dl').textContent,/25/);f.dom.window.close();
});
test('changing a marked level revokes the old confirmation',async()=>{
  const f=fixture();f.submit();await tick();f.confirm();
  assert.equal(f.el.querySelector('[data-trade-arm]').disabled,false);
  f.api.setLevel('stop_loss',21);
  assert.equal(f.el.querySelector('[data-trade-review]').hidden,true);
  assert.equal(f.el.querySelector('[data-trade-arm]').disabled,true);
  assert.equal(f.calls.arm,0);f.dom.window.close();
});
test('different account or changed price response cannot enable confirmation',async()=>{
  for(const change of [{account_id:'another-account'},{entry:'24.5'},{quantity:130},{product:'CNC'}]) {
    const f=fixture({async prepare(plan){return {preview_id:'review-1',confirmation_phrase:'CONFIRM review-1',plan:{...plan,...change}};}});
    f.submit();await tick();
    assert.equal(f.el.querySelector('[data-trade-review]').hidden,true);
    assert.equal(f.el.querySelector('[data-trade-arm]').disabled,true);
    assert.equal(f.calls.arm,0);f.dom.window.close();
  }
});
test('source change discards an in-flight preview',async()=>{
  let finish;
  const f=fixture({prepare(plan){return new Promise(resolve=>{finish=()=>resolve({preview_id:'review-1',confirmation_phrase:'CONFIRM review-1',plan});});}});
  f.submit();f.api.invalidateSource();finish();await tick();
  assert.equal(f.el.hidden,true);assert.equal(f.el.querySelector('[data-trade-review]').hidden,true);
  assert.equal(f.calls.arm,0);f.dom.window.close();
});
test('confirmed submission is sent once and never retried automatically',async()=>{
  const f=fixture();f.submit();await tick();f.confirm();
  f.el.querySelector('[data-trade-arm]').click();f.el.querySelector('[data-trade-arm]').click();await tick();
  assert.equal(f.calls.arm,1);
  assert.equal(f.el.querySelector('[data-trade-arm]').disabled,true);
  assert.match(f.el.querySelector('[data-trade-status]').textContent,/pending confirmation/);
  f.dom.window.close();
});
test('uncertain submission cannot be repeated from the same ticket',async()=>{
  let attempts=0;
  const f=fixture({async arm(){attempts++;throw Error('Broker response unknown; reconcile.');}});
  f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();
  f.el.querySelector('[data-trade-arm]').click();f.submit();await tick();
  assert.equal(attempts,1);
  assert.equal(f.el.querySelector('[data-trade-preview]').disabled,true);
  f.dom.window.close();
});


test('disabled or missing live permission never arms marked levels',async()=>{
  for(const enabled of [false,undefined]) {
    const f=fixture({async prepare(plan){return {preview_id:'review-1',confirmation_phrase:'CONFIRM review-1',live_submission_enabled:enabled,plan};}});
    f.submit();await tick();f.confirm();
    const arm=f.el.querySelector('[data-trade-arm]');
    assert.equal(arm.disabled,true);
    arm.dispatchEvent(new f.dom.window.Event('click',{bubbles:true}));
    await tick();assert.equal(f.calls.arm,0);
    assert.match(f.el.querySelector('[data-trade-status]').textContent,/Live trading is disabled/);
    f.dom.window.close();
  }
});

test('typing a new price immediately invalidates a reviewed order',async()=>{
 const f=fixture();f.submit();await tick();f.confirm();
 const price=f.el.querySelector('[name=entry]');price.value='24.5';
 price.dispatchEvent(new f.dom.window.Event('input',{bubbles:true}));
 assert.equal(f.el.querySelector('[data-trade-review]').hidden,true);
 assert.equal(f.el.querySelector('[data-trade-arm]').disabled,true);
 assert.equal(f.calls.arm,0);f.dom.window.close();
});

test('confirmed entry refreshes broker status without another placement',async()=>{
 let reads=0;
 const f=fixture({async status(){reads++;return {result:{status:'CLOSED',message:'Broker-linked exit filled.'}};}});
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 assert.equal(reads,1);assert.equal(f.calls.arm,1);
 assert.match(f.el.querySelector('[data-trade-status]').textContent,/exit filled/);
 assert.equal(f.el.querySelector('[data-trade-check]').hidden,false);
 f.api.destroy();f.dom.window.close();
});
test('failed status read never retries order placement',async()=>{
 let reads=0;
 const f=fixture({async status(){reads++;throw Error('Read unavailable. No order resent.');}});
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 assert.equal(f.calls.arm,1);assert.equal(reads,1);
 f.el.querySelector('[data-trade-check]').click();await tick();
 assert.equal(f.calls.arm,1);assert.equal(reads,2);
 f.api.destroy();f.dom.window.close();
});

test('exact comparison detects price changes below floating-point precision',async()=>{
 const f=fixture({async prepare(plan){return {preview_id:'review-1',confirmation_phrase:'CONFIRM review-1',
   live_submission_enabled:true,plan:{...plan,entry:'25.000000000000000002'}};}});
 f.change('entry','25.000000000000000001');f.submit();await tick();
 assert.equal(f.el.querySelector('[data-trade-review]').hidden,true);
 assert.match(f.el.querySelector('[data-trade-status]').textContent,/changed the marked prices/);
 assert.equal(f.calls.arm,0);f.dom.window.close();
});
test('small prices use exact whole ticks in fields, payload and review',async()=>{
 let sent;
 const f=fixture({async prepare(plan){sent=plan;return {preview_id:'p',confirmation_phrase:'CONFIRM p',
 live_submission_enabled:true,plan:{...plan,tick_size:'0.00000001',lot_size:1}};}});
 f.api.open({account_id:'account-a',broker:'DELTA_INDIA',account_name:'Delta test',symbol:'SMALLUSD',side:'BUY',
 products:['MARGIN'],price_tick:'0.00000001',quantity:1,entry:'0.00000123',stop_loss:'0.000001',target:'0.0000015'});
 assert.equal(f.el.querySelector('[name=entry]').value,'123');
 assert.match(f.el.querySelector('[data-trade-tick-unit]').textContent.replaceAll(',',''),/1 \/ 100000000/);
 f.submit();await tick();
 assert.equal(sent.entry,'0.00000123');assert.equal(sent.stop_loss,'0.000001');
 assert.equal(sent.target,'0.0000015');assert.match(f.el.querySelector('dl').textContent,/123 ticks/);
 f.api.setLevel('target','0.00000151');
 assert.equal(f.el.querySelector('[name=target]').value,'151');
 assert.equal(f.el.querySelector('[data-trade-review]').hidden,true);
 assert.equal(f.calls.arm,0);f.dom.window.close();
});
test('native preview tick replaces stale display units without changing order prices',async()=>{
 const f=fixture({async prepare(plan){return {preview_id:'p',confirmation_phrase:'CONFIRM p',live_submission_enabled:true,
 plan:{...plan,tick_size:'0.0000001',lot_size:1}};}});
 f.api.open({account_id:'account-a',broker:'DELTA_INDIA',symbol:'SMALLUSD',side:'BUY',products:['MARGIN'],
 price_tick:'0.00000001',quantity:1,entry:'0.0000012',stop_loss:'0.000001',target:'0.0000015'});
 f.submit();await tick();
 assert.equal(f.el.querySelector('[name=entry]').value,'12');
 assert.equal(f.el.querySelector('[name=stop_loss]').value,'10');
 assert.match(f.el.querySelector('dl').textContent,/12 ticks/);
 assert.equal(f.el.querySelector('[data-trade-review]').hidden,false);f.dom.window.close();
});
test('decimal helpers preserve ticks and large exact integer prices',()=>{
 const f=fixture(),p=f.dom.window.SectorPulseChartTradePrices;
 assert.equal(p.equal('1e-8','0.00000001'),true);
 assert.equal(p.equal('0.100000000000000001','0.100000000000000002'),false);
 assert.equal(p.fromTicks('123456789012345678','0.00000001'),'1234567890.12345678');
 assert.equal(p.ticks('1234567890.12345678','0.00000001'),'123456789012345678');
 assert.equal(p.snap('0.000001234','0.00000001'),'0.00000123');
 assert.equal(p.snap('0.000001236','0.00000001'),'0.00000124');
 assert.equal(p.rewardRisk('0.00000003','0.00000001','0.00000008'),'2.50');
 assert.equal(p.format('0.00000001').replaceAll(',',''),'1 / 100000000');
 assert.equal(p.format('25.05'),'25.05');f.dom.window.close();
});

test('failed native status clears a previously verified protection display',async()=>{
 const states=[];let reads=0;
 const f=fixture({onStatus:state=>states.push(state),async status(){
  if(++reads===1)return {result:{status:'OPEN',protection_confirmed:true}};
  throw Error('Connection unavailable');
 }});
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 assert.equal(states.at(-1).protection_confirmed,true);
 f.el.querySelector('[data-trade-check]').click();await tick();
 assert.equal(states.at(-1).status,'BROKER_STATUS_UNAVAILABLE');
 assert.equal(states.at(-1).protection_confirmed,false);
 assert.equal(f.calls.arm,1);f.api.destroy();f.dom.window.close();
});
test('lost submission acknowledgement publishes uncertainty without retry',async()=>{
 const states=[];
 const f=fixture({onSubmitted:state=>states.push(state),async arm(){throw Error('Request timed out');}});
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();
 assert.equal(states.at(-1).status,'SUBMISSION_UNCERTAIN');
 assert.equal(states.at(-1).protection_confirmed,false);
 assert.equal(f.el.querySelector('[data-trade-arm]').disabled,true);
 f.api.destroy();f.dom.window.close();
});

test('verified protection expires while a later native read is stalled',async()=>{
 const states=[];let reads=0;const timers=new Map();let seq=0;
 const f=fixture({onStatus:state=>states.push(state),async status(){
  if(++reads===1)return {result:{status:'POSITION_PROTECTED',protection_confirmed:true}};
  return new Promise(()=>{});
 }});
 f.dom.window.setTimeout=(fn,ms)=>{const id=++seq;timers.set(id,{fn,ms});return id;};
 f.dom.window.clearTimeout=id=>timers.delete(id);
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 assert.equal(states.at(-1).protection_confirmed,true);
 const expiry=[...timers.values()].find(t=>t.ms===20000);
 assert.ok(expiry);
 [...timers.values()].find(t=>t.ms===15000).fn();await tick();
 assert.equal(reads,2);
 expiry.fn();
 assert.equal(states.at(-1).status,'BROKER_STATUS_STALE');
 assert.equal(states.at(-1).protection_confirmed,false);
 assert.equal(f.calls.arm,1);
 f.api.destroy();f.dom.window.close();
});
test('changing source cancels the old protection freshness callback',async()=>{
 const states=[];const timers=new Map();let seq=0;
 const f=fixture({onStatus:state=>states.push(state),async status(){
  return {result:{status:'POSITION_PROTECTED',protection_confirmed:true}};
 }});
 f.dom.window.setTimeout=(fn,ms)=>{const id=++seq;timers.set(id,{fn,ms});return id;};
 f.dom.window.clearTimeout=id=>timers.delete(id);
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 const expiry=[...timers.values()].find(t=>t.ms===20000);
 f.api.invalidateSource();
 assert.equal(timers.size,0);
 const count=states.length;expiry.fn();assert.equal(states.length,count);
 f.api.destroy();f.dom.window.close();
});

test('an old account status request cannot block or unlock a newer request',async()=>{
 const states=[],pending=[];let reads=0;
 const f=fixture({onStatus:state=>states.push(state),status(){
  reads++;return new Promise(resolve=>pending.push(resolve));
 }});
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 assert.equal(reads,1);
 f.api.invalidateSource();
 f.api.open({account_id:'account-b',broker:'FYERS',symbol:'NSE:OTHER',side:'BUY',
 products:['INTRADAY'],quantity:65,entry:25,stop_loss:22,target:30});
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 assert.equal(reads,2);
 assert.equal(f.el.querySelector('[data-trade-check]').disabled,true);
 pending[0]({result:{status:'POSITION_PROTECTED',protection_confirmed:true}});
 await tick();
 assert.equal(states.length,0);
 assert.equal(f.el.querySelector('[data-trade-check]').disabled,true);
 pending[1]({result:{status:'ENTRY_PENDING',protection_confirmed:false}});
 await tick();
 assert.equal(states.length,1);assert.equal(states[0].status,'ENTRY_PENDING');
 assert.equal(f.el.querySelector('[data-trade-check]').disabled,false);
 assert.equal(f.calls.arm,2);f.api.destroy();f.dom.window.close();
});

function openDhan(f){
 f.api.open({account_id:'account-a',broker:'DHAN',symbol:'NSE_FNO:123',side:'BUY',products:['INTRADAY'],
 quantity:65,entry:25,stop_loss:22,target:30,entry_type:'STOP_LIMIT',limit_price:25.05});
}
test('waiting Dhan trigger has explicit local cancellation without another arm',async()=>{
 let arms=0,cancels=0;
 const f=fixture({async arm(){arms++;return {status:'WAITING_FOR_TRIGGER'};},
 async status(){return {result:{status:'WAITING_FOR_TRIGGER'}};},
 async cancelCondition(payload){cancels++;assert.equal(payload.account_id,'account-a');
 return {status:'CANCELLED',order_submitted:false,message:'Waiting trigger cancelled.'};}});
 openDhan(f);f.submit();await tick();
 assert.equal(f.el.querySelector('[data-trade-arm]').textContent,'Arm conditional entry');
 f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 const button=f.el.querySelector('[data-trade-cancel-condition]');
 assert.equal(button.hidden,false);button.click();button.click();await tick();
 assert.equal(cancels,1);assert.equal(arms,1);assert.equal(button.hidden,true);
 assert.match(f.el.querySelector('[data-trade-status]').textContent,/cancelled/);
 f.api.destroy();f.dom.window.close();
});
test('cancellation loses race to claim without cancelling or resending a broker order',async()=>{
 let cancels=0,arms=0,reads=0;
 const f=fixture({async arm(){arms++;return {status:'WAITING_FOR_TRIGGER'};},
 async status(){return {result:{status:++reads===1?'WAITING_FOR_TRIGGER':'SUBMISSION_UNCERTAIN'}};},
 async cancelCondition(){cancels++;throw Error('Entry was already claimed. Check broker status.');}});
 openDhan(f);f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 f.el.querySelector('[data-trade-cancel-condition]').click();await tick();await tick();
 assert.equal(cancels,1);assert.equal(arms,1);assert.equal(reads,2);
 assert.equal(f.el.querySelector('[data-trade-cancel-condition]').hidden,true);
 f.api.destroy();f.dom.window.close();
});
test('late waiting status cannot restore cancellation after local cancellation',async()=>{
 let reads=0,resolveOld;
 const f=fixture({async arm(){return {status:'WAITING_FOR_TRIGGER'};},
 status(){if(++reads===1)return Promise.resolve({result:{status:'WAITING_FOR_TRIGGER'}});
 return new Promise(resolve=>{resolveOld=resolve;});},
 async cancelCondition(){return {status:'CANCELLED',message:'Cancelled before submission'};}});
 openDhan(f);f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();await tick();await tick();
 f.el.querySelector('[data-trade-check]').click();await tick();
 f.el.querySelector('[data-trade-cancel-condition]').click();await tick();
 resolveOld({result:{status:'WAITING_FOR_TRIGGER'}});await tick();
 assert.equal(f.el.querySelector('[data-trade-cancel-condition]').hidden,true);
 assert.match(f.el.querySelector('[data-trade-status]').textContent,/Cancelled/);
 f.api.destroy();f.dom.window.close();
});
test('high-value review notice is shown as text',async()=>{
 const notice='Order value exceeds ₹50,000. <strong>Review quantity</strong>';
 const f=fixture({async prepare(plan){return {preview_id:'p',confirmation_phrase:'CONFIRM p',
 live_submission_enabled:true,plan,preflight:{notice}};}});
 f.submit();await tick();
 const node=f.el.querySelector('[data-trade-notice]');
 assert.equal(node.hidden,false);assert.equal(node.textContent,notice);assert.equal(node.querySelector('strong'),null);
 f.api.destroy();f.dom.window.close();
});


test('read-only preview can close and late response cannot revive it',async()=>{
 let finish;const f=fixture({prepare(plan){return new Promise(resolve=>finish=()=>resolve({preview_id:'late',confirmation_phrase:'CONFIRM late',live_submission_enabled:true,plan}));}});
 f.submit();f.el.querySelector('[data-trade-close]').click();assert.equal(f.el.hidden,true);
 finish();await tick();assert.equal(f.el.hidden,true);assert.equal(f.el.querySelector('[data-trade-review]').hidden,true);assert.equal(f.calls.arm,0);f.api.destroy();f.dom.window.close();
});
test('old closed preview cannot unlock a newer pending preview',async()=>{
 const finish=[];const f=fixture({prepare(plan){return new Promise(resolve=>finish.push(()=>resolve({preview_id:'p'+finish.length,confirmation_phrase:'CONFIRM',live_submission_enabled:true,plan})));}});
 f.submit();f.el.querySelector('[data-trade-close]').click();
 f.api.open({account_id:'account-a',broker:'FYERS',account_name:'FYERS · Algo',symbol:'NSE:TEST',side:'BUY',products:['INTRADAY'],product:'INTRADAY',quantity:65,entry:26,stop_loss:22,target:30});
 f.submit();finish[0]();await tick();assert.equal(f.el.querySelector('[data-trade-preview]').disabled,true);assert.equal(f.el.querySelector('[name="entry"]').disabled,true);
 finish[1]();await tick();assert.equal(f.el.querySelector('[data-trade-review]').hidden,false);assert.match(f.el.querySelector('dl').textContent,/26/);assert.equal(f.calls.arm,0);f.api.destroy();f.dom.window.close();
});
test('late preview error cannot replace a new draft message',async()=>{
 let reject;const f=fixture({prepare(){return new Promise((_,no)=>reject=no);}});
 f.submit();f.el.querySelector('[data-trade-close]').click();
 f.api.open({account_id:'account-a',broker:'FYERS',symbol:'NSE:TEST',side:'BUY',products:['INTRADAY'],quantity:65,entry:26,stop_loss:22,target:30});
 reject(Error('Old quote unavailable'));await tick();assert.equal(f.el.querySelector('[data-trade-status]').textContent,'');assert.equal(f.el.hidden,false);f.api.destroy();f.dom.window.close();
});
test('close guard remains during financial submission',async()=>{
 let finish;const f=fixture({arm(){return new Promise(resolve=>finish=()=>resolve({status:'BROKER_ACCEPTED',message:'Accepted'}));}});
 f.submit();await tick();f.confirm();f.el.querySelector('[data-trade-arm]').click();f.el.querySelector('[data-trade-close]').click();
 assert.equal(f.el.hidden,false);finish();await tick();assert.equal(f.el.querySelector('[data-trade-arm]').disabled,true);f.api.destroy();f.dom.window.close();
});
