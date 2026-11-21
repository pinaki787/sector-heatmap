const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),test=require('node:test');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const from=source.indexOf('  function mergePineOverlayPlots('),to=source.indexOf('  function publishWorkerPineResult(',from);assert.ok(from>=0&&to>from);
const kinds=['lines','boxes','labels','linefills','polylines','tables'];
const merge=vm.runInNewContext(source.slice(from,to)+';mergePineOverlayPlots',{pineDrawingKinds:kinds});
for(const kind of kinds)test(kind+' keeps pane objects and includes forced price objects without mutation',()=>{
 const key='__'+kind+'__',overlay='__'+kind+'_overlay__',data={plot:{data:[{value:3}]},[key]:{title:key,data:[{time:1,value:[{id:1,force_overlay:false}]}]},[overlay]:{title:overlay,data:[{time:1,value:[{id:2}]}]}};
 const before=JSON.stringify(data),out=merge(data);
 assert.equal(JSON.stringify(data),before);assert.equal(out.plot,data.plot);assert.equal(out[overlay],undefined);
 assert.equal(out[key].data[0].value.length,2);assert.equal(out[key].data[0].value[0].force_overlay,false);assert.equal(out[key].data[0].value[1].force_overlay,true);
});
test('force-only output creates a canonical stream and ordinary output is unchanged',()=>{
 const plain={Price:{data:[]}};assert.equal(merge(plain),plain);
 const out=merge({__tables_overlay__:{data:[{time:3,value:[{id:4}]}],options:{style:'table'}}});
 assert.equal(out.__tables__.data[0].value[0].force_overlay,true);assert.equal(out.__tables__.data[0].time,3);
});
test('an emptied overlay stream clears removed objects on subsequent updates',()=>{
 const out=merge({__lines__:{data:[{time:2,value:[]}]},__lines_overlay__:{data:[{time:2,value:[]}]}});
 assert.equal(out.__lines__.data[0].value.length,0);
});
