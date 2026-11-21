const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {chartCandles}=require('../renko-supertrend.js');
test('line uses broker closes and preserves the same missing-candle gaps as candles',()=>{
 const d={rows:[{timestamp:60,open:100,high:110,low:90,close:105}],forming:[{timestamp:180,open:105,high:108,low:101,close:107}],data_quality:{gaps:[{timestamp:120}]}};
 assert.deepEqual(chartCandles(d,'line'),chartCandles(d,'host'));
});
test('line style hides candle bodies and uses a separate close series',()=>{
 const source=fs.readFileSync('renko-supertrend.js','utf8');const start=source.indexOf('    function paintPriceStyle(){'),end=source.indexOf('\n',start);
 let candleVisible,data,options;const c={chart:{addLineSeries:()=>({applyOptions:o=>options=o,setData:p=>data=p})},candles:{applyOptions:o=>candleVisible=o.visible},el:()=>({value:'line'}),closePriceLine:null,currentPlotted:[{time:60,close:100},{time:120}],price:String};vm.createContext(c);vm.runInContext(source.slice(start,end)+';paintPriceStyle();',c);assert.equal(candleVisible,false);assert.equal(options.visible,true);assert.equal(JSON.stringify(data),'[{"time":60,"value":100},{"time":120}]');
});
