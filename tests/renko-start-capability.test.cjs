const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync(require.resolve("../renko-supertrend.js"),"utf8");
const begin=source.indexOf("async function request(path,body){")+"async function request(path,body){".length;
const end=source.indexOf("if(body&&(path===\x27preview\x27||path===\x27start\x27)&&body.auto_sizing_policy",begin);
async function gate(revision,changed=false){
 const calls=[];const ctx={path:"start",body:{strategy_basis:"RENKO"},instanceId:"selected",lastRunner:null,bindDisplayedInstrument:async()=>{calls.push("bind");if(changed)ctx.instanceId="other";},request:async p=>{calls.push(p);return {swing_breakout_revision:revision};},applyStatus:s=>calls.push("apply")};
 try{await vm.runInNewContext("(async()=>{"+source.slice(begin,end)+"})()",ctx);return {calls};}catch(error){return {calls,error};}
}
test("Start reads current selected capability even when cached runner is absent",async()=>{const r=await gate("renko-swing-breakout-v1");assert.equal(r.error,undefined);assert.deepEqual(r.calls,["bind","runner","apply"]);});
test("unsupported backend cannot silently omit configured swing enforcement",async()=>{const r=await gate(undefined);assert.match(r.error.message,/does not support/);assert.deepEqual(r.calls,["bind","runner","apply"]);});
test("selection change stops Start before capability lookup or submission",async()=>{const r=await gate("renko-swing-breakout-v1",true);assert.match(r.error.message,/review/);assert.deepEqual(r.calls,["bind"]);});
