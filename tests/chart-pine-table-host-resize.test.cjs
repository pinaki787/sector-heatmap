const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
function fixture(){
 const dom=new JSDOM('<main id="sp-chart-workspace"></main>',{runScripts:'outside-only'});
 const host=dom.window.document.querySelector('main');let width=900;
 Object.defineProperty(host,'clientWidth',{get:()=>width});
 dom.window.HTMLElement.prototype.scrollTo=function(){};
 const a=source.indexOf('  const pineTableExpanded ='),b=source.indexOf('  const workerPineResults =',a);
 dom.window.eval('function save(){}\n'+source.slice(a,b)+';window.tableApi={appendPineTables};');
 const table=[{position:'top_right',cells:[[{text:'Study'}],[{text:'Value'}]]}];
 const study={},overlays=dom.window.tableApi.appendPineTables(host,table,study,undefined,[],900);
 let callback;
 dom.window.ResizeObserver=class{constructor(cb){callback=cb;}};
 const inner=dom.window.document.createElement('div');host.append(inner);
 dom.window.chart={chartElement:()=>inner,priceScale:()=>({width:()=>60})};
 dom.window.charts=[dom.window.chart];
 dom.window.eval('window.refreshPriceTables=()=>positionPineTables(document.querySelector("main"),chart)');
 dom.window.schedulePriceRatio=()=>{};dom.window.positionDrawingFavorites=()=>{};
 dom.window.paneDividers=new Map();dom.window.panel=host;
 const x=source.indexOf('    const ratioObserver = new ResizeObserver(entries => {'),y=source.indexOf('    ratioObserver.observe(',x);
 assert.ok(x>=0&&y>x);dom.window.eval(source.slice(x,y));
 return {dom,host,study,overlay:overlays[0],setWidth:n=>width=n,resize:()=>callback([{target:host}])};
}
test('final host resize collapses automatic Pine tables without a time-scale notification, and reopens on desktop',()=>{
 const f=fixture();assert.equal(f.overlay.open,true);assert.ok(f.overlay.hasAttribute('data-pine-auto-collapse'));
 f.setWidth(542);f.resize();assert.equal(f.overlay.open,false);
 f.setWidth(900);f.resize();assert.equal(f.overlay.open,true);f.dom.window.close();
});
test('explicit expanded table remains open through a narrow host resize',()=>{
 const f=fixture();f.overlay.querySelector('button').click();assert.ok(!f.overlay.hasAttribute('data-pine-auto-collapse'));
 f.setWidth(542);f.resize();assert.equal(f.overlay.open,true);f.dom.window.close();
});
test('explicit collapsed table stays closed after returning to desktop',()=>{
 const f=fixture();f.overlay.querySelector('summary').click();assert.equal(f.overlay.open,false);
 f.setWidth(542);f.resize();f.setWidth(900);f.resize();assert.equal(f.overlay.open,false);f.dom.window.close();
});

