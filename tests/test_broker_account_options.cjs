const test=require('node:test');
const assert=require('node:assert/strict');
const {choices}=require('../broker-account-options.js');
const accounts=[
 {id:'f',broker:'FYERS',label:'Personal FYERS',configured:true},
 {id:'d',broker:'DHAN',label:'Personal Dhan',configured:true,parser_supported:true,strategy_routes:['renko','rsi','band','kama']},
 {id:'x',broker:'DELTA_INDIA',label:'Crypto',configured:true,parser_supported:true},
 {id:'u',broker:'DHAN',label:'Incomplete',configured:false}
];
test('manual lists every owned account but supports owned FYERS workspaces and the Dhan manual adapter',()=>{
 const result=choices(accounts,{kind:'manual'});
 assert.equal(result.length,4);
 assert.equal(result[1].value,'dhan:d');assert.equal(result[1].disabled,false);
 assert.equal(result[0].disabled,false);assert.equal(result[2].disabled,true);assert.equal(result[3].disabled,true);
});
test('strategies expose Dhan as manual only without enabling a false route',()=>{
 const result=choices(accounts,{kind:'strategy',currentBroker:'FYERS'});
 assert.equal(result[1].disabled,true);assert.match(result[1].label,/manual orders only/);
 assert.equal(result[0].disabled,true);assert.equal(result[2].disabled,true);
});
test('only current private workspace account can represent its strategy credentials',()=>{
 const result=choices(accounts,{currentBroker:'FYERS',workspaceId:'f'});
 assert.equal(result[0].disabled,false);assert.equal(result[0].same,true);
 assert.equal(result[1].disabled,true);
});
test('Delta manual forms cannot silently become Dhan or FYERS orders',()=>{
 const result=choices(accounts,{kind:'delta-manual',currentBroker:'DELTA_INDIA',workspaceId:'x'});
 assert.equal(result[2].disabled,false);assert.equal(result[1].disabled,true);assert.equal(result[0].disabled,true);
});
test('account labels are data and unconfigured credentials stay disabled',()=>{
 const row=choices([{id:'z',broker:'DHAN',label:'<script>',configured:false}],{kind:'manual'})[0];
 assert.equal(row.disabled,true);assert.match(row.label,/connection settings incomplete/);
});

test('Dhan Renko and RSI options route to an owned strategy account',()=>{
 for(const kind of ['renko','rsi','band','kama']){
  const result=choices(accounts,{kind});
  assert.equal(result[1].disabled,false);
  assert.equal(result[1].value,'account:d');
  assert.equal(result[3].disabled,true);
 }
});

test('strategy accounts remain disabled until loaded backend advertises the route',()=>{
 assert.equal(choices([{id:'d',broker:'DHAN',label:'Dhan',configured:true,parser_supported:true}],{kind:'renko'})[0].disabled,true);
});

test('Renko lists configured FYERS and Delta workspaces as selectable accounts',()=>{
 const result=choices(accounts,{kind:'renko'});
 assert.equal(result[0].disabled,false);assert.equal(result[2].disabled,false);
});

test('sector rotation allows every configured supported broker account',()=>{
 const result=choices(accounts,{kind:'sector'});
 assert.equal(result.find(r=>r.id==='f').disabled,false);assert.equal(result.find(r=>r.id==='d').disabled,false);assert.equal(result.some(r=>r.broker==='DELTA_INDIA'),false);assert.equal(result.find(r=>r.id==='u').disabled,true);
});

test('Live feed enables configured Dhan accounts without enabling Delta',()=>{
 const rows=choices([{id:'d',broker:'DHAN',label:'D',configured:true},{id:'x',broker:'DELTA_INDIA',label:'X',configured:true}],{kind:'account'});
 assert.equal(rows[0].disabled,false);assert.equal(rows[1].disabled,true);
});

test('Trade Parser lists configured owned brokers and rejects incomplete connections',()=>{
 const rows=choices([{id:'f',broker:'FYERS',label:'Algo',configured:true},{id:'d',broker:'DHAN',label:'Dhan',configured:true,parser_supported:true},{id:'x',broker:'DELTA_INDIA',label:'Crypto',configured:true,parser_supported:true},{id:'bad',broker:'FYERS',configured:false}],{kind:'parser'});
 assert.deepEqual(rows.map(r=>r.disabled),[false,false,false,true]);
});
test('configured Dhan Screener is selectable only after read-only backend capability is advertised',()=>{
 const a={id:'mine',broker:'DHAN',label:'Algo',configured:true,screener_read_only:true};
 assert.equal(choices([a],{kind:'screener',currentBroker:'FYERS'})[0].disabled,false);
 assert.equal(choices([{...a,screener_read_only:false}],{kind:'screener'})[0].disabled,true);
 assert.equal(choices([{...a,configured:false}],{kind:'screener'})[0].disabled,true);
});
test('Parser and Live Feed use valid owned context, sole Dhan, or explicit selection for multiple accounts',()=>{
 const {accountSelection}=require('../broker-account-options.js');
 const rows=choices(accounts,{kind:'parser'});
 assert.equal(accountSelection(rows),null);
 assert.equal(accountSelection(rows,{requestedId:'d'}).id,'d');
 assert.equal(accountSelection(rows,{requestedId:'someone-else'}),null);
 assert.equal(accountSelection(rows,{previousValue:'account:d'}).id,'d');
 assert.equal(accountSelection(rows,{previousValue:'account:deleted'}),null);
 assert.equal(accountSelection(rows.filter(r=>r.id==='d')).id,'d');
 assert.equal(accountSelection(rows,{workspaceId:'f'}).id,'f');
});
