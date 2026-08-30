(function exposeSectorDashboardModel(root, factory) {
  const model = factory()
  if (typeof module === 'object' && module.exports) module.exports = model
  else root.SectorDashboardModel = model
})(typeof globalThis === 'object' ? globalThis : this, () => {
  const sortKeys = { rank: 'rank', score: 'overall_score', 'rank-change': 'rank_change', 'relative-strength': 'relative_strength_score', momentum: 'momentum_score', breadth: 'breadth_score', volume: 'volume_score', adx: 'adx' }

  function filterAndSortSectors(sectors, filter = 'all', sort = 'rank') {
    let rows = [...sectors]
    if (filter === 'top3') rows = rows.filter(item => item.rank && item.rank <= 3)
    else if (filter === 'top5') rows = rows.filter(item => item.rank && item.rank <= 5)
    else if (filter === 'bottom3') rows = rows.filter(item => item.rank).slice(-3)
    else if (filter === 'bottom5') rows = rows.filter(item => item.rank).slice(-5)
    else if (['leading', 'improving', 'neutral', 'weakening', 'lagging'].includes(filter)) rows = rows.filter(item => item.rotation_state === filter.toUpperCase())
    else if (filter === 'bullish') rows = rows.filter(item => item.mtf_alignment.includes('BULLISH'))
    else if (filter === 'bearish') rows = rows.filter(item => item.mtf_alignment.includes('BEARISH'))
    else if (filter === 'strong-outperformer') rows = rows.filter(item => item.relative_strength_state === 'Strong Outperformer')
    else if (filter === 'strong-underperformer') rows = rows.filter(item => item.relative_strength_state === 'Strong Underperformer')
    const key = sortKeys[sort] || 'rank'
    rows.sort((left, right) => key === 'rank' ? (left.rank ?? 999) - (right.rank ?? 999) : (right[key] ?? -Infinity) - (left[key] ?? -Infinity))
    return rows
  }

  return { filterAndSortSectors }
})
