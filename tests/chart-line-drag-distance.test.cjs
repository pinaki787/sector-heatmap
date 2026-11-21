const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
const match=source.match(/    const lineDragged = \(start, end\) => \{[\s\S]*?^    };/m);assert.ok(match);
const dragged=vm.runInNewContext(match[0]+';lineDragged',{Math,Number});
const p=(x,y,cx,cy)=>({point:{x,y},sourceEvent:{clientX:cx,clientY:cy}});
test('stationary pointer remains a click through observed 7.34px pane shift',()=>assert.equal(dragged(p(408,326.46,450,500),p(408,333.79,450,500)),false));
test('physical drag is recognized even if pane moves by same amount',()=>assert.equal(dragged(p(100,100,150,200),p(100,100,170,220)),true));
test('threshold distinguishes click jitter from drag',()=>{assert.equal(dragged(p(0,0,100,100),p(20,20,103,102)),false);assert.equal(dragged(p(0,0,100,100),p(0,0,103,104)),true)});
test('coordinate fallback remains available for nonpointer callers',()=>{assert.equal(dragged({point:{x:0,y:0}},{point:{x:3,y:4}}),true);assert.equal(dragged({point:{x:0,y:0}},{point:{x:1,y:1}}),false)});
