const {test} = require('node:test');
const assert = require('node:assert/strict');
const {signals} = require('../ema-crossover.js');
const bars = prices => prices.map((close,i) => ({timestamp:i+1,open:close,high:close,low:close,close}));
test('price versus EMA10 qualifies on every completed candle without an EMA-to-EMA cross', () => {
 const result=signals(bars([...Array(100).fill(100),110,...Array(50).fill(120),80]));
 assert.equal(result[100].signal, 'CALL');
 assert.equal(result[101].signal, 'CALL');
 assert.equal(result.at(-1).signal, 'PUT');
});
test('forming bars excluded and future data cannot alter past signals', () => {
 const input=bars(Array.from({length:150},(_,i)=>100+Math.sin(i/5)*10));
 const result=signals(input);
 assert.deepEqual(signals(input.slice(0,110)), result.slice(0,110));
 assert.deepEqual(signals([...input,{...input.at(-1),timestamp:999,close:900,is_forming:true}]),result);
});
test('flat prices have no signals and invalid inputs fail', () => {
 const input=bars(Array(150).fill(100));
 assert.equal(signals(input).filter(c=>c.signal).length,0);
 assert.throws(()=>signals(input,30,10));
 assert.deepEqual(signals([...input].reverse().concat(input)), signals(input));
 assert.throws(()=>signals([input[0],{...input[0],close:101}]));
 assert.throws(()=>signals([{...input[0],close:NaN}]));
});
