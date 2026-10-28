
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const {mountChartHistoryNavigation}=require('../renko-supertrend.js');
test('visible scrollbar pans the actual chart without changing zoom or feeding back on refresh',()=>{
 const elements=[];
 function element(){const el={style:{},children:[],handlers:{},clientWidth:400,scrollLeft:0,attrs:{},append(...x){this.children.push(...x)},getBoundingClientRect(){return {left:0,width:400}},focus(){},setPointerCapture(){},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.handlers[k]=v},remove(){}};Object.defineProperty(el,'scrollWidth',{get(){return Math.max(400,parseFloat(el.children[0]?.style.width)||400)}});elements.push(el);return el;}
 const host={id:'chart',ownerDocument:{createElement:element},after(){}};
 let range={from:80,to:120},latest=199,sets=0;const subscribers=[];
 const scale={getVisibleLogicalRange:()=>range,timeToCoordinate:()=>latest,coordinateToLogical:x=>x,subscribeVisibleLogicalRangeChange:fn=>subscribers.push(fn),unsubscribeVisibleLogicalRangeChange(){},setVisibleLogicalRange:r=>{range=r;sets++;subscribers.forEach(fn=>fn())}};
 const ctx={chart:{timeScale:()=>scale},host,latestTime:()=>1,requestAnimationFrame:fn=>fn(),ResizeObserver:class{observe(){}disconnect(){}}};
 vm.createContext(ctx);const nav=vm.runInContext('('+mountChartHistoryNavigation.toString()+')({chart,host,latestTime})',ctx),rail=nav.element;
 assert.equal(rail.attrs.role,'scrollbar');assert.equal(rail.scrollLeft,800);
 rail.scrollLeft=500;rail.handlers.scroll();assert.equal(range.from,50);assert.equal(range.to,90);
 const previousSets=sets;latest=200;nav.sync();rail.handlers.scroll();assert.equal(sets,previousSets);assert.equal(range.from,50);
 range={from:180,to:220};nav.sync();assert.equal(rail.scrollLeft,1800);rail.handlers.scroll();assert.equal(sets,previousSets);
 let prevented=false;elements.find(e=>e.className==='renko-history-track').handlers.wheel({deltaY:-100,deltaX:0,preventDefault(){prevented=true}});rail.handlers.scroll();assert.equal(prevented,true);assert.equal(range.from,170);assert.equal(range.to,210);
 rail.handlers.keydown({key:'ArrowLeft',preventDefault(){}});rail.handlers.scroll();assert.equal(range.from,166);assert.equal(range.to,206);
 const track=elements.find(e=>e.className==='renko-history-track'),thumb=elements.find(e=>e.className==='renko-history-thumb');
 assert.ok(parseFloat(thumb.style.width)>24);assert.ok(parseFloat(thumb.style.width)<400);
 const priorHorizontal=range.from;track.handlers.wheel({deltaX:-60,deltaY:0,preventDefault(){}});rail.handlers.scroll();assert.ok(range.from<priorHorizontal);
 const before=range.from;track.handlers.pointerdown({button:0,target:thumb,clientX:200,pointerId:1,preventDefault(){}});track.handlers.pointermove({clientX:160});rail.handlers.scroll();track.handlers.pointerup();
 assert.ok(range.from<before);assert.equal(range.to-range.from,40);
});
