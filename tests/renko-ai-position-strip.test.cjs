const test=require('node:test'),assert=require('node:assert/strict');
const {view,lineOptions,mount}=require('../renko-ai-position-strip.js');
test('cash/point readout stays separate from price-line text without changing price or precision',()=>{
 const current={price:3660.123456,title:'USD -0.58 gross',color:'#ef5350',axisLabelVisible:true,lineWidth:1};
 assert.deepEqual(view(current),{label:'Gross P&L',value:'USD -0.58',color:'#ef5350'});
 assert.equal(lineOptions(current).title,'');assert.equal(lineOptions(current).price,3660.123456);
 assert.equal(current.title,'USD -0.58 gross');
 assert.equal(view({...current,title:'+2.13 pts'}).label,'Position move');
 assert.equal(view(null),null);assert.equal(lineOptions(null),null);
});
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.style={};this.hidden=false;}
 setAttribute(k,v){this.attrs[k]=v;} append(...els){this.children.push(...els);}
 addEventListener(name,fn){this[name]=fn;} remove(){this.removed=true;}
}
test('strip is outside plot, reuses DOM, persists scoped visibility, and clears on close',()=>{
 const nodes=[],doc={createElement:t=>{const e=new Element(t);nodes.push(e);return e;}},stage={ownerDocument:doc,before:e=>stage.previous=e};
 const values=new Map(),store={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};
 const ui=mount(stage,{key:'account:PAXGUSD',store});
 assert.equal(stage.previous,ui.element);assert.equal(ui.element.hidden,true);
 ui.update({title:'USD +1.20 gross',color:'green'});
 const [label,value,toggle]=ui.element.children;
 assert.equal(value.textContent,'USD +1.20');assert.equal(ui.element.hidden,false);
 const count=nodes.length;toggle.click();assert.equal(value.hidden,true);assert.equal(values.get('account:PAXGUSD'),'hidden');
 ui.update({title:'USD -0.20 gross',color:'red'});assert.equal(value.hidden,true);assert.equal(nodes.length,count);
 toggle.click();assert.equal(value.hidden,false);assert.equal(value.textContent,'USD -0.20');
 ui.update(null);assert.equal(ui.element.hidden,true);ui.destroy();assert.equal(ui.element.removed,true);
 const next=mount(stage,{key:'another-account:PAXGUSD',store});next.update({title:'+1.00 pts'});assert.equal(next.element.children[1].hidden,false);
});
