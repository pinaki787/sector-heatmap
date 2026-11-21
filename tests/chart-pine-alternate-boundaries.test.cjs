const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs");
const source=fs.readFileSync(process.env.PINE_REFERENCE_CANDIDATE||"chart-workspace.js","utf8");
function section(first,last){const a=source.indexOf(first),b=source.indexOf(last,a);assert.ok(a>=0&&b>a);return source.slice(a,b)}
const loader=section("  async function loadAlternatePineReference(","  async function loadPineCandles(");
const windows=section("  function yahooPineReferenceClose(","  const pineDrawingKinds =");
const snapshots=source.includes("  function calendarHistoryPrefix(")?section("  function calendarHistoryPrefix(","  function calendarLiveWithPrefix("):"";
const replay=section("  function replayCandleEnd(","  async function replayPineCandles(");
function fixture(metadata={},yahoo=false){const day=1794873600;const data={rows:[[day,100,110,90,105,1],[day+82800,105,112,101,108,2]],older_history:false,...metadata};const calls=[];const run=new Function("data","calls","yahoo",`
 const broker={yahoo},deltaSymbolSelection=!yahoo,alternatePineHistory=new WeakMap(),requestScope=new AbortController(),rows=[];
 const chartQuery=(args,symbol)=>new URLSearchParams({...args,symbol});
 const requestChartHistory=async(path)=>{calls.push(path);return data};
 const candleEnd=(time,resolution)=>time+Number(resolution)*60;
 const calendarInterval=()=>false;
 ${windows}\n${replay}\n${snapshots}\n${loader}
 return loadAlternatePineReference;
 `)(data,calls,yahoo);return {day,data,calls,run};}
test("alternate Delta request uses its own UTC-day clipping metadata",async()=>{const f=fixture({utc_daily:true});const rows=await f.run("ETHUSD","1380",{},new AbortController().signal);assert.deepEqual(rows.map(x=>x.closeTime),[(f.day+82800)*1000,(f.day+86400)*1000]);assert.match(f.calls[0],/symbol=ETHUSD/);assert.equal(rows[1].close,108)});
test("alternate reference without UTC-day metadata retains source interval semantics",async()=>{const f=fixture();const rows=await f.run("ETHUSD","1380",{},new AbortController().signal);assert.equal(rows[1].closeTime,(f.day+165600)*1000)});
test("Yahoo alternate reference retains explicit exchange close timestamps",async()=>{const day=1794873600;const f=fixture({close_times:{[day]:day+1200,[day+82800]:day+84000}},true);const rows=await f.run("OTHER","1380",{},new AbortController().signal);assert.deepEqual(rows.map(x=>x.closeTime),[(day+1200)*1000,(day+84000)*1000])});
test("reference request window and limit remain intact",async()=>{const f=fixture({utc_daily:true});const rows=await f.run("ETHUSD","1380",{start:(f.day+82800)*1000,end:(f.day+82800)*1000,limit:1},new AbortController().signal);assert.equal(rows.length,1);assert.equal(rows[0].openTime,(f.day+82800)*1000);assert.equal(rows[0].closeTime,(f.day+86400)*1000)});
test("14h,22h,23h reference periods all clip their final short candle at UTC midnight",async()=>{for(const interval of ["840","1320","1380"]){const f=fixture({utc_daily:true});const offset=Number(interval)*60;f.data.rows[1][0]=f.day+offset;const rows=await f.run("ETHUSD",interval,{},new AbortController().signal);assert.equal(rows[0].closeTime,(f.day+offset)*1000);assert.equal(rows[1].closeTime,(f.day+86400)*1000)}});
