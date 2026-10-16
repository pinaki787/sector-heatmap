const test=require('node:test'),assert=require('node:assert/strict');
const r=require('../renko-supertrend.js');
test('family defaults preserve legacy and raw subordinate choices',()=>{
 const fields={'ema-fast-enabled':true,'retest-enabled':true,'ema-family-enabled':false};
 const original=JSON.stringify(fields),payload=r.signalSettings(fields);
 assert.equal(payload.ema_family_enabled,false);assert.equal(payload.ema_fast_enabled,true);assert.equal(payload.retest_enabled,true);
 assert.equal(JSON.stringify(fields),original);assert.equal(r.familySettings({}).ema_family_enabled,true);
 const effective=r.effectiveFamilySettings(payload);
 for(const id of r.FAMILY_RULES.ema)assert.equal(effective[id.replaceAll('-','_')],false);
});
test('strategy and chart effects disabled while stored choices are retained',()=>{
 for(const [family,ids]of Object.entries(r.FAMILY_RULES)){
  const cfg={[family+'_family_enabled']:false};
  for(const id of ids){cfg[id.replaceAll('-','_')]=true;cfg[id.replaceAll('-','_')+'_indicator']=true;}
  const effective=r.effectiveFamilySettings(cfg);
  for(const id of ids){assert.equal(effective[id.replaceAll('-','_')],false);assert.equal(effective[id.replaceAll('-','_')+'_indicator'],true);}
 }
 const chart=r.chartSettings({'ema-family-enabled':false,'ema-fast-enabled':true,'ema-fast-enabled-indicator':true});
 assert.equal(chart.ema_fast_enabled,false);assert.equal(Object.hasOwn(chart,'ema_family_enabled'),false);
});
test('serialized configuration restores disabled subordinate selections',()=>{
 const saved=JSON.parse(JSON.stringify({ema_family_enabled:false,ema_fast_enabled:false,retest_enabled:false,indicator_family_choices:{ema_fast_enabled:true,retest_enabled:true}}));
 assert.equal(r.effectiveFamilySettings(saved).ema_fast_enabled,false);
 saved.ema_family_enabled=true;
 assert.equal(r.effectiveFamilySettings(saved).ema_fast_enabled,true);assert.equal(r.effectiveFamilySettings(saved).retest_enabled,true);
 saved.supertrend_family_enabled=false;assert.equal(r.effectiveFamilySettings(saved).retest_enabled,false);
});
