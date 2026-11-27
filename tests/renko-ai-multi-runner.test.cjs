const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs');
const {defaultProduct}=require('../renko-ai-options.js');
test('Intraday default applies to unset FYERS products, retaining deliberate choices',()=>{
 assert.equal(defaultProduct({broker:'FYERS'},{route:'OPTIONS'}),'INTRADAY');
 for(const product of ['MARGIN','INTRADAY','CNC'])assert.equal(defaultProduct({broker:'FYERS'},{product}),product);
 assert.equal(defaultProduct({broker:'DELTA_INDIA'},{route:'DIRECT'}),'');
 assert.equal(defaultProduct({broker:'DHAN'},{route:'OPTIONS'}),'');
 assert.equal(defaultProduct({broker:'MOTILAL_OSWAL'},{route:'DIRECT'}),'INTRADAY');
});
test('Runner selection and controls send explicit selected instrument with normal runtime proof',()=>{
 const s=fs.readFileSync(require.resolve('../renko-ai-options.js'),'utf8');
 const {aiActionUrl}=require('../renko-ai-options.js');
 const u=new URL(aiActionUrl('status','NSE:NIFTY50-INDEX'),'https://example.test');
 assert.equal(u.searchParams.get('runner_symbol'),'NSE:NIFTY50-INDEX');
 assert.match(s,/configurationError=error.message/);
 assert.match(s,/startReason.textContent=configurationError/);
 assert.match(s,/Instrument runners/);
 assert.match(s,/snapshot\?\.multi_runner_ready&&next.underlying!==snapshot.underlying/);
});

test('Cash selection defaults to direct shares, explicit instrument preferences still win',()=>{
 const {restoredInstrumentValues,configuration}=require('../renko-ai-options.js');
 const defaults={route:'OPTIONS',product:'',manualParent:'400'};
 const cash=restoredInstrumentValues(defaults,null,'NSE:LAURUSLABS-EQ','NSE_EQUITY');
 assert.equal(cash.route,'DIRECT');assert.equal(cash.product,'INTRADAY');assert.equal(cash.manualParent,'');
 const saved=restoredInstrumentValues(defaults,{route:'OPTIONS',product:'MARGIN'},'NSE:LAURUSLABS-EQ','NSE_EQUITY');
 assert.equal(saved.route,'OPTIONS');assert.equal(saved.product,'MARGIN');
 assert.equal(restoredInstrumentValues(defaults,null,'NSE:LAURUSLABS-EQ','NSE_STOCK').route,'OPTIONS');
});

test('Restoring an index runner repairs an inherited cash-market filter while stocks preserve intent',()=>{
 const {runnerMarket}=require('../renko-ai-options.js');
 assert.equal(runnerMarket('NSE:NIFTY50-INDEX',{instrument_market:'NSE_EQUITY'}),'NSE_INDEX');
 assert.equal(runnerMarket('BSE:SENSEX-INDEX',{}),'BSE_INDEX');
 assert.equal(runnerMarket('NSE:LAURUSLABS-EQ',{instrument_market:'NSE_EQUITY'}),'NSE_EQUITY');
 assert.equal(runnerMarket('NSE:LAURUSLABS-EQ',{instrument_market:'NSE_STOCK'}),'NSE_STOCK');
});
