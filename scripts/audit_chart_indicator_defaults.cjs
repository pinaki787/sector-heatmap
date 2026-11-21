// Calculation coverage audit; does not establish numerical or TradingView parity.
const fs=require("node:fs"),crypto=require("node:crypto");
require("../chart-workspace-studies.js");
const definitions=globalThis.SectorPulseChartStudies.indicators;
const bars=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const symbolInfo=process.argv[3]?JSON.parse(fs.readFileSync(process.argv[3],"utf8")):{timezone:"Asia/Kolkata",session:"0915-1530",tickerid:"NSE:NIFTY50-INDEX",ticker:"NIFTY50-INDEX",prefix:"NSE",type:"index",mintick:.05};
const results=[];
for(const [kind,definition] of Object.entries(definitions)){
 const row={kind,name:definition.name};
 if(typeof definition.run!=="function" || definition.deltaCandles || definition.requiresSecondarySymbol){row.status="CONTEXT_REQUIRED";row.reason=definition.deltaCandles?"Broker intrabars or captured trades":definition.requiresSecondarySymbol?"Selected comparison symbol":definition.shadow?"Session reference OHLC":definition.periodOverlay?"Completed reference periods":"Chart-specific evaluation";results.push(row);continue}
 const inputs=Object.fromEntries((definition.inputs||[]).map(x=>[x.id,x.value]));
 try{
  const source=inputs.source||"close";
  const prices=bars.map(b=>source==="hl2"?(b.high+b.low)/2:source==="hlc3"?(b.high+b.low+b.close)/3:source==="ohlc4"?(b.open+b.high+b.low+b.close)/4:b[source]);
  const output=definition.run(structuredClone(bars),prices,definition.length,definition.multiplier,inputs,symbolInfo);
  let finite=0,nan=0,infinity=0;
  function inspect(value){if(typeof value==="number"){if(Number.isFinite(value))finite++;else if(Number.isNaN(value))nan++;else infinity++;}else if(Array.isArray(value))value.forEach(inspect);else if(value&&typeof value==="object")Object.values(value).forEach(inspect)}
  inspect(output);Object.assign(row,{status:infinity?"INVALID_INFINITY":finite?"CALCULATED":"NO_FINITE_VALUES",plots:Array.isArray(output)?output.length:null,finite_values:finite,nan_values:nan,infinite_values:infinity});
 }catch(error){Object.assign(row,{status:"ERROR",error:error.message})}
 results.push(row);
}
const counts=results.reduce((a,r)=>(a[r.status]=(a[r.status]||0)+1,a),{});
console.log(JSON.stringify({scope:"Default calculation coverage only; not rendered or externally validated",source_bars:bars.length,source_sha256:crypto.createHash("sha256").update(fs.readFileSync(process.argv[2])).digest("hex"),registry_count:results.length,counts,results},null,2));
