from pathlib import Path
import sqlite3,json,hashlib,subprocess
out=Path(".private/chart-order-rollouts/twap-study-20261119");out.mkdir(exist_ok=True)
db=Path(".private/dashboard-login/registry.sqlite3").resolve()
with sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)as c:ids=[r[0]for r in c.execute("select id from accounts")]
roots=[Path(".")]+[Path(".private/dashboard-login/accounts")/a/"source"for a in ids if(Path(".private/dashboard-login/accounts")/a/"source/chart-workspace.js").exists()]
helper="""  const twapCalendarAnchors = {'1D': 'Session', '1W': 'Week', '1M': 'Month', '3M': 'Quarter', '12M': 'Year'};
  function anchoredTwap(bars, inputs = {}, symbolInfo = {}) {
    const {anchor = '1D', source = 'ohlc4'} = inputs;
    const calendar = twapCalendarAnchors[anchor];
    const priceSource = studyPriceSourceNames.includes(source) ? pineSources[source] : pineSources.ohlc4;
    let previousKey, count = 0, mean = 0;
    return [bars.map(bar => {
      const key = calendar ? vwapPeriodKey(bar, calendar, symbolInfo) : symbolInfo.twapAnchorKey?.(bar);
      if (key === undefined || key === null) return null;
      if (key !== previousKey) { previousKey = key; count = 0; mean = 0; }
      const value = priceSource(bar);
      if (!Number.isFinite(value)) return null;
      mean += (value - mean) / ++count;
      return mean;
    })];
  }

"""
definition="""    TWAP: {
      name: 'Time Weighted Average Price', allPlotOffset: true,
      plotNames: ['TWAP'], plotColors: ['#2962ff'],
      inputs: [
        {id: 'anchor', title: 'Anchor period', type: 'string', value: '1D', options: ['1D', '1W', '1M', '3M', '12M']},
        {id: 'source', title: 'Source', type: 'source', value: 'ohlc4', options: studyPriceSourceNames},
        {id: 'offset', title: 'Offset', value: 0, min: -500, max: 500}
      ],
      run: (bars, values, length, multiplier, inputs, symbolInfo) => anchoredTwap(bars, inputs, symbolInfo)
    },
"""
front="""  function twapAnchor(study) {
    const anchor = study.inputs?.anchor ?? '1D';
    return typeof anchor === 'string' && validInterval(anchor) && !tickInterval(anchor) && sourceInterval(anchor)
      ? anchor : undefined;
  }

  function twapReferenceInterval(study, host = settings.interval) {
    const anchor = twapAnchor(study);
    return anchor && !['1D', '1W', '1M', '3M', '12M'].includes(anchor)
      && !tradeInterval(anchor) && projectionIntervalSeconds(anchor) > projectionIntervalSeconds(host)
      ? anchor : undefined;
  }

  function twapBrokerAnchorKey(study) {
    const anchor = twapAnchor(study);
    if (!anchor) return () => undefined;
    if (['1D', '1W', '1M', '3M', '12M'].includes(anchor)) return undefined;
    if (!twapReferenceInterval(study)) return bar => bar.sourceTime ?? bar.time;
    const byTime = new Map((history.get(anchor) ?? []).map(bar => [bar.time, bar]));
    const stored = liveStudyBars.get(anchor);
    const live = stored?.scope === requestScope?.signal ? stored.candle : undefined;
    if (!barReplay && live?.provisional && !live.historyOnly) byTime.set(live.time, live);
    const reference = [...byTime.values()].sort((a, b) => a.time - b.time);
    return bar => {
      const time = bar.sourceTime ?? bar.time;
      let low = 0, high = reference.length;
      while (low < high) {
        const middle = (low + high) >>> 1;
        if (reference[middle].time <= time) low = middle + 1;
        else high = middle;
      }
      const source = reference[low - 1];
      return source && time < candleEnd(source.time, anchor) ? source.time : undefined;
    };
  }

"""
def replace(s,a,b):
 assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b,1)
