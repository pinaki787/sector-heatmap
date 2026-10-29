const {test}=require('node:test'),assert=require('node:assert/strict');
const {chartEditorSelection,signalSettings}=require('../renko-supertrend.js');
test('editor synchronization includes calculation inputs and excludes order/account changes',()=>{
 const fields={timeframe:'1 minute','strategy-basis':'RENKO','supertrend-slope-enabled':false,'supertrend-slope-bars':'2','atr-length':'5',factor:'3','history-preset':'45','rsi-length':'14',mode:'LIVE',lots:'999',symbol:'OTHER','daily-budget':'50000','broker-account':'OTHER'};
 const selection=chartEditorSelection(fields);
 for(const key of ['timeframe','strategy-basis','supertrend-slope-enabled','supertrend-slope-bars','atr-length','factor','history-preset','rsi-length'])assert.equal(selection[key],fields[key]);
 for(const key of ['mode','lots','symbol','daily-budget','broker-account'])assert.equal(key in selection,false);
 assert.equal(signalSettings(selection).strategy_basis,'RENKO');assert.equal(signalSettings(selection).supertrend_slope_enabled,false);
});
