const {test}=require('node:test'),assert=require('node:assert/strict');
const {mountChartDrawings}=require('../renko-supertrend.js');
test('drawing anchors, persistence, undo and instrument isolation',()=>{
 const nodes=[];class Element{constructor(tag){this.tag=tag;this.children=[];this.events={};this.style={};nodes.push(this);}setAttribute(k,v){this[k]=v;}append(...children){this.children.push(...children);}before(e){this.previous=e;}addEventListener(k,fn){this.events[k]=fn;}}
 global.document={createElement:t=>new Element(t),head:new Element('head')};
 let click,scope='BTCUSD',view='synthetic',series=[],levels=[],lineLevels=[];const saved=new Map();const storage={getItem:k=>saved.get(k)??null,setItem:(k,v)=>saved.set(k,v)};
 const chart={applyOptions:()=>{},subscribeClick:fn=>click=fn,addLineSeries:()=>{const s={setData:p=>s.points=p};series.push(s);return s;},removeSeries:s=>series=series.filter(x=>x!==s),timeScale:()=>({coordinateToTime:x=>x})};
 const candles={coordinateToPrice:y=>y,priceToCoordinate:y=>y,createPriceLine:o=>{o.applyOptions=v=>Object.assign(o,v);levels.push(o);return o;},removePriceLine:o=>levels=levels.filter(x=>x!==o)};
 const closeLine={...candles,
  createPriceLine:options=>{lineLevels.push(options);return options;},
  removePriceLine:handle=>{lineLevels=lineLevels.filter(line=>line!==handle);}
 };
 const host=new Element('host');host.getBoundingClientRect=()=>({top:0,left:0,width:800});
 const tools=mountChartDrawings({chart,candles,priceSeries:()=>view==='line'?closeLine:candles,host,scope:()=>scope,chartView:()=>view,formatPrice:String,storage});
 const mode=nodes.find(n=>n.tag==='select'),undo=nodes.find(n=>n.textContent==='Undo drawing');
 mode.value='horizontal';mode.events.change();click({point:{x:10,y:100},time:10});assert.equal(levels[0].price,100);assert.equal(mode.value,'cursor');
 mode.value='trend';mode.events.change();click({point:{x:20,y:120},time:20});assert.equal(series.length,0);click({point:{x:10,y:110},time:10});assert.deepEqual(series[0].points,[{time:10,value:110},{time:20,value:120}]);
 undo.events.click();assert.equal(series.length,0);assert.equal(levels.length,1);
 const event={button:0,pointerId:1,clientX:100,clientY:100,preventDefault(){},stopImmediatePropagation(){}};host.events.pointerdown(event);host.events.pointermove({...event,clientY:150});host.events.pointerup({...event,clientY:150});assert.equal(levels[0].price,150);
 view='line';tools.sync();assert.equal(levels.length,0);assert.equal(lineLevels[0].price,150);
 view='synthetic';tools.sync();assert.equal(lineLevels.length,0);assert.equal(levels[0].price,150);
 scope='ETHUSD';tools.sync();assert.equal(levels.length,0);scope='BTCUSD';tools.sync();assert.equal(levels[0].price,150);
});
