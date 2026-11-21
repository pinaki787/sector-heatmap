const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const body=source.match(/^    panel.querySelector\('\.sp-chart-legend'\).addEventListener\('focusout',[\s\S]*?^    \}\)\);/m)?.[0];assert.ok(body);
function fixture(){
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div data-row><input value="5"><button data-hide>Hide</button><details><summary>More</summary></details></div></div><button data-outside>Outside</button></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),legend=panel.querySelector('.sp-chart-legend');
 panel.open=true;let redraws=0,actions=0;w.panel=panel;
 w.drawLegend=()=>{redraws++;legend.firstElementChild.replaceWith(legend.firstElementChild.cloneNode(true));};
 w.eval(body);legend.addEventListener('click',e=>{if(e.target.matches('[data-hide]'))actions++;});
 return {dom,w,panel,legend,get redraws(){return redraws},get actions(){return actions},flush:()=>new Promise(r=>w.queueMicrotask(r))};
}
test('field-to-action focus preserves the first hide click after editing',async()=>{
 const f=fixture(),input=f.legend.querySelector('input'),button=f.legend.querySelector('button');
 input.focus();input.value='6';button.focus();await f.flush();
 if(button.isConnected)button.click();
 assert.equal(f.actions,1);assert.equal(f.redraws,0);f.dom.window.close();
});
test('keyboard focus between indicator controls retains the destination',async()=>{
 const f=fixture(),input=f.legend.querySelector('input'),summary=f.legend.querySelector('summary');
 input.focus();input.value='6';summary.focus();await f.flush();
 assert.equal(f.w.document.activeElement,summary);assert.equal(summary.isConnected,true);assert.equal(f.redraws,0);f.dom.window.close();
});
test('leaving the indicator legend still refreshes edited markup',async()=>{
 const f=fixture();f.legend.querySelector('input').focus();f.panel.querySelector('[data-outside]').focus();await f.flush();
 assert.equal(f.redraws,1);f.dom.window.close();
});
test('closed chart does not redraw on focus departure',async()=>{
 const f=fixture();f.panel.open=false;f.legend.querySelector('input').focus();f.panel.querySelector('[data-outside]').focus();await f.flush();
 assert.equal(f.redraws,0);f.dom.window.close();
});

test('pointer action survives synchronous field change redraw and commits after delegated click',async()=>{
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div class="sp-chart-study"><details data-study-settings open><summary>Settings</summary><input value="5"></details><button data-hide>Hide</button></div></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),input=panel.querySelector('input'),button=panel.querySelector('button'),details=panel.querySelector('details');
 panel.open=true;w.panel=panel;w.stage=panel;let actions=0,changes=0,flushes=0;w.drawLegend=()=>{assert.equal(changes,1);flushes++;};
 const first=source.indexOf('    let pendingStudyPointerAction;'),last=source.indexOf("    panel.addEventListener('keydown'",first);
 assert.ok(first>=0&&last>first);w.eval(source.slice(first,last));
 input.addEventListener('blur',()=>{changes++;details.parentElement.replaceWith(details.parentElement.cloneNode(true));});
 panel.addEventListener('click',e=>{if(e.target.closest('[data-hide]'))actions++;});
 input.focus();input.value='6';const down=new w.Event('pointerdown',{bubbles:true,cancelable:true});button.dispatchEvent(down);
 if(!down.defaultPrevented)button.focus();
 assert.equal(down.defaultPrevented,true);assert.equal(button.isConnected,true);
 button.click();assert.equal(actions,1);assert.equal(changes,0);
 await new Promise(resolve=>w.queueMicrotask(resolve));assert.equal(changes,1);assert.equal(flushes,1);assert.equal(details.open,false);
 dom.window.close();
});

