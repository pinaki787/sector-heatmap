"""Stage ONLY this feature's targeted edits in account-owned source snapshots; never reload."""
raise SystemExit("Retired initial staging helper: patterns predate strategy-only fixed-brick isolation. Use reviewed focused patches; do not rerun this migration.")
from pathlib import Path
import json,shutil
ROOT=Path('/home/trading/sector-heatmap')
changes=[]
def replace(text,old,new,label):
    if new in text:return text
    if old in text:return text.replace(old,new,1)
    raise ValueError('Source pattern unavailable: '+label)
def run(folder):
    changed=[]
    p=folder/'broker-form-routing.js';s=p.read_text()
    s=replace(s,"function renkoSwitchUrl(href,selected){","function renkoSwitchUrl(href,selected,renkoView=true){",'routing signature')
    s=replace(s,"u.searchParams.set('renkoBroker',selected.broker);","if(renkoView){u.searchParams.set('view','renko-supertrend');\n for(const key of ['chartSource','chartContext','chartInstance','symbol','interval','type','method','brick','renkoSource','aiRenko'])u.searchParams.delete(key);}\n u.searchParams.set('renkoBroker',selected.broker);",'renko route')
    s=replace(s,"const u=new URL(renkoSwitchUrl(href,selected));","const u=new URL(renkoSwitchUrl(href,selected,kind==='renko'));",'shared routing')
    p.write_text(s);changed.append(str(p.relative_to(folder)))
    p=folder/'chart-workspace.js';s=p.read_text()
    s=replace(s,"const sharedChartParameters = ['symbol'","const sharedChartParameters = ['chartContext', 'chartInstance', 'aiRenko', 'symbol'",'chart params')
    s=replace(s,"chartStoragePrefix = 'sector-pulse:chart-workspace:' + context.username + ':';","const embeddedRenko = linkedChart?.chartContext === 'renko';\n    chartStoragePrefix = 'sector-pulse:chart-workspace:' + context.username + (embeddedRenko ? ':renko:' + encodeURIComponent(linkedChart.chartInstance || 'default') + ':' : ':');",'chart key')
    s=replace(s,"sharedChartView = Boolean(linkedChart && !linkedChart.saveAsRegularView","sharedChartView = Boolean(linkedChart && !embeddedRenko && !linkedChart.saveAsRegularView",'chart saving')
    needle="    if (restoreView) {\n      settings = restoreView.settings;"
    insert="""    if (embeddedRenko && linkedChart.aiRenko === '1') {
      settings.studies = settings.studies.filter(study => study.kind !== 'Pine' || study.name !== 'AI Renko Supertrend');
      settings.studies.push({kind: 'Pine', name: 'AI Renko Supertrend', source: aiRenkoPineSource(), color: '#2962ff', workerRuntime: true});
    }
"""
    if insert not in s:s=replace(s,needle,insert+needle,'chart study')
    s=replace(s,"const selectionKey = 'sector-pulse:chart-source:' + window.SectorPulseWorkspace.username;","const embeddedParams = new URLSearchParams(location.search);\n    const embeddedScope = embeddedParams.get('chartContext') === 'renko' ? ':renko:' + encodeURIComponent(embeddedParams.get('chartInstance') || 'default') + ':' + encodeURIComponent(embeddedParams.get('chartSource') || '') : '';\n    const selectionKey = 'sector-pulse:chart-source:' + window.SectorPulseWorkspace.username + embeddedScope;",'source selection key')
    s=replace(s,"for (const param of sharedChartParameters) url.searchParams.delete(param);\n      url.searchParams.set('view', feature);","for (const param of sharedChartParameters) if (!embeddedScope || !['chartContext','chartInstance'].includes(param)) url.searchParams.delete(param);\n      url.searchParams.set('view', feature);",'keep chart context')
    p.write_text(s);changed.append(str(p.relative_to(folder)))
    source=(ROOT/'renko-supertrend.js').read_text()
    p=folder/'renko-supertrend.js';s=p.read_text()
    helper=source[source.index('  function embeddedRenkoChartUrl('):source.index('  function sharedRunnerCharts(')]
    if 'function embeddedRenkoChartUrl(' not in s:s=s.replace('  function sharedRunnerCharts(',helper+'  function sharedRunnerCharts(',1)
    old="const url=new URL(location.href);url.searchParams.set('renkoBroker',item.broker);url.searchParams.set('renkoInstance',key);url.searchParams.set('renkoBatchChart','1');url.searchParams.set('renkoChartSymbol',item.instrument||item.config?.underlying);frame.src=url.href;"
    new="const accountId=root.BrokerForms?.account('renko')?.id||dhanAccount;frame.src=embeddedRenkoChartUrl(location.href,{accountId,broker:item.broker,symbol:item.instrument||item.config?.underlying,instance:key,timeframe:el('timeframe').value,brick:item.config?.brick_mode==='Manual'?item.config?.manual_brick:undefined,ai:el('strategy-mode').value==='AI_RENKO_OPTIONS'});"
    s=replace(s,old,new,'embedded iframe')
    needle="card.querySelector('h3').textContent=(item.instrument||item.config?.underlying)"
    start=source.index('const chartFrame=card.querySelector(\'iframe\');const nextChartUrl=')
    end=source.index(needle,start)
    if 'const nextChartUrl=embeddedRenkoChartUrl' not in s:s=replace(s,needle,source[start:end]+needle,'chart synchronization')
    s=replace(s,"root.RenkoSupertrend={mount,signalSettings,renderTradeTable}","root.RenkoSupertrend={mount,signalSettings,renderTradeTable,embeddedRenkoChartUrl}",'public helper')
    s=replace(s,"module.exports={chartSimulationMarkers","module.exports={embeddedRenkoChartUrl,chartSimulationMarkers",'test helper')
    p.write_text(s);changed.append(str(p.relative_to(folder)))
    shutil.copy2(ROOT/'renko-ai-options.js',folder/'renko-ai-options.js')
    p=folder/'index.html';s=p.read_text()
    if '/renko-ai-options.js?' not in s:
        needle='    <script src="/broker-form-routing.js?'
        at=s.index('\n',s.index(needle));s=s[:at]+'\n    <script defer src="/renko-ai-options.js?v=20261120-1"></script>'+s[at:]
    p.write_text(s);changed+=['renko-ai-options.js','index.html']
    # Module copies have no environment, evidence, state or credentials.
    destination=folder/'strategies/nifty_ai_options';destination.mkdir(exist_ok=True)
    for module in (ROOT/'strategies/nifty_ai_options').glob('*.py'):
        if not module.name.startswith(('test_','stage_','verify_')):shutil.copy2(module,destination/module.name)
    p=folder/'sector_heatmap/web.py';s=p.read_text();reference=(ROOT/'sector_heatmap/web.py').read_text()
    needle="    renko_manifest=ROOT/'.private'/'renko-instances.json'"
    if 'def ai_options_service(' not in s:
        start=reference.index('    # Isolated standalone AI runtime.')
        end=reference.index('    def renko_instance_owners',start)
        # Keep following original lock/registry declarations outside the insertion.
        insert=reference[start:reference.index('    def renko_instance_owners',start)]
        # In root this insert ends immediately before renko_instance_owners.
        assert 'ai_options_services' in insert
        s=replace(s,needle,needle+'\n'+insert,'AI service factory')
    needle='            if path == "/api/renko-supertrend/runner":'
    insert=reference[reference.index("            if path == '/api/renko-supertrend/ai-options/status':"):reference.index(needle)]
    if "if path == '/api/renko-supertrend/ai-options/status':" not in s:s=replace(s,needle,insert+needle,'AI GET')
    needle="actions = {'/api/renko-supertrend/spread-filter':"
    new=reference[reference.index("actions = {'/api/renko-supertrend/ai-options/prepare'"):reference.index(" renko_supertrend.set_spread_filter,",reference.index("actions = {'/api/renko-supertrend/ai-options/prepare'"))]
    if "'/api/renko-supertrend/ai-options/prepare': lambda" not in s:s=replace(s,needle,new,'AI actions')
    p.write_text(s);changed.append('sector_heatmap/web.py')
    p=folder/'strategies/renko_supertrend/runner.py';s=p.read_text()
    needle="    def preview(self,payload):\n        self.validate_binding(payload)"
    new="    def preview(self,payload):\n        if payload.get('strategy_mode')=='AI_RENKO_OPTIONS':raise ValueError('AI Renko options use the dedicated standalone runtime; legacy runner fallback is forbidden.')\n        self.validate_binding(payload)"
    s=replace(s,needle,new,'no legacy fallback');p.write_text(s);changed.append('strategies/renko_supertrend/runner.py')
    return changed
for folder in sorted((ROOT/'.private/dashboard-login/accounts').glob('*/source')):
    try:changes.append(dict(account=folder.parent.name,files=run(folder),status='STAGED'))
    except Exception as error:changes.append(dict(account=folder.parent.name,status='INCOMPLETE',error=str(error)))
(ROOT/'strategies/nifty_ai_options/evidence/source-staging.json').write_text(json.dumps(changes,indent=2))
print(json.dumps(changes,indent=2))
