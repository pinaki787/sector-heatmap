const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
function fixture(){
 const dom=new JSDOM(`<main><div class="toolbar"><details data-chart-type-picker open><summary>Chart type</summary><button type="button" data-action="renko-settings">Renko settings…</button></details><details data-chart-settings><summary>Chart settings</summary><div class="sp-chart-settings-menu"><div role="tablist"><button data-chart-settings-tab="symbol" aria-selected="true">Symbol</button><button data-chart-settings-tab="renko" aria-selected="false">Renko</button></div><section data-chart-settings-page="symbol"></section><section data-chart-settings-page="renko" hidden><select data-brick-method><option selected>ATR</option><option>Traditional</option></select><input value="7"></section></div></details></div></main>`,{runScripts:'outside-only'});
 const helpers=source.slice(source.indexOf('  function openRenkoSettings() {'),source.indexOf('  async function change(event) {'));
 const bindingStart=source.indexOf('    // Handle the menu transfer at its originating control');
 const binding=source.slice(bindingStart,source.indexOf('    const settingsTabs =',bindingStart));
 assert.ok(helpers.includes('function selectChartSettingsTab'));
 dom.window.eval('const panel=document.querySelector("main");let reads=0;function updateRenkoBoxReadout(){reads++;}'+helpers+binding+';window.reads=()=>reads;');
 return {dom,root:dom.window.document.querySelector('main'),shortcut:dom.window.document.querySelector('[data-action="renko-settings"]')};
}
test('Renko shortcut opens construction tab directly without delegated menu interception',()=>{
 const f=fixture();let delegated=0;
 f.root.querySelector('.toolbar').addEventListener('click',()=>{delegated++;f.root.querySelector('[data-chart-settings]').open=false;});
 f.shortcut.click();
 assert.equal(f.root.querySelector('[data-chart-type-picker]').open,false);
 assert.equal(f.root.querySelector('[data-chart-settings]').open,true);assert.equal(delegated,0);
 assert.equal(f.root.querySelector('[data-chart-settings-page=renko]').hidden,false);
 assert.equal(f.root.querySelector('[data-chart-settings-page=symbol]').hidden,true);
 assert.equal(f.root.querySelector('[data-chart-settings-tab=renko]').getAttribute('aria-selected'),'true');
 assert.equal(f.dom.window.document.activeElement,f.root.querySelector('[data-brick-method]'));
 assert.equal(f.root.querySelector('select').value,'ATR');assert.equal(f.root.querySelector('input').value,'7');
 assert.equal(f.dom.window.reads(),1);f.dom.window.close();
});
test('reopening settings restores construction focus without changing method or length',()=>{
 const f=fixture();f.shortcut.click();const menu=f.root.querySelector('[data-chart-settings]');menu.open=false;
 f.root.querySelector('select').value='Traditional';f.root.querySelector('input').value='19';
 f.shortcut.click();assert.equal(menu.open,true);
 assert.equal(f.root.querySelector('select').value,'Traditional');assert.equal(f.root.querySelector('input').value,'19');
 assert.equal(f.dom.window.document.activeElement,f.root.querySelector('select'));f.dom.window.close();
});
