const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),test=require('node:test');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8'),scope={console};vm.createContext(scope);vm.runInContext(fs.readFileSync('chart-workspace-studies.js','utf8'),scope);
const lib=scope.SectorPulseChartStudies;
const rows=[{time:0,open:100,high:100,low:100,close:100,volume:10},{time:60,open:100,high:135,low:100,close:135,volume:50},{time:120,open:135,high:145,low:135,close:145,volume:30}];
function run(start=1,end=1,anchored=false,isRenko=true,mutate,changedTime){
 const bars=lib.renko(rows,10);if(mutate)mutate(bars);const anchor=i=>{const b=bars[i],group=bars.filter(x=>x.sourceTime===b.sourceTime);return {time:b.sourceTime,brickOffset:group.indexOf(b),brickOpen:b.open,brickClose:b.close,sourceBrickCount:group.length};};
 const drawing={kind:anchored?'anchored-volume-profile':'fixed-volume-profile',start:typeof start==='number'?anchor(start):start,end:typeof end==='number'?anchor(end):end},profiles=new Map();let lowerCalls=0;
 const ctx={drawings:[drawing],bars,rows,isRenko,profiles,changedTime,isVolumeProfile:()=>true,volumeProfileOptions:()=>({profileRows:4,profileValueArea:70}),profileSourceCandles:x=>{lowerCalls++;return x;},fixedRangeVolumeProfile:lib.fixedRangeVolumeProfile,catalogTickSize:()=>1,broker:{yahoo:false},chartSymbol:()=> 'TEST'};
 vm.createContext(ctx);
 let a=source.indexOf('  function renkoAnchorIndex('),b=source.indexOf('  function renkoAnchorAtIndex(',a);vm.runInContext(source.slice(a,b),ctx);
 a=source.indexOf('  function renkoVolumeProfileCandles(');if(a>=0){b=source.indexOf('  function profileResolution(',a);vm.runInContext(source.slice(a,b),ctx);}
 a=source.indexOf('    const refreshVolumeProfiles = (changedTime) => {');b=source.indexOf('    refreshVolumeProfiles();',a);assert.ok(a>=0&&b>a);vm.runInContext(source.slice(a,b)+';refreshVolumeProfiles(changedTime);',ctx);
 return {profile:profiles.get(drawing).profile,lowerCalls,bars};
}
test('actual Renko profile uses selected middle brick volume and geometry instead of whole parent candle',()=>{const r=run();assert.equal(r.profile.total,20);assert.equal(r.profile.rows[0].low,110);assert.equal(r.profile.rows.at(-1).high,120);assert.equal(r.lowerCalls,0);});
test('reverse brick selection preserves exactly the selected range',()=>{assert.equal(run(1,2).profile.total,40);assert.equal(run(2,1).profile.total,40);});
test('anchored Renko profile begins at selected brick and extends across later source groups',()=>assert.equal(run(1,1,true).profile.total,70));
test('legacy candle-time endpoint includes its full final source group',()=>assert.equal(run({time:60},{time:60}).profile.total,60));
test('uncertified Renko volume does not silently substitute source volume',()=>assert.equal(run(1,1,false,true,b=>{b[1].renkoVolume=false;}).profile,null));
test('regular candle profiles retain original source-volume and lower-resolution path',()=>{const r=run({time:60},{time:60},false,false);assert.equal(r.profile.total,50);assert.equal(r.lowerCalls,1);});


test('earlier source-volume revisions still refresh a later selected Renko group',()=>assert.equal(run(1,1,false,true,undefined,0).profile.total,20));
