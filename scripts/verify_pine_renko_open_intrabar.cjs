const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2];
if(!worker)throw Error('Provide staged worker path');
const text=fs.readFileSync(worker,'utf8'),a=text.indexOf('function collectRenkoIntrabars('),b=text.indexOf('\n}\n',a)+3;
assert.ok(a>=0&&b>a);
const context=vm.createContext({});vm.runInContext(text.slice(a,b),context);
const opens=[0,5,10,15],closes=[5,10,15,20],values=['A','B','C','FORMING'];
const cases=[
 {name:'unknown close exposes only completed candles',open:5,close:NaN,previous:5,clock:17,want:['B','C']},
 {name:'historical end stays bounded',open:5,close:12,previous:5,clock:17,want:['B']},
 {name:'known future end cannot expose forming candle',open:5,close:20,previous:5,clock:17,want:['B','C']},
 {name:'duplicate source window does not replay intrabars',open:5,close:10,previous:10,clock:17,want:[]},
 {name:'unknown previous close starts at source opening',open:10,close:NaN,previous:NaN,clock:17,want:['C']},
 {name:'future opening cannot expose data',open:20,close:NaN,previous:undefined,clock:17,want:[]},
 {name:'invalid evaluation clock fails closed',open:5,close:NaN,previous:5,clock:NaN,want:[]},
 {name:'unbounded close remains capped by the evaluation clock',open:5,close:Infinity,previous:5,clock:17,want:['B','C']}
];
for(const c of cases){
 const actual=Array.from(context.collectRenkoIntrabars(opens,closes,values,c.open,c.close,c.previous,c.clock));
 assert.deepEqual(actual,c.want,c.name);
}
const c=text.indexOf('function currentRenkoSecurityIndex('),d=text.indexOf("\n}\n",c)+3;
assert.ok(c>=0&&d>c);vm.runInContext(text.slice(c,d),context);
const indexCases=[
 {opens:[0,5,10,15],open:5,clock:12,want:2},
 {opens:[0,5,10,15],open:5,clock:15,want:3},
 {opens:[0,5,10,15],open:10,clock:9,want:-1},
 {opens:[],open:5,clock:12,want:-1},
 {opens:[0,5,10,15],open:5,clock:NaN,want:-1},
 {opens:[10,10,10,15],open:10,clock:12,want:2}
];
for(const c of indexCases)assert.equal(context.currentRenkoSecurityIndex(c.opens,c.open,c.clock),c.want);
console.log(JSON.stringify({status:'PASS',realtime_security_index_cases:indexCases.length,cases:cases.map(c=>c.name),scope:'Completed intrabar boundaries; no future/forming values or duplicate closed windows.'},null,2));
