const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('investment.js','utf8');
function mount(context={admin:true,allowed_features:['investment'],sidebar_visibility:{}}){
 const dom=new JSDOM('<!doctype html><nav class="nav"></nav><main class="work"><section id="sectors" class="view active"></section></main>',{url:'https://example.test',runScripts:'outside-only'});
 dom.window.SectorPulseWorkspace=context;dom.window.eval(source);dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));return dom;
}
test('mount and isolated navigation',()=>{
 const dom=mount(),w=dom.window;assert.ok(w.document.querySelector('#investment'));w.document.querySelector('[data-view=investment]').click();assert.ok(w.document.querySelector('#investment.active'));dom.window.close();
});
test('unassigned user has no investment view',()=>{const d=mount({admin:false,allowed_features:['screener']});assert.equal(d.window.document.querySelector('#investment'),null);d.window.close();});
test('hidden setting is preserved',()=>{const d=mount({admin:true,allowed_features:['investment'],sidebar_visibility:{investment:false}});assert.equal(d.window.document.querySelector('[data-view=investment]').hidden,true);d.window.close();});
test('restores rule output, escapes company text and limits displayed decimals',()=>{
 const d=mount(),w=d.window;w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{base:'https://example.test/api/jobs',job:{feature:'investment',job_id:'123456789',created:1,terminal:true,status:'COMPLETED',output:{schema:'investment/v1',policy:{distance_pct:5},coverage:{eligible:1,displayed:1},rows:[{symbol:'NSE:TEST-EQ',name:'<img src=x onerror=alert(1)>',price:123.456789,distance_pct:1.234567,rule_status:'QUALITY_REVIEW',metrics:{}}]}}}}));
 assert.match(w.document.querySelector('#investment-rows').textContent,/123.46/);assert.equal(w.document.querySelector('#investment-rows img'),null);assert.doesNotMatch(w.document.querySelector('#investment-rows').textContent,/123.456/);d.window.close();
});


test('sector RS and conditional levels render with two decimals',()=>{
 const d=mount(),w=d.window;
 const row={symbol:'NSE:TECHM-EQ',name:'Tech Mahindra',sector:'Technology Services',price:1790,reported_ath:1854,metrics:{},rule_status:'QUALITY_REVIEW',sector_strength:{status:'MIXED',windows:{'6m':{excess_pp:1.48669},'12m':{excess_pp:-6.08357}}},relative_strength:{windows:{'12m':32.52813}},plan:{status:'CONDITIONAL',entry:1854.1,stoploss:1746.2,target:2069.9,reward_risk:2}};
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{base:'https://example.test/api/jobs',job:{feature:'investment',job_id:'abcdef1234',created:2,terminal:true,status:'COMPLETED',output:{schema:'investment/v1',policy:{distance_pct:5},coverage:{eligible:1,displayed:1},rows:[row]}}}}));
 const text=w.document.querySelector('#investment-rows').textContent;
 assert.match(text,/Technology Services/);assert.match(text,/6M \+1\.49 pp/);assert.match(text,/12M -6\.08 pp/);
 assert.match(text,/Entry ₹1,854\.1/);assert.match(text,/Stop-loss ₹1,746\.2/);assert.match(text,/Target ₹2,069\.9/);
 assert.match(w.document.querySelector('.investment-table thead').textContent,/AI Assessment/);
 assert.equal(w.document.querySelectorAll('.investment-table th').length,8);
 d.window.close();
});

