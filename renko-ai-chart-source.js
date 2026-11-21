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
 return {run,account:q.get('chartSource'),frame:Number(q.get('interval')),brick:Number(q.get('brick'))};
}
function request(path,href,symbol){
 const c=context(href);if(!c)return null;
 if(path.startsWith('/api/chart-workspace/live?'))return {kind:'live',frame:{symbol,connected:false,rows:[],latest_tick:null,source_basis:'AI_RUNTIME_CONFIRMED_ONLY'}};
 if(!path.startsWith('/api/chart-workspace/history?'))return null;
 const original=new URLSearchParams(path.split('?')[1]);
 if(Number(original.get('interval'))!==c.frame)throw Error('Runtime charts retain the source timeframe captured at Start.');
 if(original.has('before'))throw Error('Runtime charts retain their exact initialization seed.');
 const q=new URLSearchParams({run_id:c.run,symbol,frame:String(c.frame)});
 if(original.has('after'))q.set('after',original.get('after'));
 return {kind:'history',path:'/api/renko-supertrend/ai-options/chart-source?'+q};
}
function verify(payload,href,symbol){
 const c=context(href);if(!c)return payload;
 if(payload.account!==c.account||payload.run_id!==c.run||payload.symbol!==symbol||payload.frame!==c.frame||payload.brick!==c.brick||payload.source_basis!=='PROVIDER_CONFIRMED_CLOSE_ONLY'||payload.ohlc_available!==false)throw Error('Chart source differs from the owned runtime instrument, seed or brick.');
 let prior=-Infinity;
 for(const row of payload.rows||[]){
  if(!Array.isArray(row)||row.length!==6||!Number.isFinite(row[0])||row[0]<=prior||!Number.isFinite(row[4])||row[4]<=0||[row[1],row[2],row[3],row[5]].some(v=>v!==null))throw Error('Invalid captured runtime close series.');
  prior=row[0];
 }
 return payload;
}
root.RenkoAiChartSource={context,request,verify};if(typeof module!=='undefined')module.exports={context,request,verify};
})(typeof window==='undefined'?globalThis:window);