test('rebuilding edited indicator markup retains its own open action menu',()=>{
 const dom=new JSDOM('<div id="legend"><div class="sp-chart-study"><details data-study-settings><summary>Settings</summary></details><details data-study-more open><summary>More</summary></details></div></div>');
 const document=dom.window.document,legend=document.querySelector('#legend'),study={},map=new WeakMap();
 map.set(legend.querySelector('[data-study-settings]'),study);legend.querySelector('[data-study-more] summary').focus();
 const capture=source.slice(source.indexOf("    const open = legend.querySelector('[data-study-settings][open]');"),source.indexOf('    const referenceSettingsOpen =',source.indexOf("    const open = legend.querySelector('[data-study-settings][open]');")));
 const restore=source.slice(source.indexOf('      if (study === moreStudy) {'),source.indexOf('      if (study !== activeStudy) continue;',source.indexOf('      if (study === moreStudy) {')));
 assert.ok(restore.includes('restoredMore.open = true'));
 const build=new Function('legend','legendStudySettings','document',capture+' return (row,study)=>{'+restore+'};');
 const apply=build(legend,map,document),row=legend.firstElementChild.cloneNode(true);row.querySelector('[data-study-more]').open=false;
 legend.firstElementChild.replaceWith(row);apply(row,study);
 assert.equal(row.querySelector('[data-study-more]').open,true);assert.equal(document.activeElement,row.querySelector('[data-study-more] summary'));
 const unrelated=row.cloneNode(true);unrelated.querySelector('[data-study-more]').open=false;apply(unrelated,{});assert.equal(unrelated.querySelector('[data-study-more]').open,false);
 dom.window.close();
});

test('pointerup does not release a pending button before a later click task',async()=>{
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div class="sp-chart-study"><details data-study-settings open><summary>Settings</summary><input></details><button data-hide>Hide</button></div></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),input=panel.querySelector('input'),button=panel.querySelector('button');
 w.panel=panel;w.stage=panel;panel.open=true;let redraws=0;w.drawLegend=()=>redraws++;
 const first=source.indexOf('    let pendingStudyPointerAction;'),last=source.indexOf("    panel.addEventListener('keydown'",first);
 w.eval(source.slice(first,last));input.focus();
 button.dispatchEvent(new w.Event('pointerdown',{bubbles:true,cancelable:true}));
 button.dispatchEvent(new w.Event('pointerup',{bubbles:true}));
 await new Promise(r=>w.setTimeout(r,10));assert.equal(w.legendPointerInteraction,true);assert.equal(redraws,0);
 button.click();await new Promise(r=>w.setTimeout(r,10));assert.equal(w.legendPointerInteraction,false);
 dom.window.close();
});

test('edited-field menu summary toggles before committing can replace its node',async()=>{
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div class="sp-chart-study"><details data-study-settings open><summary>Settings</summary><input></details><details data-study-more><summary>More</summary></details></div></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),input=panel.querySelector('input'),summary=panel.querySelector('[data-study-more] summary');
 w.panel=panel;w.stage=panel;panel.open=true;w.drawLegend=()=>{};
 const first=source.indexOf('    let pendingStudyPointerAction;'),last=source.indexOf("    panel.addEventListener('keydown'",first);w.eval(source.slice(first,last));
 input.focus();summary.dispatchEvent(new w.Event('pointerdown',{bubbles:true,cancelable:true}));
 const click=new w.MouseEvent('click',{bubbles:true,cancelable:true});summary.dispatchEvent(click);
 assert.equal(click.defaultPrevented,true);assert.equal(summary.parentElement.open,true);
 await new Promise(r=>w.queueMicrotask(r));assert.equal(summary.parentElement.open,true);dom.window.close();
});

test('settings summary toggles before redraw even with no focused field',async()=>{
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div class="sp-chart-study"><details data-study-settings><summary>Settings</summary><input></details></div></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),summary=panel.querySelector('summary');w.panel=panel;w.stage=panel;panel.open=true;
 w.drawLegend=()=>{const row=panel.querySelector('.sp-chart-study');row.replaceWith(row.cloneNode(true));};
 const first=source.indexOf('    let pendingStudyPointerAction;'),last=source.indexOf("    panel.addEventListener('keydown'",first);w.eval(source.slice(first,last));
 summary.focus();summary.dispatchEvent(new w.Event('pointerdown',{bubbles:true,cancelable:true}));
 const click=new w.MouseEvent('click',{bubbles:true,cancelable:true});summary.dispatchEvent(click);
 assert.equal(click.defaultPrevented,true);await new Promise(r=>w.queueMicrotask(r));assert.equal(panel.querySelector('details').open,true);dom.window.close();
});

