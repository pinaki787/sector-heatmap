from pathlib import Path
root=Path.cwd()
def edit(name,changes):
 p=root/name;s=p.read_text()
 for old,new in changes:
  assert s.count(old)==1,(name,old[:90],s.count(old));s=s.replace(old,new,1)
 p.write_text(s)
edit('strategies/renko_supertrend/confirmed_feed.py',[
("""            if not self.members:
                # Provider SDK close may join callbacks. Never join in Stop.
                threading.Thread(target=self.transport.stop,daemon=True,name='renko-shared-feed-close').start()""","""            # Account transport stays alive for charts and later consumers.
            # Runner Stop must never tear down another consumer's data feed."""),
("""        return exported
    finally:""","""        exported['_engine'] = deepcopy({k:state['renko_engine'][k] for k in ('state','last','anchor')})
        exported['_config'] = deepcopy(config)
        return exported
    finally:""")
])
edit('sector_heatmap/web.py',[
("""                        analyzed = {**analyzed,'anchor':confirmed_source['anchor'],'last':rows[-1]}""","""                        analyzed = confirmed_source.pop('_engine')
                        config = confirmed_source.pop('_config')"""),
("""                    if intrabar_enabled and analysis_available:""","""                    if (intrabar_enabled or requested_run) and analysis_available:"""),
("""                    with renko_display_lock:
                        context_key=json.dumps([{'underlying':symbol,'timeframe':timeframe},display_settings],sort_keys=True)""","""                    with renko_display_lock:
                        context_key=json.dumps([{'underlying':symbol,'timeframe':timeframe},display_settings],sort_keys=True)""")
])
# Last replacement is intentionally a structural assertion of the stream key.
edit('strategies/renko_supertrend/stream.py',[
("""    return {**browser_snapshot(runner,now),'forming':forming,'market':{'connected':broker.connected,""","""    snapshot = browser_snapshot(runner,now)
    confirmed = (snapshot.get('runner') or {}).get('confirmed_indicators')
    candle_health = {}
    fetcher = getattr(broker, 'fetch_candles', None)
    if fetcher and getattr(fetcher, '_renko_shared_pipeline', False):
        from .confirmed_feed import feed_for
        candle_health = feed_for(fetcher).health((config['underlying'],config['timeframe']))
    session = {'status':'UNKNOWN'}
    if tick_at is None and hasattr(broker,'session_policy'):
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            policy = broker.session_policy(config)
            regular = policy.get('master_regular_session','')
            opening,closing = regular.split('-')
            local = datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata'))
            current = local.strftime('%H%M')
            if local.weekday() >= 5 or not opening <= current < closing:
                session = {'status':'OUTSIDE_REGULAR_SESSION','regular_hours':regular}
        except (ValueError,AttributeError,KeyError,TypeError):
            pass
    return {**snapshot,'confirmed_indicators':confirmed,'candles':candle_health,
            'forming':forming,'market':{'connected':broker.connected,'session':session,""")
])
edit('renko-supertrend.js',[
("""    settings.chart_entry_guards=true;settings.chart_zone_target_enabled=!!c.zone_target_enabled;""","""    settings.chart_entry_guards=true;settings.chart_zone_target_enabled=!!c.zone_target_enabled;
    settings.confirmed_run_id=state.run_id;"""),
("""    const signal=state.last_signal,reference=data.rows?.find(r=>r.timestamp===signal?.timestamp);""","""    const signal=state.confirmed_indicators?.latest||state.last_signal,reference=data.rows?.find(r=>r.timestamp===signal?.timestamp);
    if(data.confirmed_source&&(data.confirmed_source.run_id!==context.runId||data.confirmed_source.timeframe!==context.settings.timeframe))
      return {verified:false,blocked:true,reason:'Confirmed indicator identity changed; previous chart retained.'};"""),
("""    const closed=data.market?.session?.status==='CLOSED'||data.market?.status==='CLOSED';""","""    const closed=['CLOSED','OUTSIDE_REGULAR_SESSION'].includes(data.market?.session?.status)||data.market?.status==='CLOSED';"""),
("""const label=health.chartFresh?""","""const label=health.chartFresh?"""), # guard
("""'Ticks live · candle delayed'""","""'Live prices · candle recovering'"""),
("""    function boundChartContext(){""","""    function liveChartEnabled(){return boundChartContext().basis!=='draft'||el('history-preset').value!=='custom';}
    function boundChartContext(){"""),
("""chart,candles,volumeSeries,line,fiveMinuteLine""","""chart,candles,volumeSeries,line,liveSupertrendLine,fiveMinuteLine"""),
("""line=chart.addLineSeries({lineWidth:2,priceLineVisible:false,title:'1-minute Supertrend'});""","""line=chart.addLineSeries({lineWidth:2,priceLineVisible:false,title:'1-minute Supertrend'});liveSupertrendLine=chart.addLineSeries({color:'#f2c14e',lineWidth:2,lineStyle:2,priceLineVisible:false,title:'Provisional Supertrend · no entry authority'});"""),
("""        const plottedAnalysis=provisional&&view==='host'?[...analysisRows,provisional]:analysisRows;""","""        const plottedAnalysis=boundChartContext().basis!=='draft'?analysisRows:provisional&&view==='host'?[...analysisRows,provisional]:analysisRows;
        liveSupertrendLine?.setData([]);"""),
("""    let chartBasisPreview=false,chartBasisKey='',chartParity=null;""","""    let chartBasisPreview=false,chartBasisKey='',chartParity=null,confirmedRevision=null;"""),
("""if(d.adopted_managers)managerTable(d.adopted_managers);""","""if(d.adopted_managers)managerTable(d.adopted_managers);
      const confirmed=d.confirmed_indicators;
      if(confirmed&&confirmed.run_id===boundChartContext().runId&&confirmed.revision!==confirmedRevision){const previous=confirmedRevision;confirmedRevision=confirmed.revision;if(previous&&!busy)load();}
      if(d.display_analysis&&d.market?.fresh&&chartParity?.verified&&boundChartContext().basis!=='draft'&&liveSupertrendLine){
        const preview=d.display_analysis,base=confirmed?.latest;
        if(base&&preview.timestamp>base.timestamp&&Number.isFinite(preview.supertrend)){
          liveSupertrendLine.setData([{time:base.timestamp,value:base.supertrend},{time:preview.timestamp,value:preview.supertrend}]);
          liveSupertrendLine.applyOptions({visible:el('supertrend-enabled-indicator').checked});
          el('provisional-status').textContent='Live provisional Supertrend '+price(preview.supertrend)+' · confirmed strategy unchanged';
        }
      }else if(liveSupertrendLine&&!d.market?.fresh)liveSupertrendLine.setData([]);
      """),
])
p=root/'renko-supertrend.js';s=p.read_text()
# Bound runner charts use a fixed initialization range, but still need live ticks.
s=s.replace("el('history-preset').value!=='custom'","liveChartEnabled()")
s=s.replace("function liveChartEnabled(){return boundChartContext().basis!=='draft'||liveChartEnabled();}","function liveChartEnabled(){return boundChartContext().basis!=='draft'||el('history-preset').value!=='custom';}")
p.write_text(s)
print('Shared confirmed source and separate live preview wired.')
