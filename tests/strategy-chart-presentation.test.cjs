const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
test('per-chart table control validates origin, parent, account, instrument and instance before saving',()=>{
 const start=source.indexOf("  if(aiRuntimeEmbedded)window.addEventListener('message',event=>{");
 const end=source.indexOf("\n  });",start)+7;
 let handler,saves=0,syncs=0;
 const parent={postMessage(){}},settings={hidePineTables:false};
 vm.runInNewContext(source.slice(start,end),{aiRuntimeEmbedded:true,window:{parent,addEventListener:(_,fn)=>handler=fn},location:{origin:'https://example.test'},aiRuntimeParams:new URLSearchParams({chartSource:'a',chartInstance:'call'}),chartSymbol:()=> 'CALL',settings,syncPineTableControls:()=>syncs++,save:()=>saves++});
 const valid={origin:'https://example.test',source:parent,data:{type:'sector-pulse-chart-tables',account:'a',instance:'call',symbol:'CALL',visible:false}};
 for(const event of [{...valid,origin:'https://other.test'},{...valid,source:{}},...['account','instance','symbol'].map(key=>({...valid,data:{...valid.data,[key]:'wrong'}})),{...valid,data:{...valid.data,visible:'false'}}])handler(event);
 assert.equal(saves,0);assert.equal(settings.hidePineTables,false);
 handler(valid);assert.equal(settings.hidePineTables,true);assert.equal(saves,1);assert.equal(syncs,1);
 handler({...valid,data:{...valid.data,visible:true}});assert.equal(settings.hidePineTables,false);
});
test('crowded target labels can be separated without changing their price geometry',()=>{
 require('../ai-renko-v1-display.js');const {placeReferenceLabel}=globalThis.SectorPulseAiV1Display;
 const occupied=[],boxes=[];
 for(let i=0;i<8;i++)boxes.push(placeReferenceLabel({left:100,top:160,width:110,height:22},occupied,{width:480,height:500}));
 for(let i=0;i<boxes.length;i++)for(let j=0;j<i;j++){
  const a=boxes[i],b=boxes[j];assert.ok(a.left+a.width<=b.left||b.left+b.width<=a.left||a.top+a.height<=b.top||b.top+b.height<=a.top);
 }
});
