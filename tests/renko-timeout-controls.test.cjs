const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('embedded Start cannot replace a five-minute form with a stale one-minute chart',async()=>{
 const src=fs.readFileSync('renko-supertrend.js','utf8'),a=src.indexOf('    // Embedded Start must use the visible editor'),b=src.indexOf("    root.addEventListener('message',event=>",a);
 let receive,replied;
 const child={postMessage:r=>{replied=r;}},timeframe={value:'5 minutes',options:[{value:'1 minute'},{value:'5 minutes'}]};
 const ctx={root:{addEventListener:(name,fn)=>{receive=fn;}},isBatchChartView:false,location:{origin:'https://test'},batchChartFrames:new Map([['x',{querySelector:()=>({contentWindow:child,src:'https://test/?renkoChartSymbol=BTCUSD'})}]]),URL,el:id=>id==='timeframe'?timeframe:{value:'BTCUSD'},confirmStartConfiguration:()=>{throw Error('must not confirm');}};
 vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);
 await receive({origin:'https://test',source:child,data:{type:'sector-pulse:renko-start-settings-request',id:'request',symbol:'BTCUSD',timeframe:'1 minute'}});
 assert.equal(timeframe.value,'5 minutes');assert.match(replied.error,/timeframe differs/);assert.equal(replied.payload,undefined);
});
test('status failure keeps only an identified running Stop actionable',()=>{
 const src=fs.readFileSync('renko-supertrend.js','utf8');
 const start=src.indexOf('    function syncChartControl()'),end=src.indexOf(String.fromCharCode(10),start);
 const nodes={};const el=id=>nodes[id]??=( {hidden:false,disabled:false,textContent:'',value:id==='symbol'?'BTCUSD':'PAPER'});
 const api=require('../renko-supertrend.js');
 const ctx={el,lastRunner:{running:true,run_id:'run',config:{mode:'PAPER'},indicator_selection_revision:'independent-indicators-v1'},toggleBusy:false,overrideBusy:false,runnerStatusFresh:false,toggleState:api.toggleState,overrideState:()=>({disabled:true,label:'Override',reason:''}),overrideAttempt:null,selectedBroker:'DELTA_INDIA',isDelta:true,syncActiveStartButtons(){},syncThirdEmaControls(){}};
 vm.createContext(ctx);vm.runInContext(src.slice(start,end)+';syncChartControl();',ctx);
 assert.equal(el('toggle').disabled,false);assert.equal(el('toggle').textContent,'Stop Runner');assert.equal(el('override-entry').disabled,true);
 ctx.lastRunner.running=false;vm.runInContext('syncChartControl();',ctx);assert.equal(el('toggle').disabled,true);
});
