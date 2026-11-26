const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8'),a=source.indexOf('  function boundStrategyBrick(config){'),b=source.indexOf('  function renkoBoxSize(',a),code=source.slice(a,b);
test('strategy geometry overrides saved ATR or 10-point display size in every view with full precision',()=>{
 const context={aiSelectionParams:new URLSearchParams('aiRenko=1&chartContext=renko&brick=7.142857142857143')};vm.createContext(context);vm.runInContext(code,context);
 for(const type of ['Candles','Renko','Line','Heikin Ashi']){
  const config={type,brickMethod:'atr',size:10};assert.equal(context.boundStrategyBrick(config),7.142857142857143);assert.equal(config.size,7.142857142857143);assert.equal(config.brickMethod,'fixed');
 }
});
test('standalone chart geometry is untouched',()=>{
 const context={aiSelectionParams:new URLSearchParams('symbol=TEST')};vm.createContext(context);vm.runInContext(code,context);
 const config={brickMethod:'atr',size:10};assert.equal(context.boundStrategyBrick(config),null);assert.equal(config.brickMethod,'atr');
});
