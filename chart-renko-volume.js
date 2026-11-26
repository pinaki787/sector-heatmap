/* Broker-source volume allocation for Renko. Does not modify price geometry. */
(function(root){
 'use strict';
 function withRenkoVolume(source,bricks){
  if(!Array.isArray(source)||!Array.isArray(bricks))throw new TypeError('Source candles and Renko bricks are required');
  const groups=new Map(),output=bricks.map(b=>({...b}));
  for(const brick of output){
   if(!Number.isFinite(brick.sourceTime))throw new TypeError('Renko brick requires its source timestamp');
   if(!groups.has(brick.sourceTime))groups.set(brick.sourceTime,[]);
   groups.get(brick.sourceTime).push(brick);
  }
  let previous=-Infinity,pending=0,known=true;
  for(const bar of source){
   if(!Number.isFinite(bar.time)||bar.time<=previous)throw new RangeError('Source candles must have unique increasing timestamps');
   previous=bar.time;
   const usable=Number.isFinite(bar.volume)&&bar.volume>=0;
   known=known&&usable;
   if(known){pending+=bar.volume;if(!Number.isFinite(pending))known=false;}
   const group=groups.get(bar.time);
   if(!group)continue;
   const developing=Boolean(bar.provisional||bar.historyOnly);
   if(group.some(b=>Boolean(b.provisional||b.historyOnly)!==developing))
    throw new RangeError('Renko and source finality must agree');
   const volume=known?(developing?0:pending/group.length):null;
   for(const brick of group){brick.volume=volume;brick.renkoVolume=true;}
   groups.delete(bar.time);
   if(!developing){pending=0;known=true;}
  }
  if(groups.size)throw new RangeError('Renko source candle is missing');
  return output;
 }
 root.SectorPulseRenkoVolume={withRenkoVolume};
 if(typeof module!=='undefined'&&module.exports)module.exports=root.SectorPulseRenkoVolume;
})(typeof window==='undefined'?globalThis:window);
