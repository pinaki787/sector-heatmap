from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HELPERS=r'''  function strategyEntryCheck(config,signal,direction){
    const c=effectiveFamilySettings(config||{}),s=signal||{},fail=reason=>({allowed:false,reason,revision:'strategy-qualified-replay-v1'}),num=v=>typeof v==='number'&&Number.isFinite(v),bull=direction==='BULLISH',beyond=(a,b)=>num(a)&&num(b)&&(bull?a>b:a<b);
    if(!['BULLISH','BEARISH'].includes(direction)||s.entry_qualified!==true)return fail('WAITING_SELECTED_STRATEGY');
    if(s.provisional||s.is_forming)return fail('WAITING_COMPLETED_OBSERVATION');
    if(!num(s.close))return fail('MISSING_CLOSE');
    if(c.strategy_basis==='RENKO'){
      if(!s.has_completed_brick||!beyond(s.close,s.open)||s.brick_direction!==direction)return fail('WAITING_MATCHING_RENKO_BRICK');
      if(Object.hasOwn(c,'swing_breakout_bricks')){const g=s.swing_breakout?.sides?.[direction];if(!g?.allowed||g.required!==Number(c.swing_breakout_bricks)||g.count<Number(c.swing_breakout_bricks))return fail('WAITING_SWING_BREAKOUT_CLOSES');}
    }
    if(c.supertrend_enabled&&s.pine_direction!==(bull?-1:1))return fail('WAITING_SUPERTREND_DIRECTION');
    if(c.supertrend_slope_enabled){const g=s.supertrend_slope_filter;if(!g?.allowed||g.lookback!==Number(c.supertrend_slope_bars??1)||!beyond(g.slope_atr,bull?Number(c.supertrend_slope_min_atr??0):-Number(c.supertrend_slope_min_atr??0)))return fail('WAITING_SUPERTREND_SLOPE');}
    for(const [flag,key] of [['ema_fast_enabled','ema10'],['ema_slow_enabled','ema30'],['ema_third_enabled','ema100']])if(c[flag]&&!beyond(s.close,s[key]))return fail('WAITING_'+key.toUpperCase());
    if(c.ema_fast_enabled&&c.ema_slow_enabled&&!beyond(s.ema10,s.ema30))return fail('WAITING_EMA_ORDER');
    const prior=c.ema_slow_enabled?s.ema30:c.ema_fast_enabled?s.ema10:null;
    if(c.ema_third_enabled&&(c.ema_fast_enabled||c.ema_slow_enabled)&&!beyond(prior,s.ema100))return fail('WAITING_EMA_THIRD_ORDER');
    if(c.ema_widening_enabled&&s.ema_widening!==true)return fail('WAITING_EMA_WIDENING');
    if(c.use_adx&&(!num(s.adx)||s.adx<Number(c.adx_threshold??20)))return fail('WAITING_ADX');
    if(c.rsi_slope_enabled&&s.rsi_slope_pass!==true)return fail('WAITING_RSI_SLOPE');
    if(c.rsi_level_enabled){const r=s.rsi14,mode=c.rsi_level_mode||'THRESHOLD';if(!num(r)||(mode==='BETWEEN'?!((bull?Number(c.rsi_bullish_min):Number(c.rsi_bearish_min))<=r&&r<=(bull?Number(c.rsi_bullish_max):Number(c.rsi_bearish_max))):!(bull?r>Number(c.rsi_bullish_above):r<Number(c.rsi_bearish_below))))return fail('WAITING_RSI_LEVEL');}
    for(const [flag,key] of [['anti_chop_enabled','anti_chop'],['manual_trend_enabled','manual_trend'],['calibrated_enabled','calibrated_filter'],['zone_entry_enabled','zone_entry_filter'],['market_structure_enabled','market_structure'],['higher_timeframe_enabled','mtf_supertrend'],['line_entry_enabled','line_entry_filter']])if(c[flag]&&!s[key]?.allowed)return fail('WAITING_'+key.toUpperCase());
    if(c.ema_proximity_enabled&&!s.ema_proximity?.allowed)return fail('WAITING_EMA_PROXIMITY');
    if(c.ema_momentum_enabled&&!s.ema_momentum?.allowed)return fail('WAITING_EMA_MOMENTUM');
    if([1,2,3].some(slot=>c['rsi_htf_'+slot+'_enabled'])&&!s.mtf_rsi?.allowed)return fail('WAITING_MTF_RSI');
    return {allowed:true,reason:'ALL_SELECTED_STRATEGY_RULES_PASS',revision:'strategy-qualified-replay-v1'};
  }
  function chartReplayAudit(data,parity,config=data.entry_settings||data.settings||{}){
    if(!chartAnalysisAvailable(data)||parity?.blocked)return {events:[],rejected:[],unpairedExits:0};
    const source=data.strategy_replay||data,events=[],rejected=[];let held=null,unpairedExits=0;
    for(const row of source.rows||[]){
      const bricks=row.strategy_basis==='RENKO'?(row.brick_events||[]):[row];
      for(const brick of bricks){
        const event=brick.lifecycle_event;if(!event)continue;
        const renko=row.strategy_basis==='RENKO',sig={...brick,...(renko?{has_completed_brick:true}:{}),source_timestamp:row.timestamp,lifecycle_event_at:Math.floor(brick.lifecycle_event_at??row.timestamp+60)};
        const side=event.startsWith('BUY')?'BULLISH':'BEARISH';
        if(event==='BUY'||event==='SELL'){
          const verdict=strategyEntryCheck(config,sig,side);
          if(held||!verdict.allowed){rejected.push({timestamp:sig.timestamp,event,reason:held?'SIMULATED_POSITION_ALREADY_OPEN':verdict.reason});continue;}
          held=side;sig.strategy_entry_check=verdict;
        }else{
          if(held!==side){unpairedExits++;continue;}
          held=null;sig.strategy_entry_check={allowed:true,reason:'PAIRED_ELIGIBLE_SIMULATED_TRADE',revision:'strategy-qualified-replay-v1'};
        }
        events.push({...sig,event_scope:'SIMULATION'});
      }
    }
    return {events,rejected,unpairedExits,unavailable:source.unavailable||null};
  }
  function chartHistoricalEvents(data,parity,config){return chartReplayAudit(data,parity,config).events;}
  function chartEntrySettings(fields,state,source='live'){
    if(source==='runner'&&state?.config)return {...state.config,chart_entry_guards:true,chart_zone_target_enabled:state.config.zone_target_enabled===true};
    const result=signalSettings(fields);
    for(const [family,ids] of Object.entries(FAMILY_RULES))if(fields[family+'-family-enabled']===false)for(const id of ids)result[id.replaceAll('-','_')]=false;
    result.ema_exit_enabled=fields['ema-exit-enabled']===true;result.ema_exit_length=Number(fields['ema-exit-length']??10);
    result.ema_proximity_enabled=fields['ema-proximity-enabled']===true;result.ema_momentum_enabled=fields['ema-momentum-enabled']===true;
    result.chart_entry_guards=true;result.chart_zone_target_enabled=result.zone_target_enabled===true;
    result.trend_reentry_enabled=fields['trend-reentry-enabled']!==false;
    return effectiveFamilySettings(result);
  }
  function replayQuerySettings(config){
    const result={...config};
    // Existing chart APIs parse these two switches only as defaults. They govern
    // filtering below; do not send a string to an older boolean-only parser.
    delete result.trend_reentry_enabled;delete result.spread_filter_enabled;
    for(const key of Object.keys(result))if(result[key]===null||typeof result[key]==='object'||key.endsWith('_indicator'))delete result[key];
    return result;
  }
'''
for source in [ROOT,*ROOT.glob('.private/dashboard-login/accounts/*/source')]:
 p=source/'renko-supertrend.js';s=p.read_text();backup=ROOT/'.private/chart-qualified-replay-source-backup-20261103'/('main' if source==ROOT else source.parent.name);backup.mkdir(parents=True,exist_ok=True)
 if not (backup/'renko-supertrend.js').exists():(backup/'renko-supertrend.js').write_text(s)
 start=s.index('  function chartHistoricalEvents(');end=s.index('\n  function sharedRunnerCharts',start);s=s[:start]+HELPERS+'\n'+s[end:]
 # Chart studies retain chart-only selections. A separate read-only calculation
 # supplies strategy markers whenever entry/exit settings differ.
 anchor="const chartSymbol=pageParams.get('renkoSymbol');" # no change; explicit load patch below.
 needle="const events=chartHistoricalEvents(d,chartParity);"
 replacement="""const entrySettings=chartEntrySettings(values(),lastRunner,chartBasisSource);d.entry_settings=entrySettings;
        if(chartBasisSource!=='runner'){
          const replaySettings=replayQuerySettings(entrySettings),compare=effectiveFamilySettings(d.settings||{});
          const differs=Object.keys(replaySettings).some(k=>Object.hasOwn(compare,k)&&String(compare[k])!==String(replaySettings[k]));
          if(differs){try{d.strategy_replay=await request('chart?'+new URLSearchParams({...query,...replaySettings}));if(seq!==version)return;}catch(error){d.strategy_replay={rows:[],unavailable:'Strategy replay unavailable: '+error.message};}}
        }
        const replayAudit=chartReplayAudit(d,chartParity,entrySettings),events=replayAudit.events;"""
 assert needle in s;s=s.replace(needle,replacement)
 s=s.replace("text:c.lifecycle_event}));if(d.intrabar_entries", "text:'SIM '+c.lifecycle_event}));if(d.intrabar_entries")
 # Forming observations never receive BUY/SELL signal labels.
 start=s.index("if(d.intrabar_entries&&provisional?.entry_direction&&view==='host'&&!last.projected_position)markers.push(")
 end=s.index(';const swing=last?.swing_breakout;',start);s=s[:start]+s[end+1:]
 s=s.replace("historicalMarkers=markers;paintMarkers();", "el('signal-range').textContent+=' · SIM labels require every selected Strategy rule; exits require a paired simulated entry. '+(replayAudit.unavailable||'Filtered entries: '+replayAudit.rejected.length+' · unpaired exits: '+replayAudit.unpairedExits+'.')+' Actual fills use FILL labels; broker freshness, ownership, quota and locks are verified only by the runner.';historicalMarkers=markers;paintMarkers();")
 s=s.replace("stamp(c.lifecycle_event_at??c.timestamp),c.lifecycle_event,price(c.close)", "stamp(c.lifecycle_event_at??c.timestamp),'SIM '+c.lifecycle_event,price(c.close)")
 # Keep actual ledger fills visibly distinct; only an owned filled entry can
 # establish an execution exit. No signal assessment is treated as a fill.
 s=s.replace("const direction=entry?.indicator_snapshot", "if(row.is_entry!==true&&entry?.status!=='FILLED')continue;\n      const direction=entry?.indicator_snapshot")
 s=s.replace("size:1,text:(bullish?'BUY':'SELL')", "size:1,text:'FILL '+(bullish?'BUY':'SELL')")
 s=s.replace("let markers=historicalMarkers;if(chart.uniformRenkoRows)", "let markers=executionMarkers(historicalMarkers,lastRunner,el('symbol').value,el('timeframe').value);if(chart.uniformRenkoRows)")
 # Add an explicit persistent legend immediately above the chart.
 s=s.replace("<p id=\"renko-swing-levels\"", "<p id=\"renko-swing-levels\"")
 s=s.replace("if(!el('brick-preview-status')){", "if(!el('signal-label-legend')){const legend=document.createElement('p');legend.id='renko-signal-label-legend';legend.className='muted';legend.textContent='SIM BUY / SELL: historical strategy simulation after all selected entry checks. SIM EXIT: closes its paired simulated trade. FILL: confirmed owned order ledger. Forming bricks do not generate signal labels.';el('chart').before(legend);}\n      if(!el('brick-preview-status')){")
 s=s.replace('module.exports={chartSourceContext,','module.exports={strategyEntryCheck,chartReplayAudit,chartEntrySettings,replayQuerySettings,chartSourceContext,')
 p.write_text(s)
print('Updated main and seven hosted UI sources')
