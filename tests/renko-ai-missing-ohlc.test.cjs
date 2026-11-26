const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../chart-workspace-studies.js'),'utf8'),ctx);
test('ATR refuses close-only runtime seed rather than interpreting absent High/Low as zero',()=>{
 const f=ctx.SectorPulseChartStudies.renkoAtrSize;
 const rows=Array.from({length:10},(_,i)=>({time:i,open:null,high:null,low:null,close:7620+i}));
 assert.equal(f(rows,5,1),null);
 assert.equal(f(rows.map(r=>({...r,high:r.close+2,low:r.close-2})),5,1),4);
});
