const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const baseline = process.argv[2], candidate = process.argv[3];
if (!baseline || !candidate) throw Error("Pass baseline and candidate worker files");
const scripts = {
 custom_types: `//@version=6\nindicator("Types")\ntype Sample\n    float value\nvar Sample item=Sample.new(na)\nitem.value:=close\nplot(item.value)`,
 inputs: `//@version=6\nindicator("Inputs")\nint length=input.int(14,"Length")\nplot(ta.sma(close,length))`,
 averages: `//@version=6
indicator("Averages")
plot(ta.sma(close,20))
plot(ta.ema(close,12))
plot(ta.rsi(close,14))
plot(ta.atr(14))`,
 persistence: `//@version=6
indicator("History")
var float state=na
state:=na(state[1]) ? close : state[1]*0.8+close*0.2
plot(state)
plot(close[3])
plot(na(close[200]) ? 1 : 0)`,
 arrays: `//@version=6
indicator("Collections")
var array<float> values=array.new<float>()
array.push(values,close)
if array.size(values)>5
    array.shift(values)
plot(array.avg(values))
plot(array.size(values))`,
 objects: `//@version=6
indicator("Drawings",overlay=true)
var line ln=na
var table panel=table.new(position.top_right,2,1)
if barstate.islast
    line.delete(ln)
    ln:=line.new(time[1],close[1],time,close,xloc=xloc.bar_time)
    table.cell(panel,0,0,"Close")
    table.cell(panel,1,0,str.tostring(close))
plot(close)`,
 multi_timeframe: `//@version=6
indicator("Requests")
[hi,lo]=request.security(syminfo.tickerid,"15",[high,low],lookahead=barmerge.lookahead_off)
plot(hi)
plot(lo)`
};
const baseTime=Date.UTC(2026,10,18,4)/1000;
const rows=Array.from({length:120},(_,i)=>({openTime:(baseTime+i*300)*1000,closeTime:(baseTime+(i+1)*300)*1000,open:100+i*.2,high:102+i*.2,low:99+i*.2,close:101+i*.2+Math.sin(i),volume:100+i}));
const higher=Array.from({length:40},(_,i)=>{const b=rows.slice(i*3,i*3+3);return {...b[0],closeTime:b[2].closeTime,high:Math.max(...b.map(x=>x.high)),low:Math.min(...b.map(x=>x.low)),close:b[2].close,volume:b.reduce((a,x)=>a+x.volume,0)}});
async function run(bundle, source){
 const frames={"5":structuredClone(rows),"15":structuredClone(higher)};
 let resolve,reject,lastPlots;const context=vm.createContext({console,setTimeout,clearTimeout,structuredClone});context.self=context;
 context.postMessage=data=>{if(!data.ok)reject(Error(data.error));else if(data.plots){lastPlots=JSON.stringify(data.plots);resolve(lastPlots)}else if(data.type==="updated")resolve(lastPlots);};
 vm.runInContext(fs.readFileSync(bundle,"utf8"),context);
 const send=message=>new Promise((yes,no)=>{resolve=yes;reject=no;Promise.resolve(context.onmessage({data:message})).catch(no)});
 const symbolInfo={tickerid:"NSE:TEST",ticker:"TEST",prefix:"NSE",type:"stock",timezone:"Asia/Kolkata",mintick:.05,session:"regular",currency:"INR"};
 const initial=await send({source,frames,symbolInfo,timeframe:"5",count:100});
 frames["5"].at(-1).close+=.25;
 frames["15"].at(-1).high+=.25;
 const tail=await send({type:"refresh",count:100});
 const reset=await send({type:"refresh",reset:true,count:100});
 assert.notEqual(initial,reset,"Changed source candle must change calculated output");
 return {initial,tail,reset};
}
(async()=>{
 const results=[];
 for(const [name,source] of Object.entries(scripts)){
  const a=await run(baseline,source),b=await run(candidate,source);
  assert.equal(b.initial,a.initial,name+" initial differs");assert.equal(b.reset,a.reset,name+" reset differs");assert.equal(b.tail,a.tail,name+" tail differs");
  results.push({name,initial_identical:true,reset_identical:true,tail_identical:true,tail_changed:a.initial!==a.tail,initial_sha256:crypto.createHash("sha256").update(a.initial).digest("hex")});
 }
 console.log(JSON.stringify({status:"PASS",results},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
