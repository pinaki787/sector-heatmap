const {test}=require('node:test'),assert=require('node:assert/strict'),{JSDOM}=require('jsdom'),fs=require('node:fs');
const source=fs.readFileSync(require.resolve('../dashboard-enhancements.js'),'utf8');
const start=source.lastIndexOf(';(() => {');
test('global hiding applies to administrators and unregistered features stay hidden',()=>{
 const dom=new JSDOM('<div class="desk"><nav class="nav"><button data-feature="runner-jobs">Jobs</button><a data-feature="user-guide">Help</a><button data-view="unregistered">New</button></nav><main class="work"><div class="view active" id="user-guide"></div></main></div>',{runScripts:'outside-only'});
 dom.window.SectorPulseWorkspace={admin:true,allowed_features:['runner-jobs','user-guide'],sidebar_visibility:{'runner-jobs':false}};
 dom.window.eval(source.slice(start));dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
 assert.equal(dom.window.document.querySelector('[data-feature="runner-jobs"]').hidden,true);
 assert.equal(dom.window.document.querySelector('[data-feature="user-guide"]').hidden,false);
 assert.equal(dom.window.document.querySelector('[data-view="unregistered"]').hidden,true);
 dom.window.close();
});
test('user assignments hide unassigned new features',()=>{
 const dom=new JSDOM('<div class="desk"><nav class="nav"><button data-feature="runner-jobs">Jobs</button><a data-feature="user-guide">Help</a></nav><main class="work"><div class="view active" id="user-guide"></div></main></div>',{runScripts:'outside-only'});
 dom.window.SectorPulseWorkspace={admin:false,allowed_features:['user-guide'],sidebar_visibility:{}};
 dom.window.eval(source.slice(start));dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
 assert.equal(dom.window.document.querySelector('[data-feature="runner-jobs"]').hidden,true);
 assert.equal(dom.window.document.querySelector('[data-feature="user-guide"]').hidden,false);dom.window.close();
});
