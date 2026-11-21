const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const first=source.includes('    let pendingStudyPointerAction;') ? source.indexOf('    let pendingStudyPointerAction;') : source.indexOf("    panel.addEventListener('pointerdown', event => {\n      const open = panel.querySelector('[data-study-settings][open]");
const last=source.indexOf("    panel.addEventListener('keydown'",first);
assert.ok(first>=0&&last>first);
async function fixture(action){
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><details data-study-settings open><summary>Settings</summary><select><option>4</option></select><button type="button" '+action+'>Action</button></details></div></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),input=panel.querySelector('select'),button=panel.querySelector('button'),details=panel.querySelector('details');
 w.panel=panel;w.stage=panel;w.eval(source.slice(first,last));
 // This is the actual focusout redraw hazard: edited markup replaces the row.
 input.addEventListener('focusout',()=>w.queueMicrotask(()=>{if(w.document.activeElement!==input&&details.open)details.replaceWith(details.cloneNode(true));}));
 panel.addEventListener('click',e=>{if(e.target.closest('[data-close-study-settings]')){details.open=false;details.querySelector('summary').focus();}});
 input.focus();const down=new w.Event('pointerdown',{bubbles:true,cancelable:true});button.dispatchEvent(down);
 if(!down.defaultPrevented)button.focus();
 await new Promise(resolve=>w.queueMicrotask(resolve));
 if(button.isConnected)button.click();
 return{dom,details,button,down,input,w};
}
test('first close click survives focusout after a changed field',async()=>{
 const f=await fixture('data-close-study-settings');
 assert.equal(f.down.defaultPrevented,true);
 assert.equal(f.button.isConnected,true);
 assert.equal(f.details.open,false);
 assert.equal(f.w.document.activeElement.tagName,'SUMMARY');f.dom.window.close();
});
test('defaults retains its existing focus-preservation behavior',async()=>{
 const f=await fixture('data-study-defaults');
 assert.equal(f.down.defaultPrevented,true);assert.equal(f.button.isConnected,true);f.dom.window.close();
});
test('unrelated buttons keep normal pointer focus behavior',async()=>{
 const f=await fixture('data-other-action');
 assert.equal(f.down.defaultPrevented,false);f.dom.window.close();
});
test('new volume and range studies participate in broker-backed calculation intervals',()=>{
 const body=source.match(/const calculationTimeframeStudies = new Set\(\[([\s\S]*?)\]\);/)?.[1];
 assert.ok(body);const kinds=new Function('return ['+body+']')();
 for(const k of ['ADR','NVI','PVI'])assert.ok(kinds.includes(k),k);
});