entries=[]
for i,root in enumerate(roots):
 lib=root/"chart-workspace-studies.js";s=lib.read_text()
 s=replace(s,"  function anchoredVwap(",helper+"  function anchoredVwap(")
 s=replace(s,"    VWAP: {",definition+"    VWAP: {")
 js=root/"chart-workspace.js";n=js.read_text()
 n=replace(n,"  function historyIntervals(interval) {",front+"  function historyIntervals(interval) {")
 n=replace(n,"      const calculation = calculationInterval(study, interval);\n      if (calculation) targets.add(calculation);","      const calculation = calculationInterval(study, interval);\n      if (calculation) targets.add(calculation);\n      const twap = study.kind === 'TWAP' && twapReferenceInterval(study, interval);\n      if (twap) targets.add(twap);")
 n=replace(n,"    if (calculationTimeframeStudies.has(study.kind)) {\n      const options", """    if (study.kind === 'TWAP' && section === 'Inputs') {
      const options = intervalGroups.flatMap(([, unit, values]) => values.map(value =>
        unit === 'h' ? String(value * 60) : unit === 'm' ? String(value) : value + unit));
      const anchors = [...new Set([...options, settings.interval, ...(settings.customIntervals ?? [])])]
        .filter(value => validInterval(value) && !tickInterval(value) && sourceInterval(value));
      const selected = twapAnchor(study);
      if (selected && !anchors.includes(selected)) anchors.push(selected);
      definitions = definitions.map(input => input.id === 'anchor'
        ? {...input, options: anchors, optionLabel: intervalLabel} : input);
    }
    if (calculationTimeframeStudies.has(study.kind)) {
      const options""")
 n=replace(n,"      const symbolInfo = pineSymbolInfo();\n      const requestedCalculation", "      const symbolInfo = pineSymbolInfo();\n      if (study.kind === 'TWAP') symbolInfo.twapAnchorKey = twapBrokerAnchorKey(study);\n      const requestedCalculation")
 n=replace(n,"      const interval = calculationInterval(study, hostInterval);\n      if (studyUsesFormingBar(study, interval)) targets.add(interval);","      const interval = calculationInterval(study, hostInterval);\n      if (studyUsesFormingBar(study, interval)) targets.add(interval);\n      const twap = study.kind === 'TWAP' && twapReferenceInterval(study, hostInterval);\n      if (twap && studyCanUseFormingBar(twap)) targets.add(twap);")
 n=replace(n,"      if (!indicators[study.kind]?.deltaCandles || usesTickDelta(study) || !studyVisible(study, interval)) continue;","      if (!studyVisible(study, interval)) continue;\n      const twap = study.kind === 'TWAP' && twapReferenceInterval(study, interval);\n      if (twap && olderHistory.has(twap)) targets.add(twap);\n      if (!indicators[study.kind]?.deltaCandles || usesTickDelta(study)) continue;")
 n=replace(n,"          studyHistoryChanged = (study.kind === 'PivotStandard'", "          studyHistoryChanged = (study.kind === 'TWAP' && field === 'anchor')\n            || (study.kind === 'PivotStandard'")
 for typ,path,text in [("library",lib,s),("frontend",js,n)]:
  original=path.read_bytes();(out/("owner-"+str(i)+"."+typ+".before.js")).write_bytes(original)
  candidate=out/("owner-"+str(i)+"."+typ+".candidate.js");candidate.write_text(text)
  subprocess.run(["node","--check",str(candidate)],check=True,capture_output=True)
  entries.append({"kind":typ,"path":str(path),"candidate":str(candidate),"sha256_before":hashlib.sha256(original).hexdigest(),"sha256_after":hashlib.sha256(text.encode()).hexdigest()})
(out/"manifest.json").write_text(json.dumps({"status":"STAGED_NOT_PUBLISHED","entries":entries,"reference":"https://www.tradingview.com/support/solutions/43000692939-time-weighted-average-price/","limits":["Custom-anchor and synthetic-chart semantics require numeric and hosted verification before publication."]},indent=2)+"\n")
print("Staged TWAP library andbroker-anchor integration in7sources;syntaxpass;notpublished.")
