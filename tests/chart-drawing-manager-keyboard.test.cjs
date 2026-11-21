const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
function fixture(){
 const dom=new JSDOM('<button data-action="manage-drawings" aria-expanded="true">Manage drawings</button><details id="sp-chart-drawing-list" open><summary>Drawings</summary><input type="search" value="Fib"><input type="checkbox" checked></details>');
 const panel=dom.window.document,from=source.indexOf("    const drawingList = panel.querySelector('#sp-chart-drawing-list');"),to=source.indexOf("    panel.querySelector('[data-find-drawing]')",from);assert.ok(from>=0&&to>from);
 vm.runInNewContext(source.slice(from,to),{panel,settings:{drawingToolbarHidden:false}});
 const input=panel.querySelector('input');input.focus();
 return {dom,panel,input,list:panel.querySelector('details'),key:(options={})=>{const e=new dom.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true,...options});input.dispatchEvent(e);return e}};
}
test('Escape closes manager from search, retains query/selection and restores trigger focus',()=>{
 const f=fixture(),e=f.key();assert.equal(e.defaultPrevented,true);assert.equal(f.list.open,false);assert.equal(f.input.value,'Fib');assert.equal(f.panel.querySelector('[type=checkbox]').checked,true);assert.equal(f.panel.activeElement,f.panel.querySelector('button'));f.dom.window.close();
});
test('composing Escape does not dismiss manager',()=>{const f=fixture();assert.equal(f.key({isComposing:true}).defaultPrevented,false);assert.equal(f.list.open,true);f.dom.window.close()});
test('Escape already handled by an inner field remains handled there',()=>{const f=fixture();f.input.addEventListener('keydown',e=>e.preventDefault());f.key();assert.equal(f.list.open,true);f.dom.window.close()});
