const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs');const {JSDOM}=require('jsdom');
const code=fs.readFileSync('multi-account-orders.js','utf8');
async function setup(extraAccounts=[]){
 const dom=new JSDOM('<input id="handoff-allocation-budget" value="50000"><section id="ticket-panel"></section><section id="handoff-batch-panel"></section><section id="screener-order"></section><input id="parser-native-budget" value="50000"><section id="trade-parser-order"><button id="trade-parser-submit-order">Submit order</button></section><input id="manual-order-amount" value="50000"><form id="order"><select id="account"><option value="b" selected>Dhan</option></select><input name="quantity" required></form>',{url:'https://example.test/',runScripts:'outside-only'});
 const w=dom.window;w.structuredClone=structuredClone;let sent;
 w.BrokerForms={ready:Promise.resolve(),account:()=>({id:'a'})};
 w.fetch=async(url,options)=>{if(url.includes('/api/workspaces/accounts'))return {ok:true,json:async()=>({accounts:[{id:'a',label:'Primary',broker:'FYERS'},{id:'b',label:'Second',broker:'DHAN'},...extraAccounts]})};
 if(options){sent=JSON.parse(options.body);return {ok:true,json:async()=>({batch_id:'MULTI-1',confirmation_phrase:'CONFIRM',rows:sent.items.map(i=>({account_id:i.account_id,label:i.account_id,broker:'FYERS',state:'READY',allocation:{amount:Number(i.amount),reserved:99.123,unspent:1.234},preview:{items:[{instrument:{contracts:[{symbol:'EXACT',quantity:65,limit_price:99.12}]}}],price:99.123}}))})};}
 return {ok:true,json:async()=>({batches:[]})};};
 w.eval(code);w.document.dispatchEvent(new w.Event('DOMContentLoaded'));await new Promise(r=>setImmediate(r));
 return {w,dom,sent:()=>sent};
}
test('only current account is initially selected in every mounted form',async()=>{const {w,dom}=await setup();for(const list of w.document.querySelectorAll('.multi-account-list'))assert.deepEqual([...list.querySelectorAll('input[type=checkbox]')].map(e=>e.checked),list.closest('#order')?[false,true]:[true,false]);dom.window.close();});
test('same amount applies independently and overrides are explicit',async()=>{const {w,dom,sent}=await setup();const host=w.document.getElementById('ticket-panel');const toggle=host.querySelector('.multi-account-ticket>label input');toggle.checked=true;toggle.dispatchEvent(new w.Event('change'));
 const rows=host.querySelectorAll('.multi-account-row');rows[1].querySelector('input').checked=true;
 await w.MultiAccountOrders.prepare('ticket-panel',{proposal:{kind:'EQUITY'}});
 assert.deepEqual(sent().items.map(i=>Number(i.amount)),[50000,50000]);
 rows[1].querySelectorAll('input')[1].value='25000';
 await w.MultiAccountOrders.prepare('ticket-panel',{proposal:{kind:'EQUITY'}});
 assert.deepEqual(sent().items.map(i=>Number(i.amount)),[50000,25000]);
 assert(!host.querySelector('pre').textContent.includes('99.123'));dom.window.close();});
test('no ticked accounts blocks preparation',async()=>{const {w,dom}=await setup();const host=w.document.getElementById('ticket-panel');const t=host.querySelector('.multi-account-ticket>label input');t.checked=true;t.dispatchEvent(new w.Event('change'));host.querySelectorAll('.multi-account-row input[type=checkbox]').forEach(e=>e.checked=false);await assert.rejects(w.MultiAccountOrders.prepare('ticket-panel',{}),/Tick at least/);dom.window.close();});

test('broker-wise pools group multiple accounts without duplicating the broker',async()=>{
 const {w,dom,sent}=await setup([{id:'a2',label:'Alternate FYERS',broker:'FYERS'}]);
 const host=w.document.getElementById('ticket-panel'),rows=host.querySelectorAll('.multi-account-row');
 assert.equal(rows.length,2);assert.equal(rows[0].querySelector('select').options.length,2);
 const toggle=host.querySelector('.multi-account-ticket>label input');toggle.checked=true;toggle.dispatchEvent(new w.Event('change'));
 const select=rows[0].querySelector('select');select.value='a2';select.dispatchEvent(new w.Event('change'));
 await w.MultiAccountOrders.prepare('ticket-panel',{proposal:{kind:'EQUITY'}});
 assert.deepEqual(sent().items.map(i=>i.account_id),['a2']);assert.equal(Number(sent().items[0].amount),50000);dom.window.close();
});
test('manual parser gets a review step and standalone ticket suppresses quantity-first input',async()=>{
 const {w,dom,sent}=await setup();
 const parser=w.document.getElementById('trade-parser-order'),toggle=parser.querySelector('.multi-account-ticket>label input');
 toggle.checked=true;toggle.dispatchEvent(new w.Event('change'));
 assert.match(w.document.getElementById('trade-parser-submit-order').textContent,/Prepare selected/);
 await w.MultiAccountOrders.prepare('trade-parser-order',{_manual_parser:true,source_account_id:'a',text:'BUY ABC AT 100 SL 90 TARGET 120'});
 assert.equal(sent().flow,'trade-parser');assert.equal(Number(sent().items[0].amount),50000);
 const native=w.document.getElementById('order'),nativeToggle=native.querySelector('.multi-account-ticket>label input');
 nativeToggle.checked=true;nativeToggle.dispatchEvent(new w.Event('change'));
 assert.equal(native.querySelector('[name=quantity]').disabled,true);
 nativeToggle.checked=false;nativeToggle.dispatchEvent(new w.Event('change'));
 assert.equal(native.querySelector('[name=quantity]').disabled,false);dom.window.close();
});
