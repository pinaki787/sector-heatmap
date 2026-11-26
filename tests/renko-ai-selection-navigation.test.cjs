const test=require('node:test'),assert=require('node:assert/strict');
const {selectionFrameUrl,selectionIntentMatches}=require('../renko-ai-options.js');
const base='https://example.test/?chartSource=account&chartInstance=ai-draft-0&interval=5';
test('new frame navigation restarts sequence but unchanged sizing/status keeps the frame URL',()=>{
 const frame={dataset:{}},first=selectionFrameUrl(frame,base,()=> 'nav-first');
 frame.dataset.selectionSequence='25';
 assert.equal(selectionFrameUrl(frame,base,()=> 'must-not-run'),first);
 assert.equal(frame.dataset.selectionSequence,'25');
 const second=selectionFrameUrl(frame,base.replace('interval=5','interval=1'),()=> 'nav-second');
 assert.equal(frame.dataset.selectionSequence,'0');
 assert.equal(selectionIntentMatches(second,{account:'account',instance:'ai-draft-0',navigation:'nav-second',document:'doc-new',sequence:1},'account',0,'doc-new'),true);
 assert.equal(selectionIntentMatches(second,{account:'account',instance:'ai-draft-0',navigation:'nav-first',document:'doc-old',sequence:26},'account',0,'doc-new'),false);
});
test('wrong account, instance, missing navigation and replayed sequence cannot change the form',()=>{
 const frame={dataset:{}},src=selectionFrameUrl(frame,base,()=> 'current');
 const message={account:'account',instance:'ai-draft-0',navigation:'current',document:'doc-current',sequence:2};
 assert.equal(selectionIntentMatches(src,message,'account',1,'doc-current'),true);
 for(const change of [{account:'other'},{instance:'other'},{navigation:null},{navigation:'stale'},{document:'old-document'},{sequence:1},{sequence:1.5}])assert.equal(selectionIntentMatches(src,{...message,...change},'account',1,'doc-current'),false);
});

test('same-URL reload accepts the new document counter and rejects old document messages',()=>{
 const frame={dataset:{}},src=selectionFrameUrl(frame,base,()=> 'same-nav');
 assert.equal(selectionIntentMatches(src,{account:'account',instance:'ai-draft-0',navigation:'same-nav',document:'new-doc',sequence:1},'account',0,'new-doc'),true);
 assert.equal(selectionIntentMatches(src,{account:'account',instance:'ai-draft-0',navigation:'same-nav',document:'old-doc',sequence:100},'account',0,'new-doc'),false);
});
