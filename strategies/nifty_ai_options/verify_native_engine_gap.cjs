#!/usr/bin/env node
// Offline diagnostic only; never selects or writes a sizing reference.
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const path=require('node:path'),root=path.resolve(__dirname,'../..');
const inputPath=path.join(__dirname,'evidence/20261120/history-15m.json');
const bytes=fs.readFileSync(inputPath),candles=JSON.parse(bytes).candles;
const days=new Map();
for(const row of candles){
 const d=new Date((row[0]+19800)*1000),minute=d.getUTCHours()*60+d.getUTCMinutes();
 if(minute<555||minute>=930)continue;
 const key=d.toISOString().slice(0,10);
 if(!days.has(key))days.set(key,new Map());
 const rows=days.get(key);
 if(rows.has(minute))assert.deepEqual(rows.get(minute),row,'conflicting source timestamp');
 rows.set(minute,row);
}
const complete=[],withTail=[],excluded=[];
function aggregate(rows){return {time:rows[0][0],open:rows[0][1],high:Math.max(...rows.map(r=>r[2])),low:Math.min(...rows.map(r=>r[3])),close:rows.at(-1)[4],volume:rows.reduce((s,r)=>s+r[5],0)}}
for(const [date,rows] of [...days].sort()){
 if(date>'2026-11-19')continue;
 const full=Array.from({length:24},(_,i)=>rows.get(555+15*i));
 if(full.some(r=>!r)){excluded.push(date);continue;}
 const bar=aggregate(full);complete.push(bar);withTail.push(bar);
 if(rows.has(915))withTail.push(aggregate([rows.get(915)]));
}
assert.ok(complete.length>=5,'insufficient full six-hour history');
const ctx=vm.createContext({window:{}});vm.runInContext(fs.readFileSync(path.join(root,'chart-workspace-studies.js'),'utf8').replace('root.SectorPulseChartStudies = {','root.SectorPulseChartStudies = {diagnosticATR: atr,'),ctx);
const calc=ctx.window.SectorPulseChartStudies.renkoAtrSize;
assert.equal(typeof calc,'function');
const full=calc(complete,5,.05),tail=calc(withTail,5,.05);
const specialSource=JSON.parse(fs.readFileSync(path.join(__dirname,'evidence/native-parent-special-20261108-1m-raw.json'))).candles;
const specialRows=specialSource.filter(r=>r[0]>=1794127800&&r[0]<1794131100);
assert.equal(specialRows.length,55);
assert.deepEqual(specialRows.map(r=>r[0]),Array.from({length:55},(_,i)=>1794127800+60*i));
const plusSpecial=[...complete,aggregate(specialRows)].sort((a,b)=>a.time-b.time);
const specialSize=calc(plusSpecial,5,.05);
const local=ctx.window.SectorPulseChartStudies;
const fullBricks=local.renko(complete,full,undefined,'close',false);
const tailBricks=local.renko(withTail,tail,undefined,'close',false);
const fullNativeAtr=local.diagnosticATR(fullBricks,5).at(-1);
const tailNativeAtr=local.diagnosticATR(tailBricks,5).at(-1);
const measure=JSON.parse(fs.readFileSync(path.join(__dirname,'evidence/native-measure-diagnostic-20261120.json')));
const referenceAtr=measure.values['ATR5 calculated on native Renko bars'];
const observed=JSON.parse(fs.readFileSync(path.join(__dirname,'evidence/native-reference-20261120-regular.json')));


const report={
 status:'NATIVE_ENGINE_PARITY_NOT_ESTABLISHED',
 observed_native_atr_box:observed.native_box,
 observed_native_bar_atr5:referenceAtr,observed_reference_session:observed.reference_session,
 source_file:path.relative(root,inputPath),source_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
 full_six_hour_parents:complete.length,excluded_incomplete_sessions:excluded,
 actual_chart_function:'SectorPulseChartStudies.renkoAtrSize',
 actual_chart_function_source_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'chart-workspace-studies.js'))).digest('hex'),
 first_full_parent:complete[0].time,last_full_parent:complete.at(-1).time,
 candidates:{full_six_hour_only:full,including_session_tail:tail,including_observed_short_session:specialSize},
 special_session_evidence:{source:'native-parent-special-20261108-1m-raw.json',included_minutes:55,regular_calendar_certified:false},
 native_bar_atr5_candidates:{full_six_hour_only:fullNativeAtr,including_session_tail:tailNativeAtr},
 native_brick_counts:{full_six_hour_only:fullBricks.length,including_session_tail:tailBricks.length},
 requested_observed_chart_box_base_not_natively_constructed:observed.native_box/12,
 diagnostic_bar_atr_base_not_requested:referenceAtr/12,
 candidate_bases_from_renko_bar_atr:{full_six_hour_only:fullNativeAtr/12,including_session_tail:tailNativeAtr/12},
 decision:'The requested reference remains the native chart ATR5 brick setting, observed400. Local chart ATR5 candidates, including310.05 after the observed short-session input, do not reproduce that observation. ATR5 calculated over generated bricks is a separate diagnostic, not the requested replacement. Native construction and completed-window parity remain unverified; no candidate is imported into sizing.',
 unproven:['Input history coverage is not certified calendar-complete','Exact native ATR Renko source-resolution and box update rules','Historical initialization and native rounding','Completed prior-window causality and frozen next-session reference'],
 effects:{broker_reads:0,orders:0,streams_started:0,services_reloaded:0,reference_cache_writes:0}
};
const output=path.join(__dirname,'evidence/native-engine-gap-20261120.json');
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
