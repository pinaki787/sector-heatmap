const assert = require('node:assert/strict')
const test = require('node:test')
const { analysisStatusText, filterAndSortSectors, qualityText, refreshPhaseState, riskPolicyPreview, rotationDisplay, rotationOverviewValue } = require('../sector-dashboard-model.js')

const sectors = [
  { sector_id: 'auto', rank: 1, overall_score: 80, rank_change: 2, rotation_state: 'LEADING', mtf_alignment: 'BULLISH ALIGNMENT', relative_strength_state: 'Strong Outperformer' },
  { sector_id: 'it', rank: 2, overall_score: 65, rank_change: -1, rotation_state: 'WEAKENING', mtf_alignment: 'MIXED', relative_strength_state: 'Neutral' },
  { sector_id: 'fmcg', rank: 3, overall_score: 35, rank_change: 0, rotation_state: 'LAGGING', mtf_alignment: 'BEARISH ALIGNMENT', relative_strength_state: 'Strong Underperformer' },
  { sector_id: 'metal', rank: 4, overall_score: 55, rank_change: 1, rotation_state: 'IMPROVING', mtf_alignment: 'BULLISH ALIGNMENT', relative_strength_state: 'Outperformer' },
]

test('top and bottom filters use current rank order', () => {
  assert.deepEqual(filterAndSortSectors(sectors, 'top3').map(item => item.sector_id), ['auto', 'it', 'fmcg'])
  assert.deepEqual(filterAndSortSectors(sectors, 'bottom3').map(item => item.sector_id), ['it', 'fmcg', 'metal'])
})

test('rotation, alignment, and relative-strength filters are deterministic', () => {
  assert.deepEqual(filterAndSortSectors(sectors, 'leading').map(item => item.sector_id), ['auto'])
  assert.deepEqual(filterAndSortSectors(sectors, 'bearish').map(item => item.sector_id), ['fmcg'])
  assert.deepEqual(filterAndSortSectors(sectors, 'strong-outperformer').map(item => item.sector_id), ['auto'])
})

test('sorting handles scores and rank change', () => {
  assert.deepEqual(filterAndSortSectors(sectors, 'all', 'score').map(item => item.sector_id), ['auto', 'it', 'metal', 'fmcg'])
  assert.deepEqual(filterAndSortSectors(sectors, 'all', 'rank-change').map(item => item.sector_id), ['auto', 'metal', 'fmcg', 'it'])
})

test('closed market identifies valid previous-session data and preserves its timestamp', () => {
  const analysis = { status: 'MARKET_CLOSED', market_session: { status: 'CLOSED' }, sectors: [{ last_updated: '2026-08-28T15:15:00+05:30' }] }
  assert.equal(analysisStatusText(analysis, value => value), 'MARKET CLOSED — last completed session — data through 2026-08-28T15:15:00+05:30')
  assert.equal(qualityText('MARKET CLOSED'), 'MARKET CLOSED — last completed session')
})

test('open-market stale data remains visibly stale', () => {
  const analysis = { status: 'STALE', market_session: { status: 'OPEN' }, sectors: [{ last_updated: '2026-08-28T15:15:00+05:30' }] }
  assert.equal(analysisStatusText(analysis, value => value), 'DATA STALE — data through 2026-08-28T15:15:00+05:30')
})

test('closed market does not mask stale or failure status', () => {
  const stale = { status: 'STALE', market_session: { status: 'CLOSED' }, sectors: [{ last_updated: '2026-08-27T15:15:00+05:30' }] }
  assert.match(analysisStatusText(stale, value => value), /^DATA STALE · MARKET CLOSED/)
  assert.equal(analysisStatusText({ status: 'UNAVAILABLE', error: 'Provider failed' }), 'Provider failed')
})

test('cold-start loading and retained refresh data are described without failure language', () => {
  const loading = { status: 'LOADING', refreshing: true, refresh_state: { phase: 'LOADING_BARS', message: 'Loading completed bars', completed: 4, total: 20 }, sectors: [] }
  assert.equal(analysisStatusText(loading), 'Preparing sector rotation · Loading completed bars')
  const refreshing = { status: 'DELAYED', refreshing: true, refresh_state: { phase: 'CALCULATING_INDICATORS', message: 'Calculating indicators, ranks and rotation' }, sectors: [{ last_updated: '2026-08-30T15:15:00+05:30' }] }
  assert.equal(analysisStatusText(refreshing, value => value), 'Refreshing · Calculating indicators, ranks and rotation — data through 2026-08-30T15:15:00+05:30')
})

test('failed refresh keeps last valid data distinct from cold-start failure', () => {
  const retained = { status: 'DELAYED', refresh_error: 'Provider timed out', refresh_state: { phase: 'FAILED', last_phase: 'LOADING_BARS' }, sectors: [{ last_updated: '2026-08-30T15:15:00+05:30' }] }
  assert.equal(analysisStatusText(retained, value => value), 'Refresh failed · showing retained data — data through 2026-08-30T15:15:00+05:30')
  assert.equal(analysisStatusText({ status: 'UNAVAILABLE', error: 'Provider timed out', sectors: [] }), 'Provider timed out')
})

test('refresh phases expose completed, active, failed, and pending steps', () => {
  assert.deepEqual(refreshPhaseState({ refresh_state: { phase: 'CALCULATING_INDICATORS' } }).map(step => step.state), ['complete', 'complete', 'active', 'pending'])
  assert.deepEqual(refreshPhaseState({ refresh_state: { phase: 'READY' } }).map(step => step.state), ['complete', 'complete', 'complete', 'complete'])
  assert.deepEqual(refreshPhaseState({ refresh_state: { phase: 'FAILED', last_phase: 'LOADING_BARS' } }).map(step => step.state), ['complete', 'failed', 'pending', 'pending'])
})

test('rotation readiness is rendered as waiting instead of neutral or none', () => {
  const sector = { rotation_state: 'UNAVAILABLE', acceleration_state: 'UNAVAILABLE', rotation_readiness: 'INSUFFICIENT_HISTORY' }
  const overview = { rotation_readiness: 'INSUFFICIENT_HISTORY', leading: [], improving: [], weakening: [], lagging: [] }
  assert.equal(rotationDisplay(sector), 'Waiting for completed-bar history')
  assert.equal(rotationOverviewValue(overview, ['leading']), 'Waiting for completed-bar history')
})

test('rotation quadrant and acceleration pace remain independently visible when ready', () => {
  assert.equal(rotationDisplay({ rotation_state: 'IMPROVING', acceleration_state: 'DECELERATING', rotation_readiness: 'READY' }), 'IMPROVING · DECELERATING')
})

test('risk policy preview validates limits and calculates immediate capacity', () => {
  const preview = riskPolicyPreview({ planningCapital: 100000, dailyLossLimit: 5000, ideaRiskLimit: 2000, riskReserve: 1000, maxPositions: 3, minimumRewardToRisk: 1.5, stopBasis: 'price', orderType: 'LIMIT' }, 500, 750)
  assert.equal(preview.valid, true)
  assert.equal(preview.availableNewIdeaRisk, 2000)
  assert.equal(preview.perPositionCapitalCap, 20000)
  const invalid = riskPolicyPreview({ enforceRiskControls: true, planningCapital: 0, dailyLossLimit: 5000, ideaRiskLimit: 4500, riskReserve: 1000, maxPositions: 0, minimumRewardToRisk: 0.5, stopBasis: '', orderType: '' })
  assert.equal(invalid.valid, false)
  assert.ok(invalid.errors.length >= 5)
})
