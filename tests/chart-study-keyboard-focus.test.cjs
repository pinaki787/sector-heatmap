const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const start=source.indexOf('  function beginStudyTabNavigation('),end=source.indexOf('  function drawLegend() {',start);assert.ok(start>=0&&end>start);
const guard=source.slice(end,source.indexOf('\n',source.indexOf('    if (',end))+1);
function fixture(){
 const dom=new JSDOM('<div id="panel"><div class="sp-chart-legend"><input id="length"><input id="offset"><button id="close">Close</button></div><button id="outside">Outside</button></div>',{runScripts:'outside-only'});
 const w=dom.window,panel=w.document.querySelector('#panel'),legend=panel.querySelector('.sp-chart-legend');panel.open=true;
 w.panel=panel;w.legendTabInteraction=false;w.legendPointerInteraction=false;w.redraws=0;
 w.replaceLegend=()=>{w.redraws++;legend.replaceChildren(...[...legend.children].map(e=>e.cloneNode(true)));};
 w.eval(source.slice(start,end)+guard+' replaceLegend(); }');
 panel.addEventListener('keydown',w.beginStudyTabNavigation,true);w.addEventListener('keyup',w.finishStudyTabNavigation);
 return {dom,w,panel,legend,field:id=>w.document.getElementById(id),key:(target,type,shiftKey=false)=>target.dispatchEvent(new w.KeyboardEvent(type,{key:'Tab',shiftKey,bubbles:true,cancelable:true}))};
}
for(const reverse of [false,true])test((reverse?'Shift+Tab':'Tab')+' preserves the native destination through synchronous change redraw',()=>{
 const f=fixture(),from=f.field(reverse?'offset':'length'),to=f.field(reverse?'length':'offset');
 from.addEventListener('blur',()=>f.w.drawLegend());from.focus();f.key(from,'keydown',reverse);from.blur();to.focus();f.key(to,'keyup',reverse);
 assert.equal(f.w.document.activeElement,to);assert.equal(to.isConnected,true);assert.equal(f.w.redraws,0);assert.equal(f.w.legendTabInteraction,false);f.dom.window.close();
});
test('Tab to an action button keeps its native focus',()=>{
 const f=fixture(),from=f.field('offset'),to=f.field('close');from.addEventListener('blur',()=>f.w.drawLegend());from.focus();
 f.key(from,'keydown');from.blur();to.focus();f.key(to,'keyup');assert.equal(f.w.document.activeElement,to);assert.equal(f.w.redraws,0);f.dom.window.close();
});
test('leaving the legend releases deferred redraws',()=>{
 const f=fixture(),from=f.field('offset'),to=f.field('outside');from.addEventListener('blur',()=>f.w.drawLegend());from.focus();
 f.key(from,'keydown');from.blur();to.focus();f.key(to,'keyup');assert.equal(f.w.redraws,1);assert.equal(f.w.document.activeElement,to);f.dom.window.close();
});
test('cancelled, composing and unrelated navigation do not arm the guard',()=>{
 const f=fixture(),field=f.field('length');
 for(const patch of [{key:'Enter'},{key:'Tab',isComposing:true},{key:'Tab',defaultPrevented:true}]){
  f.w.beginStudyTabNavigation({key:'Tab',defaultPrevented:false,isComposing:false,target:field,...patch});assert.equal(f.w.legendTabInteraction,false);
 }
 f.w.beginStudyTabNavigation({key:'Tab',target:f.field('outside')});assert.equal(f.w.legendTabInteraction,false);f.dom.window.close();
});
