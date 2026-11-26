const test=require('node:test'),assert=require('node:assert/strict');
const {instrumentSettingsKey,readInstrumentSettings,writeInstrumentSettings}=require('../renko-ai-options.js');
const account={id:'a'.repeat(32),broker:'FYERS'};
function storage(){const map=new Map();return {getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),map};}
test('preferences isolate user, broker, account and exact instrument',()=>{
 const store=storage(),v={underlying:'MCX:ONE',factor:2.5,timeframe:'5 minutes',chartView:'Renko',reference:999,session:'old',evidence:'old',manualParent:300,manualParentAt:123};
 writeInstrumentSettings(store,'alice',account,v);
 const saved=readInstrumentSettings(store,'alice',account,'MCX:ONE');
 assert.equal(saved.factor,2.5);assert.equal(saved.manualParentAt,123);
 assert.equal(saved.reference,undefined);assert.equal(saved.session,undefined);
 for(const [u,a,s] of [['bob',account,'MCX:ONE'],['alice',{...account,id:'b'.repeat(32)},'MCX:ONE'],['alice',{...account,broker:'DHAN'},'MCX:ONE'],['alice',account,'MCX:TWO']])assert.equal(readInstrumentSettings(store,u,a,s),null);
 assert.equal(instrumentSettingsKey('',account,'MCX:ONE'),null);
});
test('returning to an instrument restores its own last values',()=>{
 const store=storage();
 writeInstrumentSettings(store,'alice',account,{underlying:'MCX:ONE',factor:2.5});
 writeInstrumentSettings(store,'alice',account,{underlying:'MCX:TWO',factor:3});
 writeInstrumentSettings(store,'alice',account,{underlying:'MCX:ONE',factor:1.25});
 assert.equal(readInstrumentSettings(store,'alice',account,'MCX:ONE').factor,1.25);
 assert.equal(readInstrumentSettings(store,'alice',account,'MCX:TWO').factor,3);
});
test('tampered or malformed profile identity is ignored',()=>{
 const store=storage(),key=instrumentSettingsKey('alice',account,'MCX:ONE');
 store.setItem(key,'bad json');assert.equal(readInstrumentSettings(store,'alice',account,'MCX:ONE'),null);
 store.setItem(key,JSON.stringify({user:'bob',account:account.id,broker:'FYERS',symbol:'MCX:ONE',settings:{factor:9}}));assert.equal(readInstrumentSettings(store,'alice',account,'MCX:ONE'),null);
});

test('new instruments use defaults and returning instruments use only their own profile',()=>{
 const {restoredInstrumentValues}=require('../renko-ai-options.js');
 const defaults={factor:3,manualParent:'',manualParentAt:null,calculationMode:'RENKO',timeframe:'1 minute'};
 assert.deepEqual(restoredInstrumentValues(defaults,null,'NEW'),{...defaults,underlying:'NEW'});
 const saved={factor:1.25,manualParent:300,manualParentAt:123,timeframe:'5 minutes'};
 assert.deepEqual(restoredInstrumentValues(defaults,saved,'OLD'),{...defaults,...saved,underlying:'OLD'});
});

test('legacy instrument profile restores the only permitted FYERS data account without guessing between accounts',()=>{
 const {restoredDataAccount}=require('../renko-ai-options.js');
 const a={id:'one',broker:'FYERS'},b={id:'two',broker:'FYERS'};
 assert.equal(restoredDataAccount('',[a]),'one');
 assert.equal(restoredDataAccount('one',[a,b]),'one');
 assert.equal(restoredDataAccount('obsolete',[a]),'one');
 assert.equal(restoredDataAccount('',[a,b]),'');
 assert.equal(restoredDataAccount('one',[{id:'one',broker:'DHAN'}]),'');
});
