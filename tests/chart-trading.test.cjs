const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(options={}){
 const dom=new JSDOM('<main><div class="sp-chart-quote-line"></div><div class="sp-chart-content"><div class="sp-chart-stage"></div></div></main>',{runScripts:'outside-only'});
 for(const name of ['chart-trade-ticket.js','chart-trading.js'])dom.window.eval(fs.readFileSync(name,'utf8'));
 let ticketHooks;
 const mountTicket=dom.window.SectorPulseChartTradeTicket.mount;
 dom.window.SectorPulseChartTradeTicket.mount=(host,hooks)=>{ticketHooks=hooks;return mountTicket(host,hooks);};
 dom.window.SectorPulseWorkspace={csrf:'csrf-test'};
 const sent=[],created=[],removed=[],primitives=[];
 dom.window.fetch=async(url,options)=>{const payload=JSON.parse(options.body);sent.push({url,options,payload});
 return {ok:true,json:async()=>({preview_id:'p1',confirmation_phrase:'CONFIRM p1',plan:payload,live_submission_enabled:true})};};
 const host=dom.window.document.querySelector('main');
 let symbol='NSE:TEST';
 const api=dom.window.SectorPulseChartTrading.mount(host,{symbol:()=>symbol,tick:options.tick||(()=>.05)});
 api.source({prefix:'/broker-workspace/account-a',account_id:'account-a',broker:'FYERS',account_name:'Algo',available:true,permitted:true});
 const series={createPriceLine(value){created.push(value);return value;},removePriceLine(value){removed.push(value);},coordinateToPrice:y=>y,priceToCoordinate:p=>p,attachPrimitive:p=>primitives.push(p),detachPrimitive:p=>{const i=primitives.indexOf(p);if(i>=0)primitives.splice(i,1);}};
 api.attach(series);
 return {dom,host,api,sent,created,removed,series,primitives,ticketHooks,setSymbol:v=>symbol=v};
}
test('marked levels stay draft and route preview to exact chart account',async()=>{
 const f=fixture();f.host.querySelector('[data-trade-side=BUY]').click();
 const form=f.host.querySelector('form');
 form.querySelector('[name=quantity]').value=65;
 for(const [key,y]of [['entry',25.023],['stop_loss',22.009],['target',30.001]]){
  f.host.querySelector('[data-trade-pick="'+key+'"]').click();
  assert.equal(f.api.pick({y}),true);
 }
 assert.equal(f.sent.length,0);
 assert.ok(f.created.every(v=>v.title.startsWith('DRAFT')));
 assert.equal(form.querySelector('[name=entry]').value,'25');
 form.dispatchEvent(new f.dom.window.Event('submit',{cancelable:true,bubbles:true}));await tick();
 assert.equal(f.sent.length,1);
 assert.equal(f.sent[0].url,'/broker-workspace/account-a/api/chart-workspace/trading/prepare');
 assert.equal(f.sent[0].options.headers['X-CSRF-Token'],'csrf-test');
 assert.equal(f.sent[0].payload.account_id,'account-a');
 assert.equal(f.sent[0].payload.stop_loss,'22');
 assert.equal(f.sent[0].payload.target,'30');
 f.dom.window.close();
});
test('source change revokes ticket, old levels and order confirmation',()=>{
 const f=fixture();f.host.querySelector('[data-trade-side=SELL]').click();
 f.host.querySelector('[data-trade-pick=entry]').click();f.api.pick({y:25});
 assert.ok(f.created.length);
 f.api.source({available:false,permitted:true,reason:'Choose a broker'});
 assert.equal(f.host.querySelector('aside').hidden,true);
 assert.ok(f.removed.length);
 assert.equal(f.host.querySelector('[data-trade-side=BUY]').disabled,true);
 assert.equal(f.api.pick({y:30}),false);
 assert.equal(f.sent.length,0);f.dom.window.close();
});
test('Escape cancels picking and rebuilding chart preserves draft prices',()=>{
 const f=fixture();f.host.querySelector('[data-trade-side=BUY]').click();
 f.host.querySelector('[data-trade-pick=entry]').click();f.api.pick({y:25});
 const count=f.created.length;f.api.attach(f.series);assert.ok(f.created.length>count);
 f.host.querySelector('[data-trade-pick=target]').click();
 f.host.dispatchEvent(new f.dom.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
 assert.equal(f.api.pick({y:30}),false);
 assert.equal(f.host.querySelector('[name=target]').value,'');
 f.dom.window.close();
});

test('dragging a draft price invalidates review and cannot send an order',async()=>{
 const f=fixture();f.host.querySelector('[data-trade-side=BUY]').click();
 const form=f.host.querySelector('form');
 for(const [name,value]of [['quantity',65],['entry',25],['stop_loss',22],['target',40]]) {
  const input=form.querySelector('[name='+name+']');input.value=value;
  input.dispatchEvent(new f.dom.window.Event('change',{bubbles:true}));
 }
 form.dispatchEvent(new f.dom.window.Event('submit',{cancelable:true,bubbles:true}));await tick();
 assert.equal(f.host.querySelector('[data-trade-review]').hidden,false);
 const stage=f.host.querySelector('.sp-chart-stage');
 function pointer(name,y){const event=new f.dom.window.MouseEvent(name,{clientY:y,button:0,bubbles:true,cancelable:true});
 Object.defineProperty(event,'pointerId',{value:1});stage.dispatchEvent(event);}
 pointer('pointerdown',40);pointer('pointermove',42.024);pointer('pointerup',42);
 assert.equal(form.querySelector('[name=target]').value,'42');
 assert.equal(f.host.querySelector('[data-trade-review]').hidden,true);
 assert.equal(f.sent.length,1);assert.ok(f.sent[0].url.endsWith('/prepare'));
 f.dom.window.close();
});

test('tiny chart prices snap without fixed-decimal rounding and show exact tick labels',()=>{
 const f=fixture({tick:()=>1e-12});f.host.querySelector('[data-trade-side=BUY]').click();
 f.host.querySelector('[data-trade-pick=entry]').click();f.api.pick({y:1.4e-12});
 assert.equal(f.host.querySelector('[name=entry]').value,'1');
 assert.equal(f.created.at(-1).price,1e-12);
 assert.equal(f.created.at(-1).axisLabelVisible,false);
 const labels=[];
 f.primitives.at(-1).paneViews()[0].renderer().draw({useMediaCoordinateSpace(draw){
   draw({mediaSize:{width:400,height:300},context:{save(){},restore(){},measureText:text=>({width:text.length*6}),
     fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillText:text=>labels.push(text)}});
 }});
 assert.match(labels[0],/DRAFT E 1t/);
 assert.equal(f.sent.length,0);f.api.invalidate();
 assert.equal(f.primitives.length,0);f.dom.window.close();
});

test('native marker state never treats acknowledgement as fill or stale protection as current',()=>{
 const f=fixture();f.host.querySelector('[data-trade-side=BUY]').click();
 f.host.querySelector('[data-trade-pick=entry]').click();f.api.pick({y:25});
 f.ticketHooks.onSubmitted({status:'ACCEPTED'});
 assert.match(f.created.at(-1).title,/VERIFY STATUS/);
 assert.equal(f.created.at(-1).price,25);
 f.ticketHooks.onStatus({status:'ENTRY_PENDING',protection_confirmed:false});
 assert.match(f.created.at(-1).title,/PENDING/);
 f.ticketHooks.onStatus({status:'OPEN',protection_confirmed:true});
 assert.match(f.created.at(-1).title,/PROTECTED/);
 f.ticketHooks.onStatus({status:'BROKER_STATUS_UNAVAILABLE',protection_confirmed:false});
 assert.match(f.created.at(-1).title,/VERIFY STATUS/);
 f.ticketHooks.onStatus({status:'CLOSED',protection_confirmed:true});
 assert.match(f.created.at(-1).title,/^CLOSED/);
 assert.equal(f.sent.length,0);f.dom.window.close();
});

test('armed conditional entry keeps stop and target visibly planned',()=>{
 const f=fixture();f.host.querySelector('[data-trade-side=BUY]').click();
 for(const [key,y]of [['entry',25],['stop_loss',22],['target',30]]){
  f.host.querySelector('[data-trade-pick='+key+']').click();f.api.pick({y});
 }
 f.ticketHooks.onSubmitted({status:'WAITING_FOR_TRIGGER',protection_confirmed:false});
 const lines=f.created.slice(-3);
 assert.match(lines[0].title,/^ARMED · Entry/);
 assert.match(lines[1].title,/^PLANNED · Stop loss/);
 assert.match(lines[2].title,/^PLANNED · Target/);
 f.ticketHooks.onStatus({status:'REVIEW_REQUIRED',protection_confirmed:false});
 assert.ok(f.created.slice(-3).every(line=>line.title.startsWith('REVIEW REQUIRED')));
 f.dom.window.close();
});
test('show marked levels is explicit and never submits or alters draft prices',()=>{
 const f=fixture(),fits=[];
 f.api.attach(f.series,undefined,undefined,levels=>fits.push([...levels]));
 f.host.querySelector('[data-trade-side=BUY]').click();
 const fit=f.host.querySelector('[data-trade-fit]');fit.click();assert.equal(fits.length,0);
 for(const [key,y] of [['entry',25],['stop_loss',22],['target',30]]){
  f.host.querySelector('[data-trade-pick="'+key+'"]').click();f.api.pick({y});
 }
 assert.equal(fits.length,0);fit.click();assert.deepEqual(fits,[[25,22,30]]);
 assert.equal(f.sent.length,0);assert.equal(f.host.querySelector('[name=entry]').value,'25');
 f.api.source({available:false});fit.click();assert.equal(fits.length,1);
 f.dom.window.close();
});
