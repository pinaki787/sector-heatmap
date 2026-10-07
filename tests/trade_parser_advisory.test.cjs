const {test} = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const {create, render} = require('../trade-parser-advisory.js')
class Element {
  constructor() { this.children = []; this.style = {}; this.hidden = true; this.ownerDocument = {createElement: () => new Element()} }
  appendChild(el) { this.children.push(el) }
  replaceChildren() { this.children = [] }
  get allText() { return (this.textContent || '') + this.children.map(c => c.allText).join(' ') }
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
test('PASS green, FAIL red, unavailable neutral; text never interpreted as HTML', () => {
  const out = new Element()
  render(out, {intraday: {verdict:'PASS', reasons:['<script>bad</script>']}, swing:{verdict:'FAIL', reasons:['Breakdown']}})
  const cards = out.children.filter(c => c.style.cssText)
  assert.match(cards[0].style.cssText, /#35b878/)
  assert.match(cards[1].style.cssText, /#df5b67/)
  assert.match(out.allText, /<script>bad<\/script>/)
  render(out, {message: 'AI feedback skipped: AI is not connected.'})
  assert.doesNotMatch(out.allText, /PASS|FAIL/)
})
test('submission completes while AI is unresolved; no AI on parse', async () => {
  const source = fs.readFileSync('dashboard-enhancements.js','utf8')
  const start = source.indexOf("  $('trade-parser-submit-order').addEventListener('click', async () => {")
  const end = source.indexOf("  $('trade-parser-entry-mode').addEventListener('change'", start)
  const elements = new Map()
  let click, orderCalls = 0, aiCalls = 0, resolveAi
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {value: id === 'trade-parser-input' ? 'BUY TEST' : '1', addEventListener: (_, fn) => { click = fn }})
    return elements.get(id)
  }
  const out = new Element()
  const advisory = create(out, () => { aiCalls++; return new Promise(resolve => { resolveAi = resolve }) }, 1000)
  vm.runInNewContext(source.slice(start,end), {$, parserAdvisory: advisory, refreshParserLifecycle: async () => {}, parserParsedTicket:{symbol:'NSE:TEST',text:'BUY TEST',submission_id:'test-one'},parserSubmissionAttempted:false,
    postJson: async url => { assert.equal(url, '/api/trade-recommendation/submit-direct'); orderCalls++; return {message:'broker result'} }})
  await click()
  assert.equal(orderCalls, 1)
  assert.equal($('trade-parser-submit-order').disabled, true)
  assert.equal($('trade-parser-order-status').textContent, 'broker result')
  await pause(10)
  assert.equal(aiCalls, 1)
  resolveAi({ok:true, json: async () => ({status:'UNAVAILABLE',advisory_only:true,message:'AI unavailable'})})
  await pause(10)
  assert.equal($('trade-parser-order-status').textContent, 'broker result')
  const parseStart = source.indexOf("  $('trade-parser-run').addEventListener")
  const parseEnd = source.indexOf("  $('trade-parser-clear').addEventListener", parseStart)
  assert.doesNotMatch(source.slice(parseStart,parseEnd), /ai-analysis|schedule\(/)
})
test('timeout is unavailable and edit suppresses old results', async () => {
  const out = new Element()
  const stalled = create(out, (_, options) => new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(Object.assign(new Error(),{name:'AbortError'})))), 5)
  await stalled.start({})
  assert.match(out.allText, /timed out/)
  assert.doesNotMatch(out.allText, /FAIL/)
  let resolve
  const control = create(out, () => new Promise(r => {resolve = r}))
  const pending = control.start({})
  control.clear()
  resolve({ok:true,json:async()=>({message:'OLD RESULT'})})
  await pending
  assert.equal(out.hidden, true)
  assert.doesNotMatch(out.allText, /OLD RESULT/)
})
test('failed AI fetch and throwing scheduler cannot change broker result', async () => {
  const out = new Element()
  await create(out, async () => {throw new Error('offline')}).start({})
  assert.match(out.allText,/unavailable/)
  assert.doesNotMatch(out.allText,/FAIL/)
})
