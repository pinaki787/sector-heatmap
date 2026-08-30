const assert = require('node:assert/strict')
const test = require('node:test')
const { filterAndSortSectors } = require('../sector-dashboard-model.js')

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
