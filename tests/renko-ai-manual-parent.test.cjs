
const test=require('node:test'),assert=require('node:assert/strict');
const {configuration,manualSizingValues,chartView}=require('../renko-ai-options.js');
const f={underlying:'MCX:CRUDEOIL26DECFUT',sizingMode:'MANUAL_PARENT',manualParent:'200',timeframe:'1 minute',lots:'1',execution:'PAPER',product:'MARGIN'};
test('manual parent overrides automatic hidden value and retains exact conversion',()=>{
 const c=configuration({...f,reference:'1500'},{id:'owner',broker:'FYERS'});
 assert.equal(c.ai_sizing_mode,'MANUAL_PARENT');assert.equal(c.ai_reference_value,200);
 assert.equal(c.ai_manual_parent_value,200);
 assert.equal(chartView(manualSizingValues(f),null,false,'FYERS').base,200/28);
});
test('manual parent rejects invalid values and Auto stays default',()=>{
 for(const v of ['',0,-2,'NaN','Infinity'])assert.throws(()=>configuration({...f,manualParent:v},{id:'owner',broker:'FYERS'}),/positive parent/);
 assert.equal(configuration({...f,sizingMode:'AUTO'},{id:'owner',broker:'FYERS'}).ai_sizing_mode,'AUTO');
});
test('owned position keeps captured geometry when draft override differs',()=>{
 const view=chartView(manualSizingValues(f),{position:{underlying:f.underlying,spot_brick:7.14,option_type:'CE'}},true,'FYERS');
 assert.equal(view.base,7.14);assert.equal(view.frozen,true);
});
