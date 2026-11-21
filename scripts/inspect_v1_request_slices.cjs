const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const [worker,folder]=process.argv.slice(2);
const context=vm.createContext({console,setTimeout,clearTimeout,structuredClone});context.self=context;
vm.runInContext(fs.readFileSync(worker,'utf8'),context);
const debug=[];context.__spDepsDebug=data=>debug.push(data);
const indicator=new context.PineTSLib.Indicator(fs.readFileSync('sector-pulse-v1.pine','utf8'));
const prepared=indicator.prepare({ln:false,debug:false});
fs.mkdirSync(folder,{recursive:true});
fs.writeFileSync(path.join(folder,'host.js'),prepared.fn.toString());
const report=[];
for(const [key,fn] of Object.entries(prepared.ltfSlices||{})){
 const text=fn.toString();fs.writeFileSync(path.join(folder,key+'.js'),text);report.push({key,bytes:text.length,lines:text.split('\n').length});
}
fs.writeFileSync(path.join(folder,'manifest.json'),JSON.stringify(report,null,2));
if(debug.length)fs.writeFileSync(path.join(folder,'debug.json'),JSON.stringify(debug));
console.log(JSON.stringify(report));
