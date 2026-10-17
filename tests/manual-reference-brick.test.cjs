const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('renko-supertrend.js','utf8');
function harness(){
 const elements=new Map(),memory=new Map(),calls=[];
 function el(id){if(!elements.has(id))elements.set(id,{value:id==='brick-mode'?'Manual':id==='symbol'?'NSE:NIFTY50-INDEX':id==='atr-length'?'5':'',handlers:{},addEventListener(k,f){this.handlers[k]=f},closest(){return {append(){}}}});return elements.get(id)}
 const ctx={isDelta:false,stream:null,streamKey:'',connectStream(){},paintTradingSessionHours(){},el,selectedBroker:'DHAN',apiBase:'/api/renko-dhan/account/',dhanAccount:'account',document:{createElement(){return {style:{},addEventListener(){}}}},localStorage:{getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v)},URLSearchParams,JSON,Number,Error,invalidate(){calls.push('save')},load(){},async bindDisplayedInstrument(){},async request(path){calls.push(path);return {symbol:el('symbol').value,revision:'broker-session-reference-atr-v2',manual_brick:250/12,rule:{atr_length:5,divisor:12}}}};
 vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('    let manualBrickGeneration='),source.indexOf('    async function request(path,body)'))+';globalThis.derive=deriveManualBrick;',ctx);
 return {ctx,el,calls,memory};
}
test('Manual derives once and survives timeframe changes/reload with server record',async()=>{
 const h=harness();await h.ctx.derive();assert.equal(Number(h.el('manual-brick').value),20.83);
 assert.equal(h.calls.filter(x=>x.startsWith('manual-brick?')).length,1);
 h.el('timeframe').value='15 minutes';await h.ctx.derive();
 assert.equal(h.calls.filter(x=>x.startsWith('manual-brick?')).length,1);
 h.memory.clear();await h.ctx.derive();
 assert.equal(h.calls.filter(x=>x.startsWith('manual-brick?')).length,1);
 assert.equal(Number(h.el('manual-brick').value),20.83);
});
test('New instrument recalculates rather than reuse old instrument reference',async()=>{
 const h=harness();await h.ctx.derive();h.el('symbol').value='BSE:SENSEX-INDEX';await h.ctx.derive();
 assert.equal(h.calls.filter(x=>x.startsWith('manual-brick?')).length,2);
 assert.equal(JSON.parse(h.el('manual-brick-reference').value).symbol,'BSE:SENSEX-INDEX');
});
test('Auto never requests fixed manual sizing',async()=>{
 const h=harness();h.el('brick-mode').value='Auto';await h.ctx.derive();assert.deepEqual(h.calls,[]);
});

test('A late response from the prior instrument cannot overwrite the new selection',async()=>{
 const h=harness();let finish,ready;const requested=new Promise(resolve=>{ready=resolve});
 h.ctx.request=()=>new Promise(resolve=>{finish=resolve;ready()});
 const pending=h.ctx.derive();
 await requested;
 h.el('symbol').value='BSE:SENSEX-INDEX';
 h.ctx.request=async()=>({symbol:'BSE:SENSEX-INDEX',manual_brick:70,rule:{atr_length:5,divisor:12}});
 await h.ctx.derive();
 finish({symbol:'NSE:NIFTY50-INDEX',manual_brick:20,rule:{atr_length:5,divisor:12}});
 await pending;
 assert.equal(Number(h.el('manual-brick').value),70);
 assert.equal(JSON.parse(h.el('manual-brick-reference').value).symbol,'BSE:SENSEX-INDEX');
});

test('Parent refreshes only its matching embedded chart after a new Manual draft is saved',()=>{
 let reloads=0;const frame={dataset:{},get src(){return 'chart'},set src(value){reloads++}};
 const ctx={isBatchChartView:false,instanceId:'selected',batchChartFrames:new Map([['selected',{querySelector:()=>frame}]])};
 vm.createContext(ctx);
 vm.runInContext(source.slice(source.indexOf('    function syncManualBrickFrames('),source.indexOf('    let manualBrickGeneration='))+';globalThis.sync=syncManualBrickFrames;',ctx);
 const draft={symbol:'NSE:NIFTY50-INDEX','brick-mode':'Manual','manual-brick':20,'manual-brick-reference':'saved'};
 ctx.sync(draft);assert.equal(reloads,1);
 ctx.sync({...draft,timeframe:'15 minutes'});assert.equal(reloads,1);
 ctx.sync({...draft,'manual-brick':21});assert.equal(reloads,2);
 ctx.isBatchChartView=true;ctx.sync({...draft,'manual-brick':22});assert.equal(reloads,2);
});

test("Crypto rejects obsolete divisor and retains corrected reference",async()=>{const h=harness();h.ctx.isDelta=true;h.el('atr-length').value='7';h.el("symbol").value="BTCUSD";h.el("manual-brick-reference").value=JSON.stringify({symbol:"BTCUSD",manual_brick:125,rule:{divisor:12}});h.ctx.request=async path=>{h.calls.push(path);return {symbol:"BTCUSD",manual_brick:1500/46,rule:{atr_length:7,divisor:46}}};await h.ctx.derive();await h.ctx.derive();assert.equal(h.calls.filter(x=>x.startsWith("manual-brick?")).length,1);assert.equal(Number(h.el("manual-brick").value),32.61);});


test('normal chart remains visible when no batch charts replace it',()=>{
 const panel={hidden:true};const ctx={isBatchChartView:false,pageParams:new URLSearchParams(),isDelta:false,isEngine:false,batchChartArea:{hidden:false},batchChartFrames:new Map(),el:id=>id==='batch-symbols'?{selectedOptions:[]}:{closest:()=>panel}};
 vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('    function syncBatchCharts('),source.indexOf('    async function instanceList('))+';globalThis.sync=syncBatchCharts;',ctx);
 ctx.sync([]);assert.equal(panel.hidden,false);assert.equal(ctx.batchChartArea.hidden,true);
});
