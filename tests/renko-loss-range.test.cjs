const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('renko-supertrend.js','utf8');
function painter(){
 const input={checked:true,disabled:true},buffer={value:0,disabled:true},note={textContent:''};
 const ctx=vm.createContext({el:id=>id==='renko-loss-range-enabled'?input:id==='renko-loss-range-buffer'?buffer:note,price:n=>Number(n).toFixed(2)});
 const start=src.indexOf('    function paintLossRange('),end=src.indexOf('\n    }',start)+6;
 vm.runInContext(src.slice(start,end),ctx);
 return {input,buffer,note,paint:ctx.paintLossRange};
}
test('new control defaults on, uses next-Start payload, and restores broker symbol-scoped values',()=>{
 assert.match(src,/renko-renko-loss-range-enabled.*checkbox.*checked disabled/);
 assert.match(src,/fields\['renko-loss-range-enabled'\]=raw.renko_loss_range_enabled!==false/);
 assert.match(src,/renko_loss_range_enabled:el\('renko-loss-range-enabled'\).checked/);
 assert.match(src,/renko_loss_range_buffer:Number\(el\('renko-loss-range-buffer'\).value\)/);
});
test('stopped recorded config cannot overwrite next-Start selection',()=>{
 const v=painter();v.paint({config:{renko_loss_range_enabled:false},renko_loss_range_status:{enabled:false}});
 assert.equal(v.input.checked,true);assert.equal(v.input.disabled,false);assert.match(v.note.textContent,/On.*next Start/);
});
test('running controls show loaded setting and are read-only until next Start',()=>{
 const v=painter();v.paint({running:true,config:{renko_loss_range_enabled:true,renko_loss_range_buffer:1},renko_loss_range_status:{enabled:true}});
 assert.equal(v.input.disabled,true);assert.equal(v.input.checked,true);assert.equal(v.buffer.value,1);assert.match(v.note.textContent,/applies now/);
});
test('locked range displays two-decimal bounds and completed breakout requirement',()=>{
 const v=painter();v.paint({running:true,config:{},renko_loss_range_status:{enabled:true,lock:{active:true,low:100.123,high:130.567}}});
 assert.equal(v.note.textContent,'Locked 100.12 – 130.57 · completed breakout required');
});
test('unloaded worker cannot expose an enabled control',()=>{
 const v=painter();v.paint({});assert.equal(v.input.disabled,true);assert.equal(v.note.textContent,'Update pending');
});
