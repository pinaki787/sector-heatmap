const fs=require('node:fs'),test=require('node:test'),assert=require('node:assert/strict');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const a=source.indexOf('  function bindCompactDrawingControls('),b=source.indexOf('  function bindDrawingDockHandle(',a);assert.ok(a>=0&&b>a);
function setup(narrow=false){
 const dom=new JSDOM('<main><aside class="sp-chart-tools"><details id="lines"><summary>Lines</summary></details><button data-action="measure-chart" aria-label="Measure"><small>Measure</small></button><button data-drawing="zoom-area" aria-label="Zoom to a bar range"></button><button data-drawing="eraser" aria-label="Erase drawings"></button><button data-action="keep-drawing" aria-label="Keep drawing tool active" aria-pressed="true"></button><div class="sp-chart-magnet-control"><button aria-label="Magnet">Magnet</button></div><button data-action="hide-drawings" aria-label="Hide drawings">Hide</button><button data-action="lock-all-drawings" aria-label="Lock all shapes" disabled></button><details id="drawings"><summary>Drawings</summary></details></aside></main>',{runScripts:'outside-only'});
 let update;const media={matches:narrow,addEventListener:(type,cb)=>{assert.equal(type,'change');update=cb}};
 dom.window.eval('const chartToolbarIcon=()=>"<svg></svg>";'+source.slice(a,b)+';window.bind=bindCompactDrawingControls');
 const root=dom.window.document.querySelector('main'),rail=root.querySelector('aside');
 const original=[...rail.querySelectorAll(':scope > button')],measure=original[0];let clicks=0;measure.addEventListener('click',()=>clicks++);
 dom.window.bind(root,media);const group=rail.querySelector('[data-compact-drawing-controls]');
 return {dom,root,rail,group,original,measure,clicks:()=>clicks,resize:matches=>{media.matches=matches;update();}};
}
test('narrow controls retain original nodes, disabled/pressed state and handlers',()=>{
 const f=setup(true);assert.equal(f.group.hidden,false);
 assert.equal(f.group.querySelectorAll('button').length,5);assert.equal(f.measure.parentElement,f.group.querySelector('.sp-chart-layout-menu'));
 assert.equal(f.root.querySelector('[data-action="keep-drawing"]').getAttribute('aria-pressed'),'true');
 assert.equal(f.root.querySelector('[data-action="lock-all-drawings"]').disabled,true);
 f.group.open=true;f.measure.click();assert.equal(f.clicks(),1);assert.equal(f.group.open,false);
 assert.equal(f.root.querySelectorAll('[data-action="measure-chart"]').length,1);f.dom.window.close();
});
test('desktop resize restores exact control order without duplicate actions',()=>{
 const f=setup(true);f.resize(false);
 assert.equal(f.group.hidden,true);
 assert.deepEqual([...f.rail.querySelectorAll(':scope > button')],f.original);
 f.measure.click();assert.equal(f.clicks(),1);
 f.resize(true);f.resize(false);assert.deepEqual([...f.rail.querySelectorAll(':scope > button')],f.original);
 assert.equal(f.root.querySelectorAll('[data-action="keep-drawing"]').length,1);f.dom.window.close();
});
test('breakpoint change preserves a focused control and opens its compact menu',()=>{
 const f=setup(false);f.measure.focus();f.resize(true);
 assert.equal(f.group.open,true);assert.equal(f.dom.window.document.activeElement,f.measure);
 f.resize(false);assert.equal(f.dom.window.document.activeElement,f.measure);assert.equal(f.group.hidden,true);f.dom.window.close();
});
test('Escape closes compact controls and returns focus to their summary',()=>{
 const f=setup(true);f.group.open=true;f.measure.focus();
 const e=new f.dom.window.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true});f.measure.dispatchEvent(e);
 assert.equal(e.defaultPrevented,true);assert.equal(f.group.open,false);assert.equal(f.dom.window.document.activeElement,f.group.querySelector('summary'));f.dom.window.close();
});
test('other drawing groups and compact controls exclude overlapping menus',()=>{
 const f=setup(true),lines=f.root.querySelector('#lines');
 lines.open=true;f.group.open=true;f.group.dispatchEvent(new f.dom.window.Event('toggle'));
 assert.equal(lines.open,false);
 lines.open=true;lines.dispatchEvent(new f.dom.window.Event('toggle'));assert.equal(f.group.open,false);f.dom.window.close();
});
test('binding twice does not duplicate controls or labels',()=>{
 const f=setup(true);f.dom.window.bind(f.root,{matches:true,addEventListener:()=>{}});
 assert.equal(f.root.querySelectorAll('[data-compact-drawing-controls]').length,1);
 assert.equal(f.root.querySelectorAll('.sp-chart-compact-control-label').length,5);f.dom.window.close();
});
