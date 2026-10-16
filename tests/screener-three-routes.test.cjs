const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),vm=require('node:vm')
const source=fs.readFileSync(process.env.SCREENER_UI_SOURCE || 'dashboard-enhancements.js','utf8')
function fixture(plans,budget=10000) {
 const elements=new Map(),calls=[]
 const $=id=>{if(!elements.has(id)) elements.set(id,{value:'',disabled:false,hidden:false,textContent:'',innerHTML:'',dataset:{},querySelectorAll:()=>[],closest:()=>({hidden:false}),replaceChildren(){this.innerHTML=''}});return elements.get(id)}
 $('screener-allocation-budget').value=String(budget)
 const context={$,console,Set,Map,Number,Math,Promise,Error,screenerAnalysisResults:plans,screenerSelectedPlans:new Map(plans.filter(p=>p.selected).map(p=>[p.symbol,p])),screenerOptionChoices:new Map(),screenerClassifications:new Map(),screenerOrderPreview:null,
 fetchJson:async()=>({connected:true,available_funds:100000}),postJson:async(path,payload)=>{calls.push({path,payload});return {classifications:payload.candidates?.map(p=>({symbol:p.symbol,classification:'Equity',options_available:false,routes:{}}))||[],plans:[],preview_id:'preview'+calls.length,confirmation_phrase:'CONFIRM preview'+calls.length,live_submission_enabled:true,submission_eligible:true,aggregate:{cash_reserved:payload.allocation_budget||0,order_count:1}}},
 policyPayload:p=>p,riskPolicyInputs:()=>({maxPositions:10,minimumRewardToRisk:2}),orderAccount:()=>({broker:'fyers',account_id:'chosen-account'}),escapeHtml:String,money:String,invalidateScreenerOrderPreview:message=>{$('screener-order-status').textContent=message},syncScreenerSelectionUi:message=>{$('screener-order-status').textContent=message}}
 const start=source.indexOf('  const screenerRouteLabel ='),end=source.indexOf('  const invalidateScreenerOrderPreview =',start)
 vm.runInNewContext(source.slice(start,end)+'\nthis.api={screenerRouteInfo,syncScreenerRouteControls,analyzeScreenerOptionPlans,allocateScreenerPlansByFunds,prepareScreenerOrder}',context)
 return {...context,context,calls,$}
}
function plan(symbol,score=6){return {symbol,decision:'PASS',entry:100,stop:95,target:110,direction:'BULLISH',conviction:{score,rating:'High'}}}
test('allocation touches selected candidates only and preserves total budget',async()=>{
 const a={...plan('HIGH',7),selected:true},b={...plan('LOW',5),selected:true},unselected=plan('OTHER',6)
 const f=fixture([a,b,unselected]);await f.api.allocateScreenerPlansByFunds()
 assert.equal(unselected.suggested_quantity,undefined);assert.ok(a.suggested_quantity>=b.suggested_quantity)
 assert.ok(a.allocation_budget+b.allocation_budget<=10000.01);assert.equal(f.calls.length,0)
})
test('allocation refuses to use more than the entered amount or available funds',async()=>{
 const f=fixture([{...plan('A'),selected:true}],100001)
 await assert.rejects(f.api.allocateScreenerPlansByFunds(),/available funds/)
 assert.equal(f.calls.length,0)
})
test('naked buy requires verified option proposal and funds whole lots',()=>{
 const p={...plan('A'),execution_route:'LONG_OPTION'},f=fixture([p])
 assert.throws(()=>f.api.screenerRouteInfo(p),/fresh eligible/)
 f.screenerOptionChoices.set('A:LONG_OPTION',{expiry_iso:'2026-10-29',proposal:{lot_size:65,max_loss_per_lot:6500,legs:[{action:'BUY',ask:100}]}})
 const info=f.api.screenerRouteInfo(p);assert.equal(info.unit,6500);assert.equal(info.expiry,'2026-10-29')
})
test('all analyzed stocks receive option checks beyond the first twelve',async()=>{
 const plans=Array.from({length:25},(_,i)=>plan('STOCK'+i)),f=fixture(plans)
 await f.api.analyzeScreenerOptionPlans()
 assert.deepEqual(f.calls.map(c=>c.payload.candidates.length),[12,12,1]);assert.equal(f.screenerClassifications.size,25)
})
test('three selected routes become separate reviewed groups with account and exact expiry',async()=>{
 const eq={...plan('EQ'),selected:true,suggested_quantity:10,allocation_budget:2000}
 const naked={...plan('NAKED'),selected:true,execution_route:'LONG_OPTION',suggested_quantity:1,allocation_budget:4000}
 const spread={...plan('SPREAD'),selected:true,execution_route:'OPTION_SPREAD',suggested_quantity:1,allocation_budget:4000}
 const f=fixture([eq,naked,spread])
 for(const p of [naked,spread])f.screenerOptionChoices.set(`${p.symbol}:${p.execution_route}`,{expiry_iso:'2026-10-29',proposal:{kind:p.execution_route,lot_size:65,max_loss_per_lot:1000,legs:[{action:'BUY',ask:20}]}})
 await f.api.prepareScreenerOrder()
 assert.equal(f.calls.length,3);assert.ok(f.calls.every(c=>c.path.endsWith('/prepare-batch')))
 assert.deepEqual(f.calls.map(c=>c.payload.items[0].proposal.kind),['EQUITY','LONG_OPTION','OPTION_SPREAD'])
 assert.ok(f.calls.every(c=>c.payload.items[0].account_id==='chosen-account'))
 assert.equal(f.calls[1].payload.items[0].expiry,'2026-10-29');assert.equal(f.calls[1].payload.items[0].lots,1)
 assert.equal(f.$('screener-order-review').hidden,false)
})
test('route change removes the old quantity and invalidates preview without losing selection',()=>{
 const p={...plan('A'),selected:true,suggested_quantity:10,allocation_budget:2000},f=fixture([p]);let handler
 const options={EQUITY:{disabled:false},LONG_OPTION:{disabled:true},OPTION_SPREAD:{disabled:true}}
 const picker={querySelector:selector=>options[selector.match(/value="([^"]+)"/)[1]],addEventListener:(event,fn)=>{handler=fn}}
 const card={dataset:{},querySelector:selector=>selector==='.opportunity-head b'?{textContent:'A'}:selector==='.screener-execution-route'?(card.created?picker:null):selector==='.screener-route-status'?{}:null,insertAdjacentHTML(){this.created=true}}
 f.$('screener-analysis-results').querySelectorAll=()=>[card];f.$('screener-analysis-results').append=()=>{}
 f.screenerOptionChoices.set('A:LONG_OPTION',{proposal:{}});f.screenerClassifications.set('A',{classification:'Stock Options',routes:{LONG_OPTION:{eligible:true}}})
 f.api.syncScreenerRouteControls();assert.equal(options.LONG_OPTION.disabled,false)
 handler({target:{value:'LONG_OPTION'}})
 assert.equal(p.execution_route,'LONG_OPTION');assert.equal(p.suggested_quantity,undefined);assert.ok(f.screenerSelectedPlans.has('A'))
 assert.match(f.$('screener-order-status').textContent,/Execution choice changed/)
})
