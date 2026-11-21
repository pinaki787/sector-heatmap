const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
global.addEventListener=()=>{};
const {renkoSwitchUrl,brokerSwitchUrl}=require('../broker-form-routing.js');
const {embeddedRenkoChartUrl}=require('../renko-supertrend.js');
test('Renko broker selection removes stale standalone chart route and source',()=>{
 const u=new URL(renkoSwitchUrl('https://example.test/?view=chart-workspace&chartSource=fyers&symbol=NSE:NIFTY50-INDEX&renkoInstance=old',{id:'delta',broker:'DELTA_INDIA'}));
 assert.equal(u.searchParams.get('view'),'renko-supertrend');assert.equal(u.searchParams.has('chartSource'),false);assert.equal(u.searchParams.has('symbol'),false);
 assert.equal(u.searchParams.get('renkoAccount'),'delta');
});
test('other forms preserve their selected view',()=>assert.equal(new URL(brokerSwitchUrl('https://example.test/?view=ema-band',{id:'fyers',broker:'FYERS'},'band')).searchParams.get('view'),'ema-band'));
test('embedded new chart binds exact account symbol interval in separate context',()=>{
 const u=new URL(embeddedRenkoChartUrl('https://example.test/?view=chart-workspace&chartSource=old&symbol=NSE:NIFTY50-INDEX',{accountId:'delta',broker:'DELTA_INDIA',symbol:'BTCUSD',instance:'btc-runner',timeframe:'30 minutes',brick:12.345}));
 assert.equal(u.searchParams.get('chartSource'),'delta');assert.equal(u.searchParams.get('symbol'),'BTCUSD');assert.equal(u.searchParams.get('interval'),'30');assert.equal(u.searchParams.get('chartContext'),'renko');assert.equal(u.searchParams.get('chartInstance'),'btc-runner');assert.equal(u.searchParams.get('brick'),'12.345');
});
test('missing account fails rather than falling back to FYERS',()=>assert.throws(()=>embeddedRenkoChartUrl('https://example.test/',{symbol:'BTCUSD'}),/explicit account/));
test('chart engine has isolated settings and last-source keys',()=>{
 const source=fs.readFileSync('chart-workspace.js','utf8');
 assert.match(source,/linkedChart\?\.chartContext === 'renko'/);assert.match(source,/selectionKey = .*embeddedScope/);
});
