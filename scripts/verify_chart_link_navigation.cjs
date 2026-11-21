const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
const a=source.indexOf(' function activate(){'),b=source.indexOf(' const signed=',a);assert.ok(a>=0&&b>a);
function run(query,stored='investment',selected=true,hidden=false){
 const items=[{id:'chart-workspace'},{id:'investment'}];
 for(const item of items){item.classList={toggle:(_c,v)=>item.active=v};item.setAttribute=()=>{}}
 const sections=[{id:'chart-workspace'},{id:'investment'}];
 for(const section of sections)section.classList={toggle:(_c,v)=>section.active=v};
 let writes=0;
 const ctx={location:{search:query},URLSearchParams,window:{SectorPulseInvestmentSelected:selected,SectorPulseWorkspace:{sidebar_visibility:{investment:!hidden}}},
 context:{sidebar_visibility:{investment:!hidden}},localStorage:{getItem:()=>stored,setItem:()=>writes++},navButton:items[1],section:sections[1],document:{querySelectorAll:s=>s.includes('.nav')?items:sections}};
 ctx.navButton.addEventListener=()=>{};ctx.navButton.style={};ctx.section.style={};
 vm.runInNewContext(source.slice(a,b),ctx);
 return {investment:!!items[1].active,writes,hidden:!!ctx.navButton.hidden};
}
assert.deepEqual(run('?view=chart-workspace&chartSource=broker'),{investment:false,writes:0,hidden:false});
assert.equal(run('?view=sectors').investment,true); // Preserve legacy routing outside the chart-owned view.
assert.equal(run('?view=unknown').investment,true);
assert.equal(run('?view=investment','sectors',false).investment,true);
assert.equal(run('','investment',false).investment,true);
assert.equal(run('','sectors',false).investment,false);
assert.equal(run('','sectors',true).investment,true);
assert.deepEqual(run('?view=investment','investment',true,true),{investment:false,writes:0,hidden:true});
console.log(JSON.stringify({passed:true,cases:8,explicit_link_does_not_overwrite_saved_preference:true,visibility_gate_preserved:true}));
