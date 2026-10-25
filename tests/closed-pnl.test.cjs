const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const dom=new JSDOM('<select id="live-feed-broker-account"><option value="one">one</option></select><div id="host"></div>',{runScripts:'outside-only'});
dom.window.eval(fs.readFileSync('closed-pnl.js','utf8'));
const api=dom.window.ClosedPnl;
for(const [first,last,level] of [['2026-10-01','2026-10-24','week'],['2026-04-01','2026-10-24','month'],['2026-10-19','2026-10-24','day']]){
 const nodes=api.children(first,last,level).reverse();assert.equal(nodes[0].first,first);assert.equal(nodes.at(-1).last,last);
 for(let i=1;i<nodes.length;i++)assert.equal(new Date(nodes[i].first)-new Date(nodes[i-1].last),86400000);
}
const report={broker:'FYERS',currency:'INR',hierarchy_supported:true,supported:true,from_date:'2026-10-19',to_date:'2026-10-24',summary:{gross_pnl:100,charges:20,net_pnl:80},records:[{symbol:'<img src=x onerror=alert(1)>',category:'NSE · Stock options',pnl:100,buy_rate:1.123456,sell_rate:2.34567,buy_qty:10,sell_qty:10}]};
const host=dom.window.document.getElementById('host');let requests=0;
api.render(host,report,'weekly',async url=>{requests++;const u=new URL(url,'https://example.test');return {...report,from_date:u.searchParams.get('from_date'),to_date:u.searchParams.get('to_date')};});
assert.equal(host.querySelectorAll('img').length,0);assert.match(host.textContent,/80.00/);
const root=host.querySelector('details');root.open=true;
setTimeout(()=>{
 assert.equal(root.querySelectorAll('details').length,6);
 assert.ok(requests<=6);
 api.render(host,report,'weekly',async()=>{throw Error('unused');});assert.equal(host.querySelector('details'),root);assert.ok(root.open);
 host.querySelectorAll('.cp-segment')[1].click();assert.match(host.querySelector('.cp-metrics').textContent,/Not supplied/);assert.match(host.querySelector('summary strong').textContent,/gross/);
 console.log('date partition, hierarchy, filter accounting, escaping and refresh preservation passed');
},60);
