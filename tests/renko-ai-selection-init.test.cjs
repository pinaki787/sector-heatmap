const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
const begin=source.indexOf('  function requestAiSelection('),end=source.indexOf('\n  const sharedChartParameters',begin);
const fn=source.slice(begin,end);
function fixture(panel,instance='ai-draft-1'){
 const sent=[],note={textContent:''},parent={postMessage:m=>sent.push(m)};
 const context=vm.createContext({panel,aiSelectionParams:new URLSearchParams({chartContext:'renko',aiRenko:'1',chartInstance:instance,chartSource:'account',aiNavigation:'navigation'}),aiSelectionDocument:'doc',aiSelectionSequence:0,window:{parent},location:{origin:'https://example.test'}});
 vm.runInContext(fn,context);return {context,sent,note,call:change=>context.requestAiSelection(change)};
}
test('Initial Call/Put symbol hydration is not a user edit before the panel exists',()=>{
 for(const panel of [undefined,{open:false}]){
  const f=fixture(panel);
  assert.equal(f.call({symbol:'NSE:CALL'}),false);assert.equal(f.sent.length,0);
 }
});
test('Ready option charts retain their exact contract without forwarding a symbol edit',()=>{
 const note={textContent:''},f=fixture({open:true,querySelector:()=>note});
 assert.equal(f.call({symbol:'NSE:OTHER'}),true);assert.equal(f.sent.length,0);assert.match(note.textContent,/retain the selected contract/);
});
test('Ready underlying chart still forwards an explicit user selection',()=>{
 const f=fixture({open:true},'ai-draft-0');
 assert.equal(f.call({symbol:'NSE:RELIANCE-EQ'}),true);assert.equal(f.sent.length,1);
 assert.equal(f.sent[0].change.symbol,'NSE:RELIANCE-EQ');assert.equal(f.sent[0].account,'account');
});
