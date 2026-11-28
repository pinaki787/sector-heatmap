const test=require('node:test'),assert=require('node:assert/strict');require('../sector-pulse-unified-source.js');const api=globalThis.SectorPulseUnifiedSource;
const main='//@version=6\nindicator("AR-supertrend",overlay=true)\nplot(close,"Connected Supertrend")';
const ref='//@version=6\nindicator("V1",overlay=false)\nfloat preserved = close\n                string caption = rzLabels ? (z.side == 1 ? "DEMAND" : "SUPPLY")+" · "+rzSourceTf+"m · "+phase+"\\n"+str.tostring(z.lo,"#.##")+"–"+str.tostring(z.hi,"#.##") : ""\n// RSI Zones — separate indicator pane.\nold duplicate RSI';
test('one Sector Pulse declaration includes all maintained logic, compact OB captions and no component selector',()=>{
 const source=api.build(main,ref);assert.equal((source.match(/^indicator\(/gm)||[]).length,1);assert.match(source,/indicator\("Sector Pulse"/);assert.match(source,/Market Min Midline/);assert.match(source,/sp_rsi=ta.rsi/);assert.match(source,/float preserved = close/);assert.match(source,/SUPPLY"\)\+" OB · "/);assert.doesNotMatch(api.references(source),/str.tostring\(z.lo/);
});
test('regeneration preserves operator Supertrend edits and does not duplicate force_overlay arguments',()=>{
 const first=api.build(main,ref),next=api.build(first,ref);assert.equal(next,first);assert.doesNotMatch(next,/force_overlay=true.*force_overlay=true/);
 const edited=first.replace('float preserved = close','float preserved = close+1');assert.equal(api.build(edited,ref),edited,'do not overwrite imported reference edits');
});
test('unified source keeps the strict captured strategy compatibility check; calculation edits still fail',()=>{
 const vm=require('node:vm'),fs=require('node:fs'),s=fs.readFileSync('chart-workspace.js','utf8'),a=s.indexOf('  function aiIndicatorSourceMatches('),b=s.indexOf('  function openAiRenkoSupertrend(',a);
 const ctx={window:{SectorPulseUnifiedSource:api},managedAiRenkoPineSource:()=>main,aiRenkoPineSource:()=>main};vm.createContext(ctx);vm.runInContext(s.slice(a,b),ctx);
 const source=api.build(main,ref);assert.equal(ctx.aiIndicatorSourceMatches(source,10),true);assert.equal(ctx.aiIndicatorSourceMatches(source.replace('plot(close,','plot(close+1,'),10),false);
});
