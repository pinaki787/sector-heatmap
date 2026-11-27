/* Run-owned closed-price source; standalone and draft charts use normal brokers. */
(function(root){'use strict';
const openingHref=typeof location==='undefined'?null:location.href;
function context(href){
 const u=new URL(href);let q=u.searchParams;const run=q.get('aiRun');
 // The chart consumes initial link settings and then shortens its address.
 // Keep only this exact run/account context bound to the original frozen inputs.
 if(q.get('aiRenko')!=='1'&&openingHref){
  const opening=new URL(openingHref),saved=opening.searchParams;
  if(u.origin===opening.origin&&q.get('chartContext')==='renko'&&q.get('chartSource')===saved.get('chartSource')&&run===saved.get('aiRun'))q=saved;
 }
 if(q.get('chartContext')!=='renko'||q.get('aiRenko')!=='1'||!run)return null;
 if(!/^[A-Za-z0-9_-]{1,80}$/.test(run)||!/^[a-f0-9]{32}$/.test(q.get('chartSource')||''))throw Error('Invalid owned AI chart context.');
 return {run,account:q.get('chartSource'),frame:Number(q.get('interval')),brick:Number(q.get('brick')),...(q.has('aiSourceSymbol')?{sourceSymbol:q.get('aiSourceSymbol')}:{})};
}
function request(path,href,symbol,displayType='Renko'){
 const c=context(href);if(!c||!['Renko','Candles'].includes(displayType))return null;
 if(path.startsWith('/api/chart-workspace/live?')){const q=new URL(path,'https://runtime.invalid');q.searchParams.set('price_only','1');return {kind:'quote',path:q.pathname+q.search};}
 if(!path.startsWith('/api/chart-workspace/history?'))return null;
 const original=new URLSearchParams(path.split('?')[1]);
 if(Number(original.get('interval'))!==c.frame)throw Error('Runtime charts retain the source timeframe captured at Start.');
 if(original.has('before'))throw Error('Runtime charts retain their exact initialization seed.');
 const q=new URLSearchParams({run_id:c.run,symbol:c.sourceSymbol||symbol,frame:String(c.frame)});
 if(c.sourceSymbol)q.set('display_symbol',symbol);
 if(original.has('after'))q.set('after',original.get('after'));
 return {kind:'history',path:'/api/renko-supertrend/ai-options/chart-source?'+q};
}
function quote(payload,href,symbol){
 const c=context(href);if(!c)return payload;
 if(payload.symbol!==symbol)throw Error('Runtime LTP belongs to a different instrument.');
 const price=Number.isFinite(payload.latest_price)?payload.latest_price:payload.native_row?.[4]??payload.rows?.at(-1)?.[4];
 return {symbol,connected:payload.connected===true,latest_tick:payload.latest_tick,latest_price:Number.isFinite(price)&&price>0?price:null,rows:[],forming_row:payload.forming_row,forming_frame:payload.forming_frame,forming_at:payload.forming_at,revision:'runtime-quote-only',source_basis:'AI_RUNTIME_QUOTE_ONLY'};
}
const signalCaches=new Map();
function signalKey(c,symbol){return [c.account,c.run,symbol,c.frame,c.brick].join('|');}
function receiveSignals(payload,c,symbol){
 if(payload.supertrend_basis!=='COMPLETED_RENKO')return;
 const key=signalKey(c,symbol);let state=signalCaches.get(key);
 if(!state){state={points:[],bars:[]};signalCaches.set(key,state);}
 for(const point of payload.signal_points||[]){
  if(point.symbol!==symbol||point.brick!==c.brick||!Number.isInteger(point.index)||point.index<1||!['open','high','low','close','source_time','available_at'].every(k=>Number.isFinite(point[k]))||!((Number.isFinite(point.st)&&[1,-1].includes(point.direction))||(point.st===null&&point.direction===null)))throw Error('Invalid exact-run completed-brick signal.');
  const prior=state.points[point.index-1];
  if(prior){if(JSON.stringify(prior)!==JSON.stringify(point))throw Error('Completed-brick signal revision requires reconciliation.');continue;}
  if(point.index!==state.points.length+1)throw Error('Completed-brick signal history has a gap.');
  state.points.push(point);state.bars.push({...point,time:point.index,sourceTime:point.source_time,provisional:false});
 }
 if(signalCaches.size>8)signalCaches.delete(signalCaches.keys().next().value);
}
function signalBars(href,symbol){const c=context(href);return c?signalCaches.get(signalKey(c,symbol))?.bars:null;}
function verify(payload,href,symbol){
 const c=context(href);if(!c)return payload;
 if(payload.account!==c.account||payload.run_id!==c.run||payload.symbol!==symbol||payload.frame!==c.frame||payload.brick!==c.brick||!['PROVIDER_CONFIRMED_CLOSE_ONLY','BROKER_SEED_AND_LIVE_PRICE','PROVIDER_CONFIRMED_OHLC','BROKER_CONFIRMED_AND_OBSERVED_FORMING'].includes(payload.source_basis)||!([true,false].includes(payload.ohlc_available)))throw Error('Chart source differs from the owned runtime instrument, seed or brick.');
 let prior=-Infinity;
 for(const row of payload.rows||[]){
  if(!Array.isArray(row)||row.length!==6||!Number.isFinite(row[0])||row[0]<=prior||!Number.isFinite(row[4])||row[4]<=0||(payload.ohlc_available?(!row.slice(1,5).every(v=>Number.isFinite(v)&&v>0)||row[3]>Math.min(row[1],row[4])||row[2]<Math.max(row[1],row[4])):[row[1],row[2],row[3],row[5]].some(v=>v!==null)))throw Error('Invalid captured runtime close series.');
  prior=row[0];
 }
 receiveSignals(payload,c,symbol);
 root.RenkoAiBands?.receive(payload);
 return payload;
}
root.RenkoAiChartSource={context,request,verify,quote,signalBars};if(typeof module!=='undefined')module.exports={context,request,verify,quote,signalBars};
})(typeof window==='undefined'?globalThis:window);
