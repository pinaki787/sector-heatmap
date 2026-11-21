const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('renko-supertrend.js','utf8');
const start=source.indexOf('    async function bindDisplayedInstrument(){'),end=source.indexOf('    function syncManualBrickFrames',start);
function fixture(mode){
 const nodes=new Map();const el=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='strategy-mode'?mode:id==='symbol'?'NSE:RELIANCE-EQ':'',replaceChildren(){}});return nodes.get(id);};
 const calls=[];let resolve;
 const context={isBatchChartView:false,el,bindingPromise:null,boundSelectionSymbol:'',selectedBroker:'FYERS',selectionEpoch:0,prefsTimer:null,stream:null,streamEpoch:0,streamKey:'',runnerStatusFresh:false,lastRunner:null,version:0,clearTimeout,clearAnalysis(){},syncChartControl(){},renderedOrderKey:'',renderedAuditKey:'',isNative:false,apiBase:'',registryBase:'/registry/',fetch:(url,body)=>{calls.push({url,body});return new Promise(r=>resolve=r);}};
 vm.createContext(context);vm.runInContext(source.slice(start,end),context);
 return {context,el,calls,resolve:value=>resolve(value)};
}
test('AI instrument selection never creates or binds a legacy runner',async()=>{
 const f=fixture('AI_RENKO_OPTIONS');await f.context.bindDisplayedInstrument();assert.equal(f.calls.length,0);
});
test('late legacy inventory cannot create an instance after AI mode is selected',async()=>{
 const f=fixture('SIMPLE_BRICK');const work=f.context.bindDisplayedInstrument();assert.equal(f.calls.length,1);
 f.el('strategy-mode').value='AI_RENKO_OPTIONS';f.resolve({ok:true,json:async()=>({instances:[]})});await work;
 assert.equal(f.calls.length,1);assert.equal(f.el('strategy-mode').value,'AI_RENKO_OPTIONS');
 assert.equal(f.context.boundSelectionSymbol,'');
});