for(const direct of [false,true])test('settings section '+(direct?'radio':'label')+' survives blur/change markup replacement',async()=>{
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div class="sp-chart-study"><details data-study-settings open><summary>Settings</summary><div class="sp-study-settings-tabs"><label><input type="radio" name="section" value="Inputs">Inputs</label><label><input type="radio" name="section" value="Style" checked>Style</label></div><select><option>2</option><option>4</option></select></details></div></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),select=panel.querySelector('select'),radio=panel.querySelector('input[value="Inputs"]'),label=radio.parentElement;
 w.panel=panel;w.stage=panel;panel.open=true;w.drawLegend=()=>{};
 select.addEventListener('blur',()=>{const row=panel.querySelector('.sp-chart-study');row.replaceWith(row.cloneNode(true));});
 const first=source.indexOf('    let pendingStudyPointerAction;'),last=source.indexOf("    panel.addEventListener('keydown'",first);w.eval(source.slice(first,last));
 select.focus();select.value='4';const target=direct?radio:label;
 const down=new w.Event('pointerdown',{bubbles:true,cancelable:true});target.dispatchEvent(down);assert.equal(down.defaultPrevented,true);
 target.click();await new Promise(r=>w.queueMicrotask(r));
 assert.equal(panel.querySelector('input[value="Inputs"]').checked,true);assert.equal(panel.querySelector('input[value="Style"]').checked,false);
 dom.window.close();
});

for(const direct of [false,true])test('edited field to checkbox '+(direct?'control':'label')+' commits its first toggle before redraw',async()=>{
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div class="sp-chart-study"><details data-study-settings open><summary>Settings</summary><select><option>2</option><option>4</option></select><label><input type="checkbox" data-test-check>Wait</label></details></div></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),select=panel.querySelector('select'),checkbox=panel.querySelector('input'),label=checkbox.parentElement;
 w.panel=panel;w.stage=panel;panel.open=true;let model=false;
 w.drawLegend=()=>{if(w.legendPointerInteraction)return;const row=panel.querySelector('.sp-chart-study'),copy=row.cloneNode(true);copy.querySelector('input').checked=model;row.replaceWith(copy);};
 select.addEventListener('blur',()=>w.drawLegend());panel.addEventListener('change',e=>{if(e.target.hasAttribute('data-test-check')){model=e.target.checked;w.drawLegend();}});
 const first=source.indexOf('    let pendingStudyPointerAction;'),last=source.indexOf("    panel.addEventListener('keydown'",first);w.eval(source.slice(first,last));
 select.focus();select.value='4';const target=direct?checkbox:label;const down=new w.Event('pointerdown',{bubbles:true,cancelable:true});target.dispatchEvent(down);assert.equal(down.defaultPrevented,true);
 target.click();await new Promise(r=>w.queueMicrotask(r));assert.equal(model,true);assert.equal(panel.querySelector('input').checked,true);dom.window.close();
});
test('disabled checkbox does not arm a pointer guard that can never receive click',()=>{
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><div class="sp-chart-study"><details data-study-settings open><summary>Settings</summary><select><option>2</option></select><label><input type="checkbox" disabled>Unavailable</label></details></div></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel');w.panel=panel;w.stage=panel;w.drawLegend=()=>{};panel.open=true;
 const first=source.indexOf('    let pendingStudyPointerAction;'),last=source.indexOf("    panel.addEventListener('keydown'",first);w.eval(source.slice(first,last));panel.querySelector('select').focus();
 const input=panel.querySelector('input');input.dispatchEvent(new w.Event('pointerdown',{bubbles:true,cancelable:true}));assert.equal(w.legendPointerInteraction,false);assert.equal(input.checked,false);dom.window.close();
});
