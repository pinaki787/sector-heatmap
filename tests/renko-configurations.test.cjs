const {test}=require('node:test'),assert=require('node:assert/strict');
const {configurationLibrary,chooseConfiguration,storeConfiguration,deleteConfiguration,restoredConfigurationFields}=require('../renko-supertrend.js');
const record=(symbol,name,saved_at)=>({symbol,name,id:JSON.stringify([symbol,name]),saved_at,settings:{symbol,mode:'LIVE',period:saved_at}});
test('legacy duplicates consolidate deterministically and retain preferred selection',()=>{
 const old={schema_version:1,records:[record('ETHUSD','old',1),record('ETHUSD','preferred',2),record('ETHUSD','new',3),record('BTCUSD','Previously saved · BTCUSD · server draft',4)],preferred:{ETHUSD:JSON.stringify(['ETHUSD','preferred'])}};
 const library=configurationLibrary(old);assert.equal(library.records.length,2);assert.equal(chooseConfiguration(library,'ETHUSD').settings.period,2);assert.equal(chooseConfiguration(library,'BTCUSD').name,'BTCUSD');assert.equal(old.records.length,4);assert.deepEqual(configurationLibrary(library),library);
});
test('repeated saves and renames update one instrument without touching another',()=>{
 let lib=configurationLibrary(null);for(let i=0;i<10;i++){lib=storeConfiguration(lib,'Name '+i,{symbol:'ETHUSD',period:i},i);lib=storeConfiguration(lib,'Bitcoin',{symbol:'BTCUSD'},i);lib=configurationLibrary(JSON.parse(JSON.stringify(lib)));}
 assert.equal(lib.records.length,2);assert.equal(chooseConfiguration(lib,'ETHUSD').settings.period,9);assert.equal(chooseConfiguration(lib,'ETHUSD').name,'Name 9');
 const current={mode:'PAPER',symbol:'ETHUSD'};assert.equal(restoredConfigurationFields(current,chooseConfiguration(lib,'ETHUSD')).mode,'PAPER');
 lib=deleteConfiguration(lib,chooseConfiguration(lib,'ETHUSD').id);assert.ok(lib.deleted_symbols.includes('ETHUSD'));assert.equal(chooseConfiguration(lib,'ETHUSD'),null);
 lib=storeConfiguration(lib,'Again',{symbol:'ETHUSD'},20);assert.ok(!lib.deleted_symbols.includes('ETHUSD'));assert.equal(lib.records.length,2);
});
