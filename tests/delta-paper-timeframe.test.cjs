const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={window:{},document:{}};vm.runInNewContext(fs.readFileSync('delta-inr.js','utf8'),context);vm.runInNewContext(fs.readFileSync('delta-india.js','utf8'),context);
const label=context.window.DeltaPaperTimeframe;
test('entry timeframe has readable units and takes precedence over other evidence',()=>{
 for(const [value,expected] of [['1m','1 minute'],['5m','5 minutes'],['15m','15 minutes'],['1h','1 hour'],['6h','6 hours'],['1d','1 day']])assert.equal(label({entry_timeframe:value,entry_context:{timeframe:'30m'}}),expected);
});
test('legacy history uses only recorded entry evidence, never current or exit settings',()=>{
 assert.equal(label({entry_context:{timeframe:'5m'}}),'5 minutes');
 assert.equal(label({entry_context:{settings:{resolution:'1m'}}}),'1 minute');
 for(const trade of [{},{resolution:'5m',exit_context:{timeframe:'1m'}},{entry_timeframe:null,entry_context:{timeframe:'5m'}},{entry_timeframe:'bad'}])assert.equal(label(trade),'Not recorded');
});
