const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs");
const source=fs.readFileSync(process.env.FORMING_REFERENCE_CANDIDATE||"chart-workspace.js","utf8");
function section(a,b){const x=source.indexOf(a),y=source.indexOf(b,x);assert.ok(x>=0&&y>x);return source.slice(x,y)}
const helpers=section("  function alternateStudyCandleEnd(","  async function refreshAlternateStudyBars(");
const calendar=section("  function calendarLiveWithPrefix(","  function renderLiveRows(");
const native=section("  function deltaFormingFromNative(","  function alternateStudyCandleEnd(");
const fyers=section("  function fyersFormingLiveBar(","  function calendarLiveWithPrefix(");
const replay=section("  function replayCandleEnd(","  async function replayPineCandles(");
function build(){return new Function(
 "const broker={nse:false},deltaSymbolSelection=true,fyersSymbolSelection=false,motilalSymbolSelection=false;"+
 "const calendarInterval=i=>/[DWM]$/.test(i);"+
 "const candleEnd=(t,i)=>t+(/W$/.test(i)?Number(i.slice(0,-1))*604800:/D$/.test(i)?Number(i.slice(0,-1))*86400:Number(i)*60);"+
 "const chartTickTimestamp=t=>t;"+
 "const deltaBucketStart=(t,i,p)=>t-(p.utc_daily?t%86400:t)%(Number(i)*60);"+
 replay+"\n"+fyers+"\n"+calendar+"\n"+native+"\n"+helpers+
 "return {live:alternateStudyLiveCandle,end:alternateStudyCandleEnd};")();}
const week=1794787200,day=86400,now=week+2*day+43200;
function fixture(){return {state:{bars:[{time:week-604800}],calendarPrefix:{bar:[week,100,120,90,110,20],through:week+day}},frame:{connected:true,latest_tick:now,rows:[[week,111,125,105,124,8,week+2*day]]}}}
test("calendar comparison merges completed days with a fresh current-day snapshot",()=>{const f=fixture();assert.deepEqual(build().live("1W",f.frame,f.state,now),{time:week,open:100,high:125,low:90,close:124,volume:28,provisional:true})});
test("stale, disconnected, and future-dated ticks never publish reference candles",()=>{for(const patch of [{latest_tick:now-60},{latest_tick:now+3},{connected:false}]){const f=fixture();Object.assign(f.frame,patch);assert.equal(build().live("1W",f.frame,f.state,now),undefined)}});
test("mid-period reference without prefix is not promoted to a full week",()=>{const f=fixture();delete f.state.calendarPrefix;assert.equal(build().live("1W",f.frame,f.state,now),undefined)});
test("a gap between prefix and live day is rejected",()=>{const f=fixture();f.state.calendarPrefix.through=week;assert.equal(build().live("1W",f.frame,f.state,now),undefined)});
test("native complete-period snapshot works without prefix",()=>{const f=fixture();delete f.state.calendarPrefix;f.frame.rows[0][6]=week;assert.equal(build().live("1W",f.frame,f.state,now).close,124)});
test("invalid merged OHLC is rejected",()=>{const f=fixture();f.frame.rows[0][2]=115;assert.equal(build().live("1W",f.frame,f.state,now),undefined)});
test("already completed reference is not republished as forming",()=>{const f=fixture();f.state.bars=[{time:week}];assert.equal(build().live("1W",f.frame,f.state,now),undefined)});
test("Delta aggregate uses contiguous native prefix rather than incomplete direct rows",()=>{const time=week,at=time+3*3600+600;const state={bars:[{time:week-day}],intradayPrefix:{utc_daily:true,native_seconds:3600,intraday_prefix:[[time,100,110,90,105,1],[time+3600,105,112,100,108,2],[time+7200,108,113,102,110,3]]}};const frame={connected:true,latest_tick:at,native_row:[time+10800,110,115,109,114,4],rows:[[time,110,115,109,114,4]]};assert.deepEqual(build().live("1380",frame,state,at),{time,open:100,high:115,low:90,close:114,volume:10,provisional:true});state.intradayPrefix.intraday_prefix.splice(1,1);assert.equal(build().live("1380",frame,state,at),undefined)});
test("shortened Delta reference clips at UTC day boundary",()=>assert.equal(build().end(week+82800,"1380",{intradayPrefix:{utc_daily:true}}),week+86400));
test("reference history retains its own calendar and native coverage metadata",async()=>{
 const loader=section("  function studySymbolHistory(","  async function requestChartHistory(");
 const data={rows:[[week-604800,90,100,80,95,10]],prefix:{bar:[week,100,120,90,110,20],through:week+day},native_seconds:3600,intraday_prefix:[],regular_session:[33300,55800],fyers_forming_seed:{bar:[week,100,120,90]}};
 const run=new Function("data","alternateStudyCandleEnd",
 "const barReplay=null,requestScope=new AbortController(),secondaryStudyHistory=new WeakMap(),history=new Map(),broker={yahoo:false},panel={open:false},rows=[];"+
 "const requestChartHistory=async()=>data;"+loader+"return studySymbolHistory;")(data,build().end);
 const state=run("ETHUSD","1W");await new Promise(setImmediate);
 assert.equal(state.pending,false);assert.equal(state.calendarPrefix,data.prefix);assert.equal(state.intradayPrefix,data);assert.equal(state.fyersSeed,data.fyers_forming_seed);assert.equal(state.regularSession,data.regular_session);
});
test("same close with changed range or volume requires a study redraw",()=>{
 const code=section("  function sameCandle(","  function fyersFormingLiveBar(");
 const same=new Function(code+"return sameCandle;")();
 const a={time:week,open:100,high:120,low:90,close:110,volume:20,provisional:true};
 assert.equal(same(a,{...a}),true);assert.equal(same(a,{...a,high:125}),false);assert.equal(same(a,{...a,volume:30}),false);
});
