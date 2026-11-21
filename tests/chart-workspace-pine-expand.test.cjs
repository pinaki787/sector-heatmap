const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync('chart-workspace.js','utf8');
function fixture(){
 const dom=new JSDOM('<main id="sp-chart-workspace"></main>',{runScripts:'outside-only'});
 dom.window.HTMLElement.prototype.scrollTo=function(x,y){this.scrollLeft=x;this.scrollTop=y;};
 const start=source.indexOf('  const pineTableExpanded ='),end=source.indexOf('  const workerPineResults =',start);
 assert.ok(start>=0&&end>start);
 dom.window.eval('function save(){}\n'+source.slice(start,end)+';window.tables={appendPineTables,updatePineTables};');
 const host=dom.window.document.querySelector('main'),study={name:'Private study'},views=[];
 const data=text=>[{position:'middle_right',cells:[[{text:'Levels'}],[{text}]]}];
 const overlays=dom.window.tables.appendPineTables(host,data('First'),study,undefined,views,900);
 return {dom,host,study,data,overlays,api:dom.window.tables};
}
test('expand reads more rows without toggling disclosure or replacing table controls during live updates',()=>{
 const f=fixture(),overlay=f.overlays[0],button=overlay.querySelector('button');
 assert.equal(overlay.hasAttribute('data-pine-expanded'),false);button.click();
 assert.equal(overlay.open,true);assert.equal(overlay.hasAttribute('data-pine-expanded'),true);
 assert.equal(button.getAttribute('aria-label'),'Compact table: Levels');
 f.api.updatePineTables(f.host,f.overlays,f.data('Latest tick'),f.study);
 assert.equal(f.overlays[0],overlay);assert.equal(overlay.querySelector('button'),button);
 assert.equal(overlay.querySelector('table').textContent,'LevelsLatest tick');
 assert.equal(overlay.hasAttribute('data-pine-expanded'),true);
 button.click();assert.equal(overlay.hasAttribute('data-pine-expanded'),false);assert.equal(overlay.open,true);
 f.dom.window.close();
});
test('expanded table survives narrow reconstruction but other studies keep compact defaults',()=>{
 const f=fixture();f.overlays[0].querySelector('button').click();f.host.replaceChildren();
 const rebuilt=f.api.appendPineTables(f.host,f.data('Narrow'),f.study,undefined,[],400)[0];
 assert.equal(rebuilt.open,true);assert.equal(rebuilt.hasAttribute('data-pine-auto-collapse'),false);
 const other=f.api.appendPineTables(f.host,f.data('Other'),{},undefined,[],400)[0];
 assert.equal(other.hasAttribute('data-pine-expanded'),false);assert.equal(other.open,false);
 f.dom.window.close();
});
test('changing script table captions keeps expansion control and accessible region current',()=>{
 const f=fixture(),overlay=f.overlays[0],button=overlay.querySelector('button');button.click();
 const changed=[{position:'middle_right',cells:[[{text:'Updated levels'}],[{text:'Changed values'}]]}];
 f.api.updatePineTables(f.host,f.overlays,changed,f.study);
 assert.equal(overlay.querySelector('button'),button);
 assert.equal(button.getAttribute('aria-label'),'Compact table: Updated levels');
 assert.equal(overlay.querySelector('[role=region]').getAttribute('aria-label'),'Updated levels');
 button.click();assert.equal(button.getAttribute('aria-label'),'Expand table: Updated levels');
 assert.equal(overlay.hasAttribute('data-pine-expanded'),false);f.dom.window.close();
});
