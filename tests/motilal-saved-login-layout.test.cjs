const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');const {JSDOM}=require('/private/tmp/renko-browser-check/node_modules/jsdom');
test('saved credentials are masked and status is a table without credential values',async()=>{
 const dom=new JSDOM(fs.readFileSync('motilal-oswal.html','utf8'),{url:'https://example.test/broker-workspace/'+'a'.repeat(32)+'/',runScripts:'outside-only'}),w=dom.window;
 w.fetch=async path=>({ok:true,json:async()=>path.endsWith('workspace-context')?{csrf:'test',visible:true,permitted:true,workspace:{id:'a'.repeat(32),label:'MO',account_ref:'TEST'}}:path.endsWith('saved-login')?{configured:true,client_id:'TEST',otp_required:false}:{authenticated:true,client_id:'TEST',live_enabled:true,exchanges:['NSE','MCX'],products:['NORMAL'],session_expires_at:1900000000}});
 w.eval(fs.readFileSync('motilal-oswal.js','utf8'));await new Promise(r=>setTimeout(r,10));
 for(const id of ['saved-password','saved-pan']){const input=w.document.getElementById(id);assert.equal(input.value,'');assert.equal(input.disabled,true);assert.match(input.placeholder,/Saved/);}
 assert.equal(w.document.getElementById('save-login').hidden,true);assert.equal(w.document.querySelectorAll('#connection tr').length,7);assert.match(w.document.getElementById('connection').textContent,/AuthenticationConnected/);assert.doesNotMatch(w.document.getElementById('connection').textContent,/[{}]/);
 w.document.getElementById('edit-login').click();assert.equal(w.document.getElementById('saved-pan').disabled,false);assert.equal(w.document.getElementById('save-login').hidden,false);dom.window.close();
});
