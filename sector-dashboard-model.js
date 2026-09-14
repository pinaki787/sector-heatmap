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

  function latestDataTimestamp(analysis) {
    return (analysis?.sectors || []).reduce((latest, sector) => !sector.last_updated || (latest && latest >= sector.last_updated) ? latest : sector.last_updated, null)
  }

  function analysisStatusText(analysis, formatTime = value => value) {
    const updated = latestDataTimestamp(analysis)
    const suffix = updated ? ` — data through ${formatTime(updated)}` : ''
    const refresh = analysis?.refresh_state || {}
    if (analysis?.refreshing) {
      const prefix = analysis?.sectors?.length ? 'Refreshing' : 'Preparing sector rotation'
      return `${prefix} · ${refresh.message || 'Loading completed bars'}${suffix}`
    }
    if (refresh.phase === 'FAILED' && analysis?.refresh_error && analysis?.sectors?.length) {
      return `Refresh failed · showing retained data${suffix}`
    }
    if (!analysis || analysis.status === 'UNAVAILABLE' || analysis.error) return analysis?.error || refresh.message || 'Analysis unavailable'
    if (analysis.status === 'STALE') return `DATA STALE${analysis.market_session?.status === 'CLOSED' ? ' · MARKET CLOSED' : ''}${suffix}`
    if (analysis.market_session?.status === 'CLOSED') return `MARKET CLOSED — last completed session${suffix}`
    if (analysis.status === 'DELAYED') return `MARKET OPEN · completed-bar data${suffix}`
    return `${analysis.status || 'Analysis ready'}${suffix}`
  }

  function refreshPhaseState(analysis) {
    const order = ['CONNECTING', 'LOADING_BARS', 'CALCULATING_INDICATORS', 'READY']
    const phase = analysis?.refresh_state?.phase || (analysis?.refreshing ? 'CONNECTING' : analysis?.error ? 'FAILED' : 'READY')
    const activeIndex = phase === 'FAILED' ? Math.max(0, order.indexOf(analysis?.refresh_state?.last_phase || 'CONNECTING')) : order.indexOf(phase)
    return order.map((id, index) => ({
      id,
      state: phase === 'FAILED' && index === activeIndex ? 'failed' : index < activeIndex || (phase === 'READY' && index === activeIndex) ? 'complete' : index === activeIndex ? 'active' : 'pending',
    }))
  }

  function qualityText(quality) {
    return quality === 'MARKET CLOSED' ? 'MARKET CLOSED — last completed session' : quality
  }

  function rotationDisplay(sector) {
    if (sector?.rotation_readiness !== 'READY') return 'Waiting for completed-bar history'
    return `${sector.rotation_state || 'Unavailable'} · ${sector.acceleration_state || 'Unavailable'}`
  }

  function rotationOverviewValue(overview, states) {
    if (overview?.rotation_readiness !== 'READY') return 'Waiting for completed-bar history'
    return states.flatMap(state => overview?.[state] || []).join(', ') || 'None'
  }

  function riskPolicyPreview(values, realizedLoss = 0, openWorstCaseRisk = 0) {
    const number = key => Number(values?.[key])
    const planningCapital = number('planningCapital')
    const dailyLossLimit = number('dailyLossLimit')
    const ideaRiskLimit = number('ideaRiskLimit')
    const riskReserve = number('riskReserve')
    const maxPositions = number('maxPositions')
    const minimumRewardToRisk = number('minimumRewardToRisk')
    const errors = []
    if (values?.enforceRiskControls) {
      if (!(planningCapital > 0)) errors.push('Planning capital must be positive when capital controls are enabled.')
      if (!(dailyLossLimit > 0)) errors.push('Daily loss must be positive when capital controls are enabled.')
      if (!(ideaRiskLimit > 0)) errors.push('Per-idea risk must be positive when capital controls are enabled.')
      if (!(riskReserve >= 0)) errors.push('Reserved risk cannot be negative.')
      if (ideaRiskLimit + riskReserve > dailyLossLimit) errors.push('Per-idea risk plus reserve must fit inside the daily loss limit.')
      if (!Number.isInteger(maxPositions) || maxPositions < 1) errors.push('Maximum positions must be a whole number when capital controls are enabled.')
    }
    if (minimumRewardToRisk < 0) errors.push('Minimum reward:risk cannot be negative.')
    if (!['price', 'percent'].includes(values?.stopBasis)) errors.push('Choose a supported stop basis.')
    if (!['LIMIT', 'MARKET'].includes(values?.orderType)) errors.push('Choose a supported order preference.')
    const usedRisk = Number(realizedLoss) + Number(openWorstCaseRisk)
    if (!Number.isFinite(usedRisk) || usedRisk < 0) errors.push('Used risk must be a nonnegative number.')
    if (usedRisk > dailyLossLimit) errors.push('Realized plus worst-case open risk already exceeds the daily loss limit.')
    const perPositionCapitalCap = planningCapital > 0 && maxPositions >= 1 ? planningCapital * 0.6 / maxPositions : 0
    const availableNewIdeaRisk = Math.max(0, Math.min(ideaRiskLimit, dailyLossLimit - usedRisk - riskReserve))
    return {
      valid: errors.length === 0,
      errors,
      usedRisk,
      availableNewIdeaRisk,
      perPositionCapitalCap,
      positionSlots: maxPositions,
      minimumRewardToRisk,
      orderType: values?.orderType,
      stopBasis: values?.stopBasis,
    }
  }

  return { analysisStatusText, filterAndSortSectors, latestDataTimestamp, qualityText, refreshPhaseState, riskPolicyPreview, rotationDisplay, rotationOverviewValue }
})
