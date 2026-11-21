const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),test=require('node:test');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const kinds=source.match(/  const pineDrawingKinds = \[[^\n]+\];/)[0];
const from=source.indexOf('          const needsDrawingPane = evaluation =>'),to=source.indexOf('          const hasPaneDrawings',from);
assert.ok(from>=0&&to>from);
function needs(objects,{hidden={},price=false,manual=[]}={}){
 const context={study:{hiddenPineDrawings:hidden},pineUsesPricePane:()=>price,drawings:manual};
 const f=vm.runInNewContext(kinds+source.slice(from,to)+';needsDrawingPane',context);
 return f({plots:Object.fromEntries(Object.entries(objects).map(([kind,value])=>['__'+kind+'__',{data:[{value}]}]))});
}
test('separate-pane Pine table is detected with no manual drawings',()=>assert.equal(needs({tables:[{force_overlay:false}]}),true));
test('manual drawing objects cannot shadow Pine object categories',()=>assert.equal(needs({lines:[{force_overlay:false}]},{manual:[{kind:'rectangle'}]}),true));
test('hidden/deleted/forced-price objects do not create a separate pane',()=>{
 assert.equal(needs({tables:[{}]},{hidden:{tables:true}}),false);
 assert.equal(needs({tables:[{_deleted:true}]}),false);
 assert.equal(needs({tables:[{force_overlay:true}]}),false);
 assert.equal(needs({tables:[{}]},{price:true}),false);
});
test('object-only studies pass both pane-creation gates',()=>{
 assert.match(source,/if \(!shading.length && !attachPaneMarkers && !plots.some\(\(_, index\) => shown\(index\)\)\) continue;/);
 assert.match(source,/if \(wantsPane && \(attachPaneMarkers \|\| plots.some/);
});
