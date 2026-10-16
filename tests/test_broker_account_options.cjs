const test=require('node:test');
const assert=require('node:assert/strict');
const {choices}=require('../broker-account-options.js');
const accounts=[
 {id:'f',broker:'FYERS',label:'Personal FYERS',configured:true},
 {id:'d',broker:'DHAN',label:'Personal Dhan',configured:true,strategy_routes:['renko','rsi','band','kama']},
 {id:'x',broker:'DELTA_INDIA',label:'Crypto',configured:true},
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
 assert.equal(choices([{id:'d',broker:'DHAN',label:'Dhan',configured:true}],{kind:'renko'})[0].disabled,true);
});

test('Renko lists configured FYERS and Delta workspaces as selectable accounts',()=>{
 const result=choices(accounts,{kind:'renko'});
 assert.equal(result[0].disabled,false);assert.equal(result[2].disabled,false);
});

test('sector rotation allows every configured supported broker account',()=>{
 const result=choices(accounts,{kind:'sector'});
 assert.equal(result[0].disabled,false);assert.equal(result[1].disabled,false);assert.equal(result[2].disabled,false);assert.equal(result[3].disabled,true);
});

test('Live feed enables configured Dhan accounts without enabling Delta',()=>{
 const rows=choices([{id:'d',broker:'DHAN',label:'D',configured:true},{id:'x',broker:'DELTA_INDIA',label:'X',configured:true}],{kind:'account'});
 assert.equal(rows[0].disabled,false);assert.equal(rows[1].disabled,true);
});

test('parser enables configured FYERS from main portal without enabling other brokers',()=>{
 const rows=choices([{id:'f',broker:'FYERS',label:'Algo',configured:true},{id:'d',broker:'DHAN',label:'Dhan',configured:true},{id:'x',broker:'DELTA_INDIA',label:'Crypto',configured:true},{id:'bad',broker:'FYERS',configured:false}],{kind:'parser'});
 assert.deepEqual(rows.map(r=>r.disabled),[false,true,true,true]);
});
