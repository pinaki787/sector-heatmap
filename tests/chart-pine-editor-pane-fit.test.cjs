const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
function setup(minima=[120,72,72,72],stageHeight=330){
 const settings={editorBottomHeight:320},written=[];
 const pane=(minimum,other={})=>({styleInfo:{display:'block',minHeight:minimum+'px'},offsetHeight:minimum,matches:()=>true,hasAttribute:()=>false,...other});
 const stage={isConnected:true,clientHeight:stageHeight,children:[...minima.map(n=>pane(n)),pane(6,{matches:()=>false})]};
 const container={clientHeight:900},editor={offsetHeight:320,style:{setProperty:(k,v)=>{written.push(v);editor.offsetHeight=parseInt(v);}}};
 const ctx={settings,stage,panel:{querySelector:s=>s==='.sp-chart-content'?container:editor},getComputedStyle:e=>e.styleInfo};
 const a=source.indexOf('  function applyPineBottomHeight('),b=source.indexOf('  function syncPineEditorPlacement(',a);assert.ok(a>=0&&b>a);
 vm.createContext(ctx);vm.runInContext(source.slice(a,b),ctx);return {ctx,settings,stage,container,editor,written,pane};
}
test('captured three-pane narrow geometry fits by reducing displayed editor320to308 without changing preference',()=>{const f=setup();f.ctx.applyPineBottomHeight();assert.equal(f.written.at(-1),'308px');assert.equal(f.settings.editorBottomHeight,320);});
test('larger viewport restores preferred editor height rather than keeping temporary constrained size',()=>{const f=setup();f.ctx.applyPineBottomHeight();f.container.clientHeight=1200;f.stage.clientHeight=700;f.ctx.applyPineBottomHeight();assert.equal(f.written.at(-1),'320px');assert.equal(f.settings.editorBottomHeight,320);});
test('hidden panes reserve no space while collapsed panes reserve only their actual strip',()=>{const f=setup([120,72],280);f.stage.children.push(f.pane(72,{styleInfo:{display:'none',minHeight:'72px'}}),f.pane(0,{offsetHeight:34,hasAttribute:()=>true}));f.ctx.applyPineBottomHeight();assert.equal(f.written.at(-1),'320px');});
test('impossible many-pane geometry keeps usable editor minimum rather than shrinking it to zero',()=>{const f=setup([120,...Array(10).fill(72)]);f.ctx.applyPineBottomHeight();assert.equal(f.written.at(-1),'150px');assert.equal(f.settings.editorBottomHeight,320);});
test('explicit drag remembers its constrained height, while disconnected chart uses normal cap',()=>{const f=setup();f.ctx.applyPineBottomHeight(450,true);assert.equal(f.settings.editorBottomHeight,308);f.stage.isConnected=false;f.ctx.applyPineBottomHeight(320);assert.equal(f.written.at(-1),'320px');});

