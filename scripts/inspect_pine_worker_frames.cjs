const fs=require("node:fs"),vm=require("node:vm");
const [bundle,inputFile]=process.argv.slice(2),input=JSON.parse(fs.readFileSync(inputFile,"utf8"));
const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
ctx.postMessage=data=>{if(!data.ok){console.log(JSON.stringify({status:"ERROR",error:data.error}));process.exitCode=1;return}if(!data.plots)return;const summaries=Object.entries(data.plots).map(([name,p])=>({name,finite:p.data.filter(x=>Number.isFinite(x.value)).length,last:p.data.filter(x=>Number.isFinite(x.value)).at(-1)?.value,objects:Array.isArray(p.data.at(-1)?.value)?p.data.at(-1).value.filter(x=>!x._deleted).length:undefined}));const tables=data.plots.__tables__?.data.at(-1)?.value.filter(x=>!x._deleted);console.log(JSON.stringify({status:"CALCULATED",summaries,tables},null,2))};
vm.runInContext(fs.readFileSync(bundle,"utf8"),ctx);ctx.onmessage({data:input}).catch(e=>{console.error(e.message);process.exitCode=1});
