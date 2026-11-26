const test=require('node:test'),assert=require('node:assert/strict');
const {BandState}=require('../renko-ai-bands.js');
const {configuration}=require('../renko-ai-options.js');
test('SMA cloud uses real High/Low and a complete configurable window',()=>{
 const s=new BandState('SMA',3);
 assert.equal(s.push({time:1,open:100,high:110,low:90,close:100}),null);
 s.push({time:2,open:100,high:120,low:80,close:100});
 const v=s.push({time:3,open:100,high:130,low:70,close:100});
 assert.equal(v.upper,120);assert.equal(v.lower,80);
 const next=s.push({time:4,open:100,high:140,low:60,close:100});
 assert.equal(next.upper,130);assert.equal(next.lower,70);
});
test('EMA cloud seeds with SMA and then uses exponential weighting',()=>{
 const s=new BandState('EMA',3);
 for(let time=1;time<=3;time++)s.push({time,high:110,low:90,close:100});
 const v=s.push({time:4,high:150,low:50,close:100});assert.equal(v.upper,130);assert.equal(v.lower,70);
 assert.throws(()=>s.push({time:4,high:150,low:50,close:100}),/Invalid/);
});
test('Bands default to period30 and off, with independent explicit settings',()=>{
 const f={underlying:'NSE:NIFTY50-INDEX',lots:'1',product:'MARGIN',timeframe:'5 minutes',execution:'PAPER'};
 const c=configuration(f,{id:'owner',broker:'FYERS'});
 for(const k of ['sma','ema']){assert.equal(c['ai_'+k+'_band_period'],30);assert.equal(c['ai_'+k+'_band_entry'],false);assert.equal(c['ai_'+k+'_band_exit'],false);}
 const enabled=configuration({...f,smaPeriod:'10',smaEntry:true,emaPeriod:'20',emaExit:true},{id:'owner',broker:'FYERS'});
 assert.equal(enabled.ai_sma_band_period,10);assert.equal(enabled.ai_sma_band_entry,true);assert.equal(enabled.ai_ema_band_period,20);assert.equal(enabled.ai_ema_band_exit,true);
 assert.throws(()=>configuration({...f,smaPeriod:'2.5'},{id:'owner',broker:'FYERS'}),/whole number/);
});
test('SMA cloud colors use completed closes with neutral boundaries; EMA stays unchanged',()=>{
 const {cloudColor}=require('../renko-ai-bands.js');
 const state=new BandState('SMA',2);
 state.push({time:1,high:110,low:90,close:100});
 const bullish=state.push({time:2,high:130,low:110,close:125});
 assert.equal(bullish.close,125);assert.equal(cloudColor('SMA',bullish),'#22c55e');
 assert.equal(cloudColor('SMA',{upper:120,lower:100,close:95}),'#ef4444');
 for(const close of [100,110,120])assert.equal(cloudColor('SMA',{upper:120,lower:100,close}),'#94a3b8');
 assert.equal(cloudColor('SMA',{upper:120,lower:100}),'#94a3b8');
 assert.equal(cloudColor('EMA',bullish),'#a78bfa');
});
test('late historical SMA seed merges after latest heartbeat without dropping history or duplicating timestamps',()=>{
 const {mergeBandPoint}=require('../renko-ai-bands.js'),points=[];
 mergeBandPoint(points,{timestamp:30,upper:3});
 for(const timestamp of [10,20,30])mergeBandPoint(points,{timestamp,upper:timestamp});
 assert.deepEqual(points.map(p=>p.timestamp),[10,20,30]);
 mergeBandPoint(points,{timestamp:30,upper:99});mergeBandPoint(points,{timestamp:40,upper:4});
 assert.equal(points[2].upper,99);assert.deepEqual(points.map(p=>p.timestamp),[10,20,30,40]);
});
test('active-run band ownership applies only to Renko; real candle views retain completed broker history',()=>{
 const fs=require('node:fs'),source=fs.readFileSync(require('node:path').join(__dirname,'../chart-workspace.js'),'utf8');
 assert.ok(source.includes("bandContext&&settings.type==='Renko'&&aiBandBasis==='UNDERLYING'?"));
 assert.ok(source.includes("sourceContext&&settings.type==='Renko'&&aiBandBasis==='UNDERLYING'?"));
 assert.ok(source.includes("completed:row=>!row.provisional&&candleEnd(row.time,settings.interval)<=Date.now()/1000"));
});
