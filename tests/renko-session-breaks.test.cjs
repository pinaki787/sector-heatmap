const test=require('node:test'),assert=require('node:assert/strict');
const {chartSessionBreaks}=require('../renko-supertrend.js');
const ts=(d,t)=>Date.parse(d+'T'+t+':00+05:30')/1000;
test('NSE boundaries follow verified 09:15 session and preserve fractional Renko coordinate',()=>{
 const rows=[{time:ts('2026-10-27','09:00')},{time:ts('2026-10-27','09:15')+.25,source_timestamp:ts('2026-10-27','09:15')},{time:ts('2026-10-27','09:15')+.5},{time:ts('2026-10-28','09:15')+.25}];
 const out=chartSessionBreaks(rows,{master_regular_session:'0915-1530'});assert.equal(out.length,2);assert.equal(out[0].time,rows[1].time);assert.match(out[0].label,/09:15 IST/);
});
test('MCX uses 09:00 and absent policy never invents a session',()=>{
 const rows=[{time:ts('2026-10-28','09:00')}];
 assert.equal(chartSessionBreaks(rows,{}).length,0);
 assert.match(chartSessionBreaks(rows,{master_regular_session:'0900-2330'})[0].label,/09:00 IST/);
});
test('continuous crypto displays daily boundary rather than NSE opening',()=>{
 const out=chartSessionBreaks([{time:ts('2026-10-28','00:00')},{time:ts('2026-10-28','01:00')}],{seven_day_session:true,session_source:'CONTINUOUS_CRYPTO'});
 assert.equal(out.length,1);assert.match(out[0].label,/Day.*00:00 IST/);
});
