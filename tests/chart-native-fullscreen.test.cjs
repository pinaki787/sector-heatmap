const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
const helper=source.slice(source.indexOf('  function chartFullscreenControl('),source.indexOf('\n  const aiSelectionParams'));
function fixture(){
 const classes=new Set(),attrs={},status={};let change;
 const doc={fullscreenElement:null,addEventListener:(event,fn)=>{assert.equal(event,'fullscreenchange');change=fn;},async exitFullscreen(){this.fullscreenElement=null;change();}};
 const panel={classList:{toggle:(name,on)=>on?classes.add(name):classes.delete(name)},querySelector:()=>status,async requestFullscreen(){doc.fullscreenElement=this;change();}};
 const button={setAttribute:(key,value)=>attrs[key]=value};
 const fn=vm.runInNewContext(helper+';chartFullscreenControl');
 return {doc,panel,button,attrs,classes,status,toggle:fn(panel,button,doc),change};
}
test('fullscreen requests the native panel and exits without altering chart state',async()=>{
 const f=fixture();await f.toggle();assert.equal(f.doc.fullscreenElement,f.panel);assert.equal(f.attrs['aria-pressed'],'true');assert(f.classes.has('sp-chart-expanded'));
 await f.toggle();assert.equal(f.doc.fullscreenElement,null);assert.equal(f.attrs['aria-label'],'Fullscreen');
});
test('browser Escape synchronizes fullscreen button and layout',async()=>{
 const f=fixture();await f.toggle();f.doc.fullscreenElement=null;f.change();assert.equal(f.attrs['aria-pressed'],'false');assert(!f.classes.has('sp-chart-expanded'));
});
test('permission rejection restores layout and provides an actionable status',async()=>{
 const f=fixture();f.panel.requestFullscreen=async()=>{throw Error('not permitted');};await f.toggle();assert.equal(f.attrs['aria-pressed'],'false');assert.match(f.status.textContent,/not permitted/);
});
test('strategy iframe explicitly delegates fullscreen',()=>{
 const ai=fs.readFileSync('renko-ai-options.js','utf8');assert.match(ai,/frame.allowFullscreen=true;frame.setAttribute\('allow','fullscreen'\)/);
});
