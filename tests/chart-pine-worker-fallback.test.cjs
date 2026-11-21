const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function pineUsesWorkerFeatures('),end=s.indexOf('  function pineApplyTarget(',start);assert.ok(start>=0&&end>start);const eligible=vm.runInNewContext(s.slice(start,end)+';pineUsesWorkerFeatures');
for(const [name,body] of [['arrays','var array<float> a=array.new<float>()'],['UDT','type State\n    float value'],['function','f(x) => x*2\nplot(f(close))'],['loop','for i=0 to 3\n    a=i'],['syntax error','plot(close'],['runtime error','runtime.error("test")']])
test(name+' may reach full Pine worker',()=>assert.equal(eligible('//@version=6\nindicator("Test")\n'+body),true));
test('Version5 indicator may reach worker',()=>assert.equal(eligible('//@version=5\nindicator("Test")\nplot(close)'),true));
test('Unsupported or undeclared sources are not admitted',()=>{for(const source of ['indicator("Test")','//@version=4\nindicator("Test")','//@version=6\nstrategy("Test")','console.log("indicator(")'])assert.equal(eligible(source),false);});
