/* Confirmed runtime fills only; no order path or standalone chart state. */
(function(root){'use strict';
function markers(events,bars,symbol){
 const result=[];
 for(const event of events||[]){
  if(event.confirmed!==true||!['PAPER','LIVE'].includes(event.mode)||(event.symbol!==symbol&&event.underlying!==symbol)||!['BUY','SELL','OPEN_LONG','OPEN_SHORT','CLOSE_LONG','CLOSE_SHORT'].includes(event.action))continue;
  const signalTime=Number(event.confirmed_at??event.source_timestamp??event.timestamp);
  const matches=bars.filter(b=>Number(b.sourceTime??b.time)<=signalTime&&!b.provisional);
  const bar=matches.at(-1);if(!bar)continue;
  const entry=event.action==='BUY'||event.action.startsWith('OPEN_');
  result.push({time:bar.time,position:entry?'belowBar':'aboveBar',color:entry?'#26a69a':'#ef5350',shape:entry?'arrowUp':'arrowDown',text:''});
 }
 return result.sort((a,b)=>a.time-b.time);
}
function entryLine(position,bars,symbol){
 if(!position||!(Number(position.quantity)>0))return null;
 const exact=position.symbol===symbol;
 let price=exact?position.fill_price:position.underlying===symbol?position.entry_underlying_price:null;
 let reference=false;
 if(!exact&&position.underlying===symbol&&!Number.isFinite(price)){
  const stamp=Number(position.entry_confirmed_at??position.entry_timestamp);
  const source=bars||[];let left=0,right=source.length;
  while(left<right){const mid=(left+right)>>1;if(Number(source[mid].sourceTime??source[mid].time)<=stamp)left=mid+1;else right=mid;}
  let index=left-1;while(index>=0&&source[index].provisional)index--;
  const bar=source[index];
  price=bar?.close;reference=true;
 }
 if(typeof price!=='number'||!Number.isFinite(price)||price<=0)return null;
 return {price,color:['SHORT','PE'].includes(position.side)?'#ef5350':'#26a69a',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'',reference};
}
function currentLine(position,bars,symbol,trade,now=Date.now()/1000){
 const entry=entryLine(position,bars,symbol);if(!entry)return null;
 const bar=bars?.at(-1);let price=bar?.close;
 const exact=position.symbol===symbol;
 const orderMatches=!(position.order_id||trade?.entry_order)||(!!position.order_id&&String(position.order_id)===String(trade?.entry_order||''));
 const validTrade=orderMatches&&trade&&trade.symbol===position.symbol&&trade.status==='OPEN'&&Number(trade.quantity)===Number(position.quantity)&&Number(trade.entry_premium)===Number(position.fill_price)&&Number.isFinite(trade.unrealized_gross)&&Number.isFinite(trade.latest_time)&&now-trade.latest_time>=0&&now-trade.latest_time<=15;
 if(exact&&validTrade&&Number.isFinite(trade.latest_price))price=trade.latest_price;
 if(!Number.isFinite(price)||price<=0)return null;
 const sign=!exact&&position.side==='PE'||position.side==='SHORT'?-1:1;
 const points=sign*(price-entry.price);
 const value=validTrade?trade.unrealized_gross:points;
 const title=validTrade?(trade.currency||'')+' '+(value>=0?'+':'')+value.toFixed(2)+' gross':(value>=0?'+':'')+value.toFixed(2)+' pts';
 return {price,title,color:value>=0?'#26a69a':'#ef5350',lineWidth:1,lineStyle:0,axisLabelVisible:true};
}
function stopLine(stop,position,symbol,now=Date.now()/1000){
 if(!stop||!position||position.symbol!==symbol||stop.symbol!==symbol||!position.order_id||String(position.order_id)!==stop.order_id||!(position.quantity>0)||stop.kind!=='STRATEGY_MANAGED'||stop.broker_resting!==false||!Number.isFinite(stop.price)||stop.price<=0||!Number.isFinite(stop.verified_at)||now-stop.verified_at<0||now-stop.verified_at>8)return null;
 return {price:stop.price,title:(stop.confirmation_mode==='RENKO_BRICKS_ONLY'?'Stop · completed brick ':'Strategy stop ')+stop.price.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}),color:'#d97706',lineWidth:2,lineStyle:2,axisLabelVisible:true};
}
root.RenkoAiChartMarkers={markers,entryLine,currentLine,stopLine};if(typeof module!=='undefined')module.exports={markers,entryLine,currentLine,stopLine};
})(typeof window==='undefined'?globalThis:window);
