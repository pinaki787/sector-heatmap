/* Percentage-LTP sizing inferred from captured native series.
 * Captured BTCUSD/PAXGUSD/ETHUSD cases establish selected sizes, not universal parity.
 */
(function(root){
 'use strict';
 function renkoPercentageSize(price,percentage,tick){
  if(![price,percentage,tick].every(n=>Number.isFinite(n)&&n>0))throw new TypeError('Positive finite price, percentage and tick are required');
  const raw=price*percentage/100;
  if(!Number.isFinite(raw)||raw<=0)throw new RangeError('Percentage size is outside the supported numeric range');
  const tickExponent=Math.floor(Math.log10(tick)+1e-12);
  const mantissa=tick/Math.pow(10,tickExponent);
  const quantum=.5*Math.pow(10,Math.ceil(Math.log10(mantissa)-1e-12)+Math.floor(Math.log10(raw/mantissa)+1e-12));
  if(!Number.isFinite(quantum)||quantum<=0)throw new RangeError('Percentage rounding quantum is outside the supported numeric range');
  const rounded=Math.round(raw/quantum)*quantum;
  const units=rounded/tick;
  if(!Number.isFinite(units)||units>Number.MAX_SAFE_INTEGER)throw new RangeError('Percentage size has too many broker ticks');
  return Math.max(1,Math.round(units+Math.abs(units)*Number.EPSILON*2))*tick;
 }
 root.SectorPulseRenkoSizing={renkoPercentageSize};
 if(typeof module!=='undefined'&&module.exports)module.exports=root.SectorPulseRenkoSizing;
})(typeof window==='undefined'?globalThis:window);
