const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync(process.env.REFERENCE_FAILURE_CANDIDATE||"chart-workspace.js","utf8");
const extract=name=>{const m=source.match(new RegExp("^  (?:async )?function "+name+"\\([\\s\\S]*?^  }","m"));assert.ok(m,name);return m[0]};
function fixture({aborted=false,generation=1,replay=false}={}){
 const controller=new AbortController();if(aborted)controller.abort();
 const old={time:900,open:100,high:110,low:90,close:105,provisional:true},state={bars:[{time:600}],live:old};
 let now=950,fail=true,updates=0,calls=0;
 const ctx={Date:{now:()=>now*1000},barReplay:replay,settings:{studies:[{}]},symbolSelection:()=>true,tradeInterval:()=>false,broker:{yahoo:false},
 alternateStudySymbol:()=>"ETHUSD",studyVisible:()=>true,calculationInterval:()=>undefined,studySymbolHistory:()=>state,
 loadPineLiveFrame:async()=>{calls++;if(fail)throw Error("temporary reference outage");return {connected:true}},
 alternateStudyLiveCandle:()=>({...old,close:106}),generation,panel:{open:true},rows:[{time:900,provisional:true}],pendingViewportRedraw:false,
 updateLastPrice:()=>{updates++;return true},sameCandle:(a,b)=>a.close===b.close};
 const refresh=vm.runInNewContext(extract("refreshAlternateStudyBars")+";refreshAlternateStudyBars",ctx);
 return {state,old,ctx,refresh:()=>refresh(1,"5",controller.signal),advance:()=>{now+=6;fail=false},counts:()=>({updates,calls})};
}
test("failed owned reference request clears forming state and recovers on automatic retry",async()=>{const f=fixture();await f.refresh();assert.equal(f.state.live,undefined,"stale forming value must be cleared");assert.equal(f.counts().updates,1);f.advance();await f.refresh();assert.equal(f.state.live.close,106);assert.equal(f.counts().updates,2)});
test("superseded request cannot clear current chart reference state",async()=>{const f=fixture({generation:2});await f.refresh();assert.equal(f.state.live,f.old);assert.equal(f.counts().updates,0)});
test("replay and aborted scopes do not mutate reference state",async()=>{for(const args of [{replay:true},{aborted:true}]){const f=fixture(args);await f.refresh();assert.equal(f.state.live,f.old);assert.equal(f.counts().calls,0)}});
