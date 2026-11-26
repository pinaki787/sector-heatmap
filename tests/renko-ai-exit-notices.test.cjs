const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('renko-ai-options.js','utf8'),start=source.indexOf(' function renderExitNotices(){'),end=source.indexOf('\n function drawCharts(',start);
function element(){return {dataset:{},style:{},children:[],hidden:false,textContent:'',setAttribute(k,v){this[k]=v},replaceChildren(){this.children=[]},append(n){this.children.push(n)}}}
test('persistent chart exit notice stays scoped, uses text, and clears only with reconciled state',()=>{
 let banner;const charts={querySelector:s=>s==='h2'?{after:n=>{banner=n}}:banner};
 const snapshot={exit_notices:[{account_id:'owner',symbol:'EXACT-CALL',recorded_quantity:20,message:'Exit remains unconfirmed.'},{account_id:'another',symbol:'OTHER',message:'Do not show'}]};
 const c={charts,snapshot,selected:()=>({id:'owner'}),document:{createElement:element}};vm.createContext(c);vm.runInContext(source.slice(start,end),c);
 c.renderExitNotices();assert.equal(banner.role,'alert');assert.equal(banner.hidden,false);assert.equal(banner.children.length,1);assert.match(banner.children[0].textContent,/EXACT-CALL.*20.*unconfirmed/);
 c.renderExitNotices();assert.equal(banner.children.length,1);assert.equal(banner.hidden,false);
 snapshot.exit_notices[0].symbol='<img src=x>';c.renderExitNotices();assert.match(banner.children[0].textContent,/<img src=x>/);assert.equal(banner.children[0].innerHTML,undefined);
 snapshot.exit_notices=[];c.renderExitNotices();assert.equal(banner.hidden,true);assert.equal(banner.children.length,0);
});
