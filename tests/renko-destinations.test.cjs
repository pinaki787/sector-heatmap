const {test}=require('node:test'),assert=require('node:assert/strict');
const {DESTINATION_RULES,migrateDestinations,chartSettings,signalSettings,restoredConfigurationFields,configurationText}=require('../renko-supertrend.js');
const base={'atr-length':5,factor:3,'brick-mode':'Auto','manual-brick':10,'adx-threshold':20,'adx-length':14,'adx-smoothing':14,'widening-window':2};
for(const id of DESTINATION_RULES)for(const [strategy,indicator] of [[true,false],[false,true],[true,true],[false,false]])test(`${id}: strategy ${strategy}, indicator ${indicator}`,()=>{
 const fields={...base,[id]:strategy,[id+'-indicator']:indicator};const key=id.replaceAll('-','_');
 assert.equal(signalSettings(fields)[key],strategy);assert.equal(chartSettings(fields)[key],indicator);
 assert.equal(signalSettings(fields)[key+'_indicator'],indicator);
 assert.equal(fields[id],strategy);
});
test('legacy migration follows each saved switch, while explicit independent selections survive',()=>{
 const legacy={...base,'supertrend-enabled':false,'ema-fast-enabled':true,'rsi-exit-enabled':true};
 const migrated=migrateDestinations(legacy);assert.equal(migrated['supertrend-enabled-indicator'],false);assert.equal(migrated['ema-fast-enabled-indicator'],true);assert.equal(migrated['rsi-exit-enabled-indicator'],true);
 const restored=restoredConfigurationFields({...base,mode:'PAPER','supertrend-enabled-indicator':true},{symbol:'ETHUSD',settings:legacy});assert.equal(restored['supertrend-enabled-indicator'],false);
 const explicit=migrateDestinations({...legacy,'supertrend-enabled-indicator':true});assert.equal(explicit['supertrend-enabled-indicator'],true);assert.equal(explicit['supertrend-enabled'],false);
});
test('export preserves independently selected draft and active destinations',()=>{
 const fields={...base,'supertrend-enabled':false,'supertrend-enabled-indicator':true};
 const requested=signalSettings(fields),active={...requested,supertrend_enabled:true,supertrend_enabled_indicator:false};
 const exported=configurationText({broker:'DELTA_INDIA',fields:[],requested,active});const data=JSON.parse(exported.text.split('Serialized configuration (text JSON):\n')[1]);
 assert.equal(data.requested_start_configuration.supertrend_enabled,false);assert.equal(data.requested_start_configuration.supertrend_enabled_indicator,true);assert.equal(data.active_runner_configuration.supertrend_enabled_indicator,false);
});
const {toggleState}=require('../renko-supertrend.js');
test('retained recovery is distinct from active monitoring and pending reconciliation',()=>{
 assert.equal(toggleState({running:false,position:{},status:'RECOVERY_REQUIRED',position_recovery_revision:'management-only-recovery-v1'}).label,'Resume position monitoring');
 assert.equal(toggleState({running:false,pending:{}}).disabled,true);
 assert.equal(toggleState({running:true,position:{},management_only:true,accepting_entries:false}).label,'Stop Runner');
 assert.equal(toggleState({running:true,position:{},management_only:true,accepting_entries:false}).disabled,false);
});
const {zoneBandRect}=require('../renko-supertrend.js');
test('thin zones remain legible at wide price scales without changing source bounds',()=>{
 const zone={pivotAt:100,upper:2442.1,lower:2442};
 const before={...zone};const rect=zoneBandRect(zone,{from:90,to:200},1000,500,400,300,300.2);
 assert.equal(rect.height,6);assert.equal(rect.width,600);assert.deepEqual(zone,before);
 assert.ok(rect.y<=300&&rect.y+rect.height>=300.2);
});
test('minimum display highlight stays inside pane at top and bottom edges',()=>{
 for(const [upper,lower] of [[0,.1],[499.9,500]]){
  const rect=zoneBandRect({pivotAt:100},{from:90,to:200},1000,500,400,upper,lower);
  assert.ok(rect.y>=0);assert.ok(rect.y+rect.height<=500);assert.equal(rect.height,6);
 }
 assert.equal(zoneBandRect({pivotAt:100},{from:90,to:200},1000,500,400,510,520),null);
});
