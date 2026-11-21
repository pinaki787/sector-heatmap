/* Retained heap of isolated arrays, not a live-chart memory estimate. */
const fs=require('node:fs'),vm=require('node:vm');
const c=vm.createContext({console,setTimeout,clearTimeout,structuredClone});c.self=c;
const s=fs.readFileSync(process.argv[2],'utf8').replace('}function xd(t)','}self.__ArrayClass=G;self.__ArrayType=W;function xd(t)');
vm.runInContext(s,c);global.gc();
const before=process.memoryUsage().heapUsed,context={precision:x=>x},started=performance.now();
global.arrays=Array.from({length:10000},()=>new c.__ArrayClass([1,2,3],c.__ArrayType.float,context));
const elapsed=performance.now()-started;global.gc();const after=process.memoryUsage().heapUsed;
console.log(JSON.stringify({worker:process.argv[2],arrays:global.arrays.length,retained_heap_bytes:after-before,construction_ms:elapsed}));
