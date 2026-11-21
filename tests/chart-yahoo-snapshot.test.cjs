const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const candidate=process.env.YAHOO_SNAPSHOT_CANDIDATE||'chart-workspace.js';
const source=fs.readFileSync(candidate,'utf8'),start=source.indexOf('  function calendarHistoryPrefix('),end=source.indexOf('  function calendarLiveWithPrefix(',start);
const enabled=start>=0&&end>start;
const run=enabled?new Function('broker','candleEnd',source.slice(start,end)+'return {calendarHistoryPrefix,calendarPrefixAvailableAt,calendarRowsAtSnapshotCutoff};')({yahoo:true},time=>time+86400):null;
const snapshot=()=>({forming_snapshot:{provider:'Yahoo Finance',provisional:true,history_only:true,bar:[100,10,14,8,12,5],as_of:500,close_time:1000}});
test('provider-stamped Yahoo snapshot is copied into provisional context only',{skip:!enabled},()=>{
 const data=snapshot(),p=run.calendarHistoryPrefix(data,true,600);
 assert.deepEqual(p,{bar:[100,10,14,8,12,5],through:500,close_time:1000,snapshot:true});
 assert.notEqual(p.bar,data.forming_snapshot.bar);assert.equal(data.rows,undefined);
});
test('broker prefixes stay unchanged and other brokers cannot inherit Yahoo snapshots',{skip:!enabled},()=>{
 const native={bar:[100,1,2,1,2,1],through:200};assert.equal(run.calendarHistoryPrefix({prefix:native},false,600),native);
 assert.equal(run.calendarHistoryPrefix(snapshot(),false,600),null);
});
test('future expired invalid or unmarked snapshots do not enter chart context',{skip:!enabled},()=>{
 for(const change of [{as_of:700},{close_time:600},{provisional:false},{history_only:false},{provider:'Other'},{bar:[100,10,9,8,12,5]},{bar:[100,10,14,8,12,-1]}]){
  const data=snapshot();Object.assign(data.forming_snapshot,change);assert.equal(run.calendarHistoryPrefix(data,true,600),null,JSON.stringify(change));
 }
});
test('Pine cutoff uses snapshot observation time rather than future period close',{skip:!enabled},()=>{
 const p=run.calendarHistoryPrefix(snapshot(),true,600);
 assert.equal(run.calendarPrefixAvailableAt(p,499999),false);assert.equal(run.calendarPrefixAvailableAt(p,500000),true);
 const confirmed={time:50,close:10},forming={time:100,close:12,provisional:true},bars=[confirmed,forming];
 assert.deepEqual(run.calendarRowsAtSnapshotCutoff(bars,p,499999),[confirmed]);
 assert.equal(run.calendarRowsAtSnapshotCutoff(bars,p,500000),bars);
 assert.equal(run.calendarRowsAtSnapshotCutoff(bars,p,null),bars);
 assert.equal(run.calendarRowsAtSnapshotCutoff(bars,{through:100},0),bars);
 assert.equal(run.calendarPrefixAvailableAt({through:100},86499999),false);
});
