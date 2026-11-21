const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const source = fs.readFileSync('dashboard-enhancements.js', 'utf8')
function fixture() {
  const unrelated = { hidden: false, dataset: {}, querySelector: () => null }
  const elements = new Map()
  const boardCards = []
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {
      hidden: false, innerHTML: '', textContent: '',
      querySelectorAll: () => boardCards,
      addEventListener: (_, handler) => { elements.get(id).handler = handler },
    })
    return elements.get(id)
  }
  const document = { querySelectorAll: selector => selector === '.opportunity-card' ? [unrelated, ...boardCards] : [] }
  return { $, document, unrelated, boardCards }
}
test('empty handoff with exclusions does not hydrate unrelated EMA or screener cards', () => {
  const f = fixture()
  const start = source.indexOf('  const renderAnalysisCards = () => {')
  const end = source.indexOf('  const acceptAnalysisCard =', start)
  const analysisRun = { cards: [], exclusions: [{kind:'OPTIONS',name:'Example',reason:'Evidence gate failed'}] }
  vm.runInNewContext(source.slice(start, end) + '\nrenderAnalysisCards()', {
    ...f, analysisRun, escapeHtml: String,
  })
  assert.match(f.$('analysis-board').innerHTML, /No fresh opportunity/)
  assert.match(f.$('analysis-exclusions').innerHTML, /Evidence gate failed/)
  assert.equal(f.unrelated.hidden, false)
})
test('clearing handoff selection hides its plans only', () => {
  const f = fixture()
  const own = {hidden:false}
  f.boardCards.push(own)
  const start = source.indexOf("  $('clear-candidate-selection').addEventListener")
  const end = source.indexOf("  $('prepare-handoff-batch').addEventListener", start)
  vm.runInNewContext(source.slice(start, end), f)
  f.$('clear-candidate-selection').handler()
  assert.equal(own.hidden, true)
  assert.equal(f.unrelated.hidden, false)
})
test('candidate selection filters handoff plans without hiding other views', () => {
  const f = fixture()
  const selected = {value:'selected',addEventListener:(_, handler)=>{selected.handler=handler}}
  const matching = {hidden:true,dataset:{candidateKey:'selected'}}
  const other = {hidden:false,dataset:{candidateKey:'other'}}
  f.boardCards.push(matching,other)
  f.document.querySelectorAll = selector => ({
    '.candidate-select':[selected], '.candidate-select:checked':[selected],
    '.opportunity-card':[f.unrelated,...f.boardCards],
  })[selector] || []
  const start = source.indexOf('  const renderCandidates = () => {')
  const end = source.indexOf('  const policyPayload =',start)
  vm.runInNewContext(source.slice(start,end)+'\nrenderCandidates()', {...f,candidateCollection:{candidates:[]},selectedInstrumentRoute:()=> 'cash_equity'})
  selected.handler()
  assert.equal(matching.hidden,false)
  assert.equal(other.hidden,true)
  assert.equal(f.unrelated.hidden,false)
})
