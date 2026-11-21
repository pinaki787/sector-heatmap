/* Confirmed runtime fills only; no order path or standalone chart state. */
(function(root){'use strict';
function markers(events,bars,symbol){
 const result=[];
 for(const event of events||[]){
  if(event.confirmed!==true||!['PAPER','LIVE'].includes(event.mode)||event.symbol!==symbol||!['BUY','SELL','OPEN_LONG','OPEN_SHORT','CLOSE_LONG','CLOSE_SHORT'].includes(event.action))continue;
  const signalTime=Number(event.source_timestamp??event.timestamp);
  const matches=bars.filter(b=>Number(b.sourceTime??b.time)<=signalTime&&!b.provisional);
  const bar=matches.at(-1);if(!bar)continue;
  const entry=event.action==='BUY'||event.action.startsWith('OPEN_');
  result.push({time:bar.time,position:entry?'belowBar':'aboveBar',color:entry?'#26a69a':'#ef5350',shape:entry?'arrowUp':'arrowDown',text:event.mode+' '+(entry?'ENTRY':'EXIT')+(Number.isFinite(event.price)?' '+event.price.toFixed(2):'')});
 }
 return result.sort((a,b)=>a.time-b.time);
}
root.RenkoAiChartMarkers={markers};if(typeof module!=='undefined')module.exports={markers};
})(typeof window==='undefined'?globalThis:window);
