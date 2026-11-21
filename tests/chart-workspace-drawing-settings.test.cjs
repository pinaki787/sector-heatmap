const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync('chart-workspace.js','utf8');
const start=source.indexOf('  function organizeDrawingSettings(form, visibility) {');
const end=source.indexOf('  function editDrawing(index, button) {',start);
assert.ok(start>=0&&end>start);
function fixture(extra='',text=true){
 const dom=new JSDOM('<form><div class="sp-chart-drawing-fields">'+
  '<label>Name<input name="drawingName" value="Original &amp; exact"></label>'+
  '<label>Start price<input type="number" name="StartPrice" required value="63851.14541509974"></label>'+
  '<label>Start time<input type="datetime-local" name="StartTime" value="2026-11-16T23:00"></label>'+
  '<label>End price<input type="number" name="EndPrice" value="64682.37348527518"></label>'+
  '<label>Stroke<select name="style"><option value="solid">Solid</option><option value="dashed" selected>Dashed</option></select></label>'+
  '<label>Width<select name="width"><option>1</option><option selected>3</option></select></label>'+
  '<label>Color<input name="color" type="color" value="#2962ff"></label>'+
  (text?'<label>Text<input name="annotation" value="Keep this annotation"></label><label>Bold<input name="rectangleTextBold" type="checkbox" checked></label>':'')+
  extra+
  '<fieldset data-visibility><legend>Visibility</legend><label><input name="unit" value="h" type="checkbox" checked>Hours</label><label><input name="unit" value="m" type="checkbox" checked>Minutes</label><label><input name="bound" value="0.5"></label><label><input name="ignored" value="disabled" disabled></label></fieldset>'+
  '</div><footer><button type="submit">Apply</button></footer></form>',{runScripts:'outside-only'});
 dom.window.eval(source.slice(start,end)+';window.organize=organizeDrawingSettings;');
 const form=dom.window.document.querySelector('form'),visibility=form.querySelector('[data-visibility]');
 const values=()=>[...new dom.window.FormData(form)].map(([key,value])=>[key,String(value)]).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
 const before=values(),controls=[...form.elements],events=[];
 for(const control of controls)control.addEventListener('change',()=>events.push(control.name));
 dom.window.organize(form,visibility);
 return {dom,form,values,before,controls,events,close:()=>dom.window.close()};
}
test('tab organization retains exact data, existing controls, handlers and disabled/duplicate fields',()=>{
 const f=fixture('<details><summary>Fib levels</summary><input name="fibLevels" value="0, 44, 50, 56, 100"><input name="fibArcRatios" value="0.618, 1.618"></details>');
 assert.deepEqual(f.values(),f.before);
 for(const control of f.controls)assert.ok([...f.form.elements].includes(control));
 f.form.elements.namedItem('StartPrice').dispatchEvent(new f.dom.window.Event('change'));
 assert.deepEqual(f.events,['StartPrice']);
 for(const tab of f.form.querySelectorAll('[role="tab"]'))tab.click();
 assert.deepEqual(f.values(),f.before);
 assert.equal(f.form.elements.namedItem('StartPrice').value,'63851.14541509974');
 f.close();
});
test('complex anchor, annotation and visibility settings stay available in their sections',()=>{
 const f=fixture('<label>Control<input name="Control2Price" value="0.0000000123456789"></label><label>Vertex<input name="Vertex12Time" value="2026-11-16T23:00"></label><label>Fill<input name="fillOpacity" value="25"></label>');
 for(const name of ['StartPrice','StartTime','EndPrice','Control2Price','Vertex12Time'])
  assert.equal(f.form.elements.namedItem(name).closest('[role="tabpanel"]').dataset.drawingSettingsPage,'Coordinates');
 assert.equal(f.form.elements.namedItem('annotation').closest('[role="tabpanel"]').dataset.drawingSettingsPage,'Text');
 assert.equal(f.form.elements.namedItem('fillOpacity').closest('[role="tabpanel"]').dataset.drawingSettingsPage,'Style');
 assert.deepEqual(f.values(),f.before);f.close();
});
test('keyboard tab navigation exposes one panel and keeps active tab focus',()=>{
 const f=fixture(),tabs=[...f.form.querySelectorAll('[role="tab"]')];
 const press=(tab,key)=>tab.dispatchEvent(new f.dom.window.KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}));
 press(tabs[0],'ArrowLeft');
 assert.equal(f.dom.window.document.activeElement,tabs.at(-1));
 assert.equal(tabs.at(-1).getAttribute('aria-selected'),'true');
 press(tabs.at(-1),'Home');
 assert.equal(f.dom.window.document.activeElement,tabs[0]);
 press(tabs[0],'End');
 assert.equal(f.dom.window.document.activeElement,tabs.at(-1));
 assert.equal([...f.form.querySelectorAll('[role="tabpanel"]')].filter(p=>!p.hidden).length,1);
 assert.deepEqual(f.values(),f.before);f.close();
});
test('hidden invalid coordinates open their panel and empty Text sections do not create tabs',()=>{
 const f=fixture('',false);
 assert.deepEqual([...f.form.querySelectorAll('[role="tab"]')].map(t=>t.textContent),['Style','Coordinates','Visibility']);
 f.form.elements.namedItem('StartPrice').value='';
 assert.equal(f.form.checkValidity(),false);
 const selected=f.form.querySelector('[role="tab"][aria-selected="true"]');
 assert.equal(selected.textContent,'Coordinates');
 assert.equal(f.form.querySelector('[data-drawing-settings-page="Coordinates"]').hidden,false);
 f.close();
});
