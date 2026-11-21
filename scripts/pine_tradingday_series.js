// Pine built-in metadata must retain history just like price series.
// Recompute the current element on same-bar updates; rebuild if history shrinks
// or symbol metadata changes. Secondary contexts own separate caches.
function spPineTradingDaySeries(context) {
  const zone = context.pine?.syminfo?.timezone || "UTC";
  const crypto = context.pine?.syminfo?.type === "crypto";
  const closes = context.data.closeTime.data;
  let cache = context._spTradingDaySeries;
  if (!cache || cache.zone !== zone || cache.crypto !== crypto || cache.series.data.length > closes.length) {
    cache = context._spTradingDaySeries = {zone, crypto, series: new y([])};
  }
  const values = cache.series.data;
  for (let index = Math.max(0, values.length - 1); index < closes.length; index++) {
    const close = closes[index];
    if (!Number.isFinite(close)) values[index] = NaN;
    else {
      const date = Ai(close - (crypto ? 1 : 0), zone);
      values[index] = Date.UTC(date.year, date.month - 1, date.day);
    }
  }
  return cache.series;
}
