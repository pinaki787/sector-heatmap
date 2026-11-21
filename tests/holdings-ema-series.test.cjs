const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('holdings-review-tools.js','utf8');const context={};vm.runInNewContext(source.slice(source.indexOf('const emaPeriods='),source.indexOf('let scope=null'))+';this.ema=holdingEmaSeries;this.periods=emaPeriods;',context);
test('six EMA periods seed only after sufficient candles and preserve precision',()=>{
 assert.deepEqual(Array.from(context.periods),[10,20,30,50,100,200]);
 const rows=Array.from({length:210},(_,i)=>({time:i+1,close:100+i*.123456}));
 for(const period of context.periods){const points=context.ema(rows,period);assert.equal(points.length,211-period);assert.equal(points[0].time,period);assert.equal(context.ema(rows.slice(0,period-1),period).length,0);let expected=rows.slice(0,period).reduce((n,r)=>n+r.close,0)/period;for(const r of rows.slice(period))expected+=(r.close-expected)*2/(period+1);assert.equal(points.at(-1).value,expected);}
});
