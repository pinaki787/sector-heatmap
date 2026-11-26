const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('renko-ai-options.js','utf8');
function element(){return {style:{},children:[],hidden:false,attrs:{},setAttribute(k,v){this.attrs[k]=v},replaceChildren(){this.children=[]},append(e){this.children.push(e)},after(e){this.afterElement=e},addEventListener(){},querySelector(){return this.children[0]}}}
test('typing exposes exact catalog suggestions but does not select or dispatch until a click',()=>{
 const input=element(),pick={options:[{value:'NSE_EQ:9436'}],value:'',events:[],dispatchEvent(e){this.events.push(e.type)}},context={document:{getElementById:id=>id==='renko-search'?input:pick,createElement:element},mode:{value:'AI'},MODE:'AI',Event:class{constructor(type){this.type=type}}};
 vm.createContext(context);const a=source.indexOf(' let suggestionBox;'),b=source.indexOf(' let aiSearchTimer',a);vm.runInContext(source.slice(a,b),context);
 context.renderSearchSuggestions([{symbol:'NSE_EQ:9436',underlying:'AXISCADES',suggested:true}],'AXICADES');
 assert.equal(pick.value,'');assert.equal(pick.events.length,0);assert.equal(input.afterElement.hidden,false);
 const option=input.afterElement.children[0];assert.match(option.textContent,/AXISCADES.*NSE_EQ:9436.*Close spelling/);option.onclick();
 assert.equal(pick.value,'NSE_EQ:9436');assert.deepEqual(pick.events,['change']);assert.equal(input.afterElement.hidden,true);
});
test('late search response cannot overwrite another account, route, market or query',async()=>{
 for(const change of ['account','route','market','query']){
  let account='one',route='DIRECT',resolve,rendered=0;const market={value:'NSE_EQUITY'},input={value:'AXI'};
  const c={aiSearchSequence:0,MODE:'AI',mode:{value:'AI'},selected:()=>({id:account}),values:()=>({route}),document:{getElementById:id=>id==='renko-market'?market:input},status:{},request:()=>new Promise(r=>resolve=r),URLSearchParams,renderSearchSuggestions:()=>rendered++,show(){}};
  vm.createContext(c);const a=source.indexOf(' async function searchAiInstruments(){'),b=source.indexOf("\n document.addEventListener('input'",a);vm.runInContext(source.slice(a,b),c);
  const pending=c.searchAiInstruments();if(change==='account')account='two';if(change==='route')route='OPTIONS';if(change==='market')market.value='BSE_EQUITY';if(change==='query')input.value='OTHER';resolve({matches:[{symbol:'NSE_EQ:9436'}]});await pending;assert.equal(rendered,0);
 }
});

test('a failed superseded search cannot replace the current search status',async()=>{
 let reject;const input={value:'AXI'},market={value:'NSE_EQUITY'},c={aiSearchSequence:0,MODE:'AI',mode:{value:'AI'},selected:()=>({id:'one'}),values:()=>({route:'DIRECT'}),document:{getElementById:id=>id==='renko-market'?market:input},status:{},request:()=>new Promise((_,r)=>reject=r),URLSearchParams};
 vm.createContext(c);const a=source.indexOf(' async function searchAiInstruments(){'),b=source.indexOf("\n document.addEventListener('input'",a);vm.runInContext(source.slice(a,b),c);
 const pending=c.searchAiInstruments();input.value='AXISCADES';c.status.textContent='New search result';reject(Error('Old connection error'));await pending;assert.equal(c.status.textContent,'New search result');
});
