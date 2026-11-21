const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const f='.private/chart-order-rollouts/renko-traditional-activation-20261120/';
const files=JSON.parse(fs.readFileSync(f+'files.json','utf8')),source=fs.readFileSync(f+'root/chart-workspace.js','utf8');
function choices(type,method){
 const c={settings:{type,brickMethod:method,customIntervals:['17','100T']},requestedHourIntervals:['360','840','1320','1380'],tradeInterval:x=>/[ST]$/.test(x),sourceInterval:()=>true,projectionIntervalSeconds:x=>parseInt(x)*(/D$/.test(x)?86400:/W$/.test(x)?604800:/M$/.test(x)?2592000:60)};
 vm.createContext(c);const a=source.indexOf('  function studyCalculationChoices('),b=source.indexOf('  function studyCalculationBars(',a);vm.runInContext(source.slice(a,b),c);return c;
}
test('Traditional Renko exposes supported higher and custom calculation intervals',()=>{
 const c=choices('Renko','fixed'),actual=[...c.studyCalculationChoices('1')];
 for(const value of ['5','15','60','360','840','1320','1380','1D','1W','1M','12M','17'])assert.ok(actual.includes(value),value);
 assert.ok(!actual.includes('100T'));assert.deepEqual([...c.studyCalculationChoices('100T')],[]);
});
test('unresolved ATR and percentage sizing cannot enter the new Renko timeframe path',()=>{
 for(const method of ['atr','percent'])assert.deepEqual([...choices('Renko',method).studyCalculationChoices('1')],[]);
});
test('standard chart timeframe choices remain available',()=>{
 for(const type of ['Candles','Line','Heikin Ashi'])assert.ok(choices(type,'atr').studyCalculationChoices('30').includes('60'));
});
test('all seven browser library bundles load the full Renko engine without a new backend asset route',()=>{
 const bundles=files.filter(r=>r.target.endsWith('chart-workspace-studies.js'));assert.equal(bundles.length,7);
 for(const r of bundles){
  const context={window:{}};vm.createContext(context);vm.runInContext(fs.readFileSync(r.staged,'utf8'),context);
  assert.equal(typeof context.window.SectorPulseChartStudies.renko,'function');
  for(const name of ['calculateRenkoTimeframeStudy','renkoStudyPublication','applyRenkoStudyPublication'])assert.equal(typeof context.window.SectorPulseRenkoStudyAlignment[name],'function');
 }
});
test('all21 pages retain library-before-workspace loading and carry the activation version',()=>{
 const pages=files.filter(r=>r.target.endsWith('.html'));assert.equal(pages.length,21);
 for(const r of pages){const html=fs.readFileSync(r.staged,'utf8');
  const library=html.match(/<script[^>]*src="\/?chart-workspace-studies\.js[^"]*"/);
  const workspace=html.match(/<script[^>]*src="\/?chart-workspace\.js[^"]*"/);
  assert.ok(library&&workspace&&library.index<workspace.index,r.target);
  assert.equal((html.match(/renko-study-tf=20261120-1/g)??[]).length,2);
 }
});

