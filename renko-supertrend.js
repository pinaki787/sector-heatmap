/* Supplied PRST calculations come from the Python engine; no RSI relabeling. */
(function(root) {
  function chartSelectionForInstrument(symbol, selected){return selected.length>1?selected:(symbol?[symbol]:[]);}

  function configurationComparisonRows(id,saved,current){
    const parse=value=>{try{return typeof value==='string'?JSON.parse(value):value;}catch{return value;}};
    const format=(key,value)=>value==null||value===''?'—':key.endsWith('_at')&&Number.isFinite(Number(value))?new Date(Number(value)*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':typeof value==='boolean'?(value?'On':'Off'):typeof value==='number'?(Number.isInteger(value)?String(value):value.toFixed(2)):typeof value==='object'?Object.entries(value).map(([k,v])=>k.replaceAll('_',' ')+': '+(typeof v==='object'?JSON.stringify(v):v)).join('\n'):String(value);
    if(id!=='manual-brick-reference')return [{label:id.replaceAll('-',' '),saved:format(id,saved),current:format(id,current)}];
    const a=parse(saved)||{},b=parse(current)||{};
    return [['symbol','Reference contract'],['manual_brick','Calculated brick size'],['reference_atr','Reference ATR'],['reference_bars','Completed reference bars'],['reference_last_at','Last reference candle'],['calculated_at','Calculated at'],['source_resolution','Source resolution'],['source_basis','Source basis'],['source','Data source'],['rule','Calculation rule'],['session_policy','Trading session'],['revision','Calculation version']].filter(([key])=>a[key]!=null||b[key]!=null).map(([key,label])=>({label,saved:format(key,a[key]),current:format(key,b[key])}));
  }
  function mergeChartRows(data,previous=[]){
    if(!data.incremental)return data;
    const rows=new Map(previous.map(row=>[row.timestamp,row]));
    for(const row of data.rows||[])rows.set(row.timestamp,row);
    return {...data,rows:[...rows.values()].sort((a,b)=>a.timestamp-b.timestamp)};
  }
  function chartHistoricalEvents(data,parity){
    return chartAnalysisAvailable(data)&&!parity?.blocked?(data.rows||[]).flatMap(row=>row.strategy_basis==='RENKO'?(row.brick_events||[]).filter(b=>b.lifecycle_event).map(b=>({...b,source_timestamp:row.timestamp,lifecycle_event_at:Math.floor(b.lifecycle_event_at??row.timestamp+60)})):row.lifecycle_event?[row]:[]):[];
  }

  function runnerChartContext(fields,state,preview=false,now=Date.now()){
    const draft=chartSettings(fields),c=state?.config;
    const bound=!preview&&!!(state?.running||state?.position||state?.pending)&&c?.underlying===fields.symbol&&c?.timeframe===fields.timeframe&&!!state?.run_id;
    if(!bound)return {basis:'draft',settings:draft,history:{},differences:[],label:'SELECTED INSTRUMENT · live chart · form settings; no trading change'};
    const settings={...draft,strategy_basis:c.strategy_basis||'LEGACY',renko_brick_exit_enabled:c.renko_brick_exit_enabled===true};
    // A recorded legacy runner never acquires a newly defaulted entry rule.
    if(!Object.hasOwn(c,'ema_third_enabled'))settings.ema_third_enabled=false;
    for(const key of Object.keys(draft))if(Object.hasOwn(c,key))settings[key]=c[key]??'';
    // Execution choices govern calculations; visual destination toggles only hide/show series.
    for(const key of DESTINATION_RULES.map(id=>id.replaceAll('-','_')))if(Object.hasOwn(c,key))settings[key]=c[key];
    settings.chart_entry_guards=true;settings.chart_zone_target_enabled=!!c.zone_target_enabled;
    settings.confirmed_run_id=state.confirmed_feed_revision==='shared-confirmed-live-v1'?state.run_id:'';
    settings.symbol=c.underlying;settings.timeframe=c.timeframe;
    for(const key of ['commodity_holding','execution_route','session_deadline','carry_policy','fyers_history_enabled','fyers_history_account_id'])
      if(c[key]!=null)settings[key]=c[key];
    const requested={...signalSettings(fields),symbol:fields.symbol,timeframe:fields.timeframe};
    const differences=Object.keys(requested).filter(k=>!k.endsWith('_indicator')&&Object.hasOwn(settings,k)&&String(requested[k])!==String(settings[k]));
    const anchor=state.initialization_anchor;
    let history={},error=null;
    if(Number.isFinite(anchor)){
      const first=new Date(anchor*1000+19800000+7*86400000).toISOString().slice(0,10),last=new Date(now+19800000).toISOString().slice(0,10);
      const span=(Date.parse(last)-Date.parse(first))/86400000;
      if(first>last||span>90)error='Runner history anchor cannot be reproduced within this chart range. Use draft preview for separate research.';
      else history={history_preset:'custom',history_from:first,history_to:last};
    }else error='Runner history anchor unavailable; matching calculations cannot be verified.';
    if(settings.confirmed_run_id){history={};error=null;}
    const basis='active';
    return {basis,settings,history,differences,error,runId:state.run_id,anchor,label:(basis==='active'?'ACTIVE RUNNER':'LAST RUN · STOPPED')+' · '+c.timeframe+' · brick '+(state.confirmed_indicators?.latest?.box??state.last_signal?.box??c.manual_brick)+(differences.length?' · draft differs; not applied':(c.renko_confirmation==='PRICE'?' · price-confirmed bricks · timeframe sizes Auto':' · captured Start settings'))};
  }
  function runnerChartAlignment(context,state,data){
    if(context.basis==='draft')return {verified:false,blocked:false,reason:'Draft preview; historical signals are not runner decisions.'};
    if(context.runId!==state?.run_id)return {verified:false,blocked:true,reason:'Runner changed while chart loaded; refreshing its settings.'};
    if(context.error)return {verified:false,blocked:true,reason:context.error};
    if(data.initialization_anchor!==context.anchor)return {verified:false,blocked:true,reason:'Chart history anchor differs from the runner; derived signals withheld.'};
    const signal=state.confirmed_indicators?.latest||state.last_signal,reference=data.rows?.find(r=>r.timestamp===signal?.timestamp);
    if(data.confirmed_source&&(data.confirmed_source.run_id!==context.runId||data.confirmed_source.timeframe!==context.settings.timeframe))
      return {verified:false,blocked:true,reason:'Confirmed indicator identity changed; previous chart retained.'};
    if(!signal||!reference)return {verified:false,blocked:true,reason:'Recorded runner candle unavailable in chart; agreement is unconfirmed.'};
    for(const key of ['direction','supertrend','ema10','ema30',...(context.settings?.ema_third_enabled?['ema100']:[])]){
      const a=signal[key],b=reference[key];
      if(typeof a==='number'?(!Number.isFinite(b)||Math.abs(a-b)>Math.max(1e-7,Math.abs(a)*1e-10)):a!==b)
        return {verified:false,blocked:true,reason:'Chart and recorded runner '+key.replaceAll('_',' ')+' disagree; derived signals withheld.'};
    }
    return {verified:true,blocked:false,reason:'Verified against the recorded runner candle: direction, Supertrend and EMA values agree.'};
  }

  const STRATEGY='RENKO_SUPERTREND_V1';
  const RSI_HTF_SLOTS=[1,2,3],RSI_HTF_FRAMES=['15 minutes','30 minutes','1 hour'];
  const RSI_HTF_LEVELS={'level-mode':'BETWEEN','bullish-min':60,'bullish-max':80,'bearish-min':35,'bearish-max':40,'bullish-above':50,'bearish-below':40};
  const RSI_HTF_IDS=RSI_HTF_SLOTS.flatMap(i=>['enabled','timeframe',...Object.keys(RSI_HTF_LEVELS)].map(k=>'rsi-htf-'+i+'-'+k));
  function inheritRsiHtfFields(fields){const next={...fields};for(const i of RSI_HTF_SLOTS)for(const [key,fallback] of Object.entries(RSI_HTF_LEVELS)){const id='rsi-htf-'+i+'-'+key;if(next[id]==null||next[id]==='')next[id]=fields['rsi-'+key]??fallback;}return next;}
  function rsiHtfSettings(fields){const inherited=inheritRsiHtfFields(fields);return Object.fromEntries(RSI_HTF_SLOTS.flatMap((i,index)=>[['rsi_htf_'+i+'_enabled',fields['rsi-htf-'+i+'-enabled']===true&&fields['rsi-family-enabled']!==false],['rsi_htf_'+i+'_timeframe',fields['rsi-htf-'+i+'-timeframe']||RSI_HTF_FRAMES[index]],...Object.keys(RSI_HTF_LEVELS).map(k=>['rsi_htf_'+i+'_'+k.replaceAll('-','_'),k==='level-mode'?inherited['rsi-htf-'+i+'-'+k]:Number(inherited['rsi-htf-'+i+'-'+k])])]));}
  function requireRsiHtfSupport(config,snapshot){if(config.anti_chop_enabled&&snapshot?.anti_chop_revision!=='host-timeframe-anti-chop-v4-combination')throw Error('Anti-chop filter requires backend activation before Save or Start.');if(config.zone_entry_enabled&&snapshot?.zone_entry_revision!=='opposing-zone-entry-v1')throw Error('Supply/demand entry filter activation required before Start.');if(config.calibrated_enabled&&snapshot?.calibrated_profile_revision!=='overlap-atr-profile-v1')throw Error('Calibrated profile backend activation required before Start.');if(config.ema_policy_profile==='all-broker-flexible-atr-v1'&&snapshot?.entry_atr_policy_revision!=='all-broker-flexible-atr-v1')throw Error('Flexible ATR backend activation required before Start.');if(config.ema_third_enabled&&config.ema_family_enabled!==false&&snapshot?.ema_third_revision!=='third-ema-entry-v1')throw Error('Third EMA activation is required before Start.');if(config.ema_momentum_enabled&&snapshot?.entry_momentum_revision!=='split-proximity-momentum-v1')throw Error('Momentum backend activation required before Start.');if(RSI_HTF_SLOTS.some(i=>config['rsi_htf_'+i+'_enabled'])&&snapshot?.mtf_rsi_revision!=='optional-three-htf-rsi-v2')throw Error('Higher-timeframe RSI backend update required before Start.');return config;}
  function rsiHtfSummary(gate){if(!gate?.enabled)return 'Higher-timeframe RSI OFF / not assessed.';return 'Assessed '+new Date(gate.observed_at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST · '+gate.slots.map(slot=>'HTF '+slot.slot+' · '+slot.timeframe+' · RSI '+(Number.isFinite(slot.rsi)?slot.rsi.toFixed(2):'Unavailable')+' · '+(slot.levels?(slot.levels.rsi_level_mode==='BETWEEN'?'Bull '+slot.levels.rsi_bullish_min+'–'+slot.levels.rsi_bullish_max+' / Bear '+slot.levels.rsi_bearish_min+'–'+slot.levels.rsi_bearish_max:'Bull > '+slot.levels.rsi_bullish_above+' / Bear < '+slot.levels.rsi_bearish_below)+' · ':'')+slot.reason+' · closed '+(slot.closed_at?new Date(slot.closed_at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}):'Unavailable')+' IST · '+(slot.fresh?'completed / fresh at assessment':'missing or stale')).join(' | ');}


  async function stopAllRenko(fetcher,timeoutMs=15000){
    const bounded=async(url,options={})=>{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs);try{return await fetcher(url,{...options,signal:controller.signal});}catch(e){if(controller.signal.aborted)throw Error('Request timed out; stop or closure is not confirmed. Refresh status before retrying.');throw e;}finally{clearTimeout(timer);}};
    const post=async(url)=>{const r=await bounded(url,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const d=await r.json();if(!r.ok)throw Error(d.error||'Stop request failed');return d;};
    const results=[];
    // Stop the producer first so new Telegram recommendations cannot restart a runner.
    try{await post('/api/telegram/paper-stop');}catch(e){results.push({instrument:'Telegram Paper entries',status:'FAILED',error:e.message});}
    const response=await bounded('/api/renko-instances'),data=await response.json();
    if(!response.ok)throw Error(data.error||'Could not load runners');
    for(const v of data.instances||[]){
      if(!['FYERS','DELTA_INDIA'].includes(v.broker)||!(v.running||v.position||v.pending))continue;
      const instrument=v.instrument||v.config?.underlying||v.broker;
      try{const d=await post((v.broker==='DELTA_INDIA'?'/api/renko-delta/':'/api/renko-supertrend/')+'stop?instance='+encodeURIComponent(v.instance_key||'default'));results.push({instrument,status:d.running||d.position||d.pending?'CLOSING / RECONCILIATION PENDING':'STOPPED'});}
      catch(e){results.push({instrument,status:'FAILED',error:e.message});}
    }
    return results;
  }

  // Existing switches remain execution switches. Chart destinations are independent.
  const DESTINATION_RULES=['rsi-level-enabled','supertrend-enabled','ema-fast-enabled','ema-slow-enabled','ema-third-enabled','ema-widening-enabled','rsi-slope-enabled','use-adx','supertrend-exit-enabled','ema-exit-enabled','ema-slow-exit-enabled','rsi-exit-enabled','ema-widening-exit-enabled','adx-exit-enabled','market-structure-exit-enabled','zone-target-enabled','market-structure-enabled','higher-timeframe-enabled','ema-proximity-enabled','ema-momentum-enabled','retest-enabled'];
  const RULE_DEFAULTS={'higher-timeframe-enabled':false,'supertrend-enabled':true,'ema-fast-enabled':true,'ema-slow-enabled':true,'ema-third-enabled':true,'ema-widening-enabled':true,'rsi-slope-enabled':true,'supertrend-exit-enabled':true};
  function migrateAtrProfile(fields={}){
    if(fields['ema-policy-profile']==='all-broker-flexible-atr-v1')return {...fields};
    return {...fields,'ema-policy-profile':'all-broker-flexible-atr-v1','ema-momentum-enabled':true,'ema-proximity-enabled':true,'ema-proximity-mode':'ATR','ema-proximity-distance':'0.5','intrabar-entries':false};
  }
  function migrateDestinations(fields){fields=migrateAtrProfile(fields);const result={'supertrend-slope-enabled':false,'supertrend-slope-bars':1,'supertrend-slope-min-atr':0,'ema-third-enabled':true,'ema-third-length':100,...fields};for(const id of DESTINATION_RULES)if(!Object.hasOwn(result,id+'-indicator'))result[id+'-indicator']=Object.hasOwn(result,id)?result[id]===true:RULE_DEFAULTS[id]===true;return result;}
  function chartSettings(fields){const result=signalSettings(fields);if(Object.hasOwn(fields,'fyers-history-enabled')){result.fyers_history_enabled=fields['fyers-history-enabled']===true;result.fyers_history_account_id=fields['fyers-history-account-id']||'';}for(const id of DESTINATION_RULES){const key=id.replaceAll('-','_');result[key]=migrateDestinations(fields)[id+'-indicator'];delete result[key+'_indicator'];}for(const [name,ids] of Object.entries(FAMILY_RULES)){if(fields[name+'-family-enabled']===false)for(const id of ids)result[id.replaceAll('-','_')]=false;delete result[name+'_family_enabled'];}if(fields['ema-family-enabled']===false||fields['supertrend-family-enabled']===false)result.retest_enabled=false;result.chart_zone_target_enabled=result.zone_target_enabled;result.chart_entry_guards=true;return result;}

  const FAMILY_RULES={
    supertrend:['supertrend-slope-enabled','supertrend-continuation-enabled','supertrend-enabled','supertrend-exit-enabled','higher-timeframe-enabled'],
    ema:['ema-fast-enabled','ema-slow-enabled','ema-third-enabled','ema-widening-enabled','ema-proximity-enabled','ema-momentum-enabled','retest-enabled','ema-exit-enabled','ema-slow-exit-enabled','ema-widening-exit-enabled'],
    rsi:['rsi-level-enabled','rsi-slope-enabled','rsi-exit-enabled',...RSI_HTF_SLOTS.map(i=>'rsi-htf-'+i+'-enabled')],
    adx:['use-adx','adx-exit-enabled'],
    structure:['market-structure-enabled','market-structure-exit-enabled'],
    zones:['zone-target-enabled']
  };
  function effectiveChartChoice(fields,id){
    const rule=id.replace(/-indicator$/,'');
    const family=rule==='rsi-sma-enabled'?'rsi':Object.keys(FAMILY_RULES).find(name=>FAMILY_RULES[name].includes(rule));
    return fields[id]===true&&(!family||fields[family+'-family-enabled']!==false);
  }
  function familySettings(values){return Object.fromEntries(Object.keys(FAMILY_RULES).map(name=>[name+'_family_enabled',values[name+'-family-enabled']!==false]));}
  function effectiveFamilySettings(config){
    const result={...config,...(config.indicator_family_choices||{})};
    for(const [name,ids] of Object.entries(FAMILY_RULES))if(config[name+'_family_enabled']===false)for(const id of ids)result[id.replaceAll('-','_')]=false;
    if(config.ema_family_enabled===false||config.supertrend_family_enabled===false)result.retest_enabled=false;
    return result;
  }
  function ownedEntryPrice(state,symbol){
    const p=state?.position;if(!p||!(p.quantity>0)||state.config?.underlying!==symbol)return null;
    const trade=(state.trade_history||[]).find(t=>t.lifecycle_id===p.lifecycle_id&&t.remaining_quantity>0);
    const cash=['CASH_EQUITY','DELTA_PERPETUAL'].includes(state.config?.execution_route)||['CASH_EQUITY','DELTA_PERPETUAL'].includes(trade?.execution_route);
    const value=cash?p.entry_price:trade?.spot_entry;
    if(!Number.isFinite(value)||value<=0)return null;
    return {price:value,title:cash?(p.direction==='BEARISH'?'SELL entry':'BUY entry'):'Underlying at fill · reference',basis:cash?'Confirmed fill':'Observed underlying at fill confirmation'};
  }
  function entryDecisionText(signal,state,symbol){
    const event=[...(state?.execution_signals||[])].reverse().find(e=>e.run_id===state.run_id&&e.timestamp===signal?.timestamp&&e.underlying===symbol);
    return signal?.entry_qualified&&state?.config?.underlying===symbol&&event?.status==='BLOCKED'?'Signal qualified · execution blocked: '+event.reason:signal?.entry_diagnostic;
  }
  function testedNiftyDefaults(fields){
    if(fields.symbol!=='NSE:NIFTY50-INDEX'||fields.timeframe!=='5 minutes')throw Error('Tested defaults require NIFTY 50 five-minute candles.');
    return {...fields,'manual-brick-reference':JSON.stringify({symbol:fields.symbol,manual_brick:27.71,user_override:true,rule:{atr_length:5},revision:'tested-nifty-zone-profile-v1',source:'User-selected tested fixed NIFTY profile'}),'calibrated-enabled':true,'calibrated-overlap-pairs':6,'calibrated-overlap-max':.4,'calibrated-stop-atr':3,'calibrated-target-atr':1.5,
      'zone-entry-enabled':true,'zone-entry-min-atr':1,'zone-entry-rearm':true,'zone-target-enabled':true,'zone-target-enabled-indicator':true,'zones-family-enabled':true,
      'atr-length':5,'factor':3,'brick-mode':'Manual','manual-brick':27.71,'widening-window':2,'ema-fast-length':10,'ema-slow-length':30,'ema-third-length':100,
      'supertrend-family-enabled':true,'ema-family-enabled':true,'rsi-family-enabled':true,'supertrend-enabled':true,'ema-fast-enabled':true,'ema-slow-enabled':true,'ema-third-enabled':true,'ema-widening-enabled':true,
      'rsi-slope-enabled':true,'rsi-length':14,'ema-momentum-enabled':true,'ema-proximity-enabled':true,'ema-proximity-mode':'ATR','ema-proximity-distance':.5,
      'retest-enabled':true,'retest-engulfing':true,'retest-harami':true,'retest-star':true,'supertrend-exit-enabled':true,'ema-slow-exit-enabled':true,'ema-exit-enabled':true,'ema-exit-length':30,
      'sideways-enabled':true,'sideways-max-candles':2,'intrabar-entries':false,'trailing-enabled':false,'spot-stop':'','spot-target':'',
      'manual-trend-enabled':false,'supertrend-continuation-enabled':false,'higher-timeframe-enabled':false,'higher-timeframe-enabled-indicator':false,
      'adx-family-enabled':false,'use-adx':false,'use-adx-indicator':false,'adx-exit-enabled':false,'adx-exit-enabled-indicator':false,
      'structure-family-enabled':false,'market-structure-enabled':false,'market-structure-enabled-indicator':false,'market-structure-exit-enabled':false,'market-structure-exit-enabled-indicator':false,
      'rsi-level-enabled':false,'rsi-level-enabled-indicator':false,'rsi-exit-enabled':false,'rsi-exit-enabled-indicator':false,'rsi-htf-1-enabled':false,'rsi-htf-2-enabled':false,'rsi-htf-3-enabled':false,
      'ema-widening-exit-enabled':false,'ema-widening-exit-enabled-indicator':false};
  }
  const ANTI_CHOP_DEFAULTS={'anti-chop-enabled':false,'anti-chop-combination':'All','anti-chop-role':'Filter','anti-chop-mode':'Adaptive','anti-chop-atr-length':14,'anti-chop-atr-average-length':20,'anti-chop-ema-fast-length':20,'anti-chop-ema-slow-length':50,'anti-chop-adaptive-window':200,'anti-chop-slope-percentile':60,'anti-chop-gap-percentile':60,'anti-chop-overlap-percentile':40,'anti-chop-slope-bars':3,'anti-chop-slope-atr':.15,'anti-chop-gap-atr':.20,'anti-chop-cross-bars':6,'anti-chop-structure-bars':3,'anti-chop-overlap-percent':50};
  const ANTI_CHOP_IDS=Object.keys(ANTI_CHOP_DEFAULTS);
  function antiChopSettings(values){return Object.fromEntries(ANTI_CHOP_IDS.map(id=>[id.replaceAll('-','_'),id==='anti-chop-enabled'?values[id]===true:['anti-chop-mode','anti-chop-role','anti-chop-combination'].includes(id)?(values[id]||ANTI_CHOP_DEFAULTS[id]):Number(values[id]??ANTI_CHOP_DEFAULTS[id])]));}
  function universalStrategyDefaults(fields={}){
    const result={...fields};
    for(const key of Object.keys(result))if(typeof result[key]==='boolean'||key.endsWith('-enabled')||key.endsWith('-indicator'))result[key]=false;
    return {...result,...ANTI_CHOP_DEFAULTS,'strategy-basis':'RENKO','supertrend-slope-enabled':true,'supertrend-slope-bars':1,'supertrend-slope-min-atr':0,'renko-brick-exit-enabled':true,'supertrend-family-enabled':true,'rsi-family-enabled':false,'adx-family-enabled':false,'structure-family-enabled':false,'zones-family-enabled':false,'ema-slow-enabled':false,'ema-slow-enabled-indicator':false,'ema-third-enabled':false,'ema-third-enabled-indicator':false,'ema-widening-enabled':false,'ema-widening-enabled-indicator':false,'ema-slow-exit-enabled':false,'ema-widening-exit-enabled':false,'rsi-slope-enabled':false,'rsi-level-enabled':false,'use-adx':false,'ema-family-enabled':false,'supertrend-enabled':true,'supertrend-enabled-indicator':true,'supertrend-exit-enabled':true,'supertrend-exit-enabled-indicator':true,'ema-fast-enabled':false,'ema-fast-enabled-indicator':false,'ema-fast-length':10,'ema-slow-length':30,'ema-third-length':100,'ema-exit-enabled':false,'ema-exit-enabled-indicator':false,'ema-exit-length':10,'atr-length':5,factor:3,'brick-mode':'Auto','manual-brick-reference':'','intrabar-entries':false,'chart-view':'synthetic',mode:'PAPER',lots:1};
  }
  function signalSettings(values) {
    return {supertrend_slope_enabled:values['supertrend-slope-enabled']===true,supertrend_slope_bars:Number(values['supertrend-slope-bars']??1),supertrend_slope_min_atr:Number(values['supertrend-slope-min-atr']??0),strategy_basis:values['strategy-basis']||'LEGACY',renko_brick_exit_enabled:values['renko-brick-exit-enabled']===true,...antiChopSettings(values),...familySettings(values),...rsiHtfSettings(values),zone_entry_enabled:values['zone-entry-enabled']===true&&values['calibrated-enabled']===true&&values.symbol==='NSE:NIFTY50-INDEX'&&values.timeframe==='5 minutes',zone_entry_min_atr:Number(values['zone-entry-min-atr']??1),zone_entry_rearm:values['zone-entry-rearm']!==false,calibrated_enabled:values['calibrated-enabled']===true&&values.symbol==='NSE:NIFTY50-INDEX'&&values.timeframe==='5 minutes',calibrated_overlap_pairs:Number(values['calibrated-overlap-pairs']||6),calibrated_overlap_max:Number(values['calibrated-overlap-max']??.4),calibrated_stop_atr:Number(values['calibrated-stop-atr']||3),calibrated_target_atr:Number(values['calibrated-target-atr']||1.5),manual_trend_enabled:values['manual-trend-enabled']===true,manual_trend_bullish:!values['manual-trend-bullish']?'':Number(values['manual-trend-bullish']),manual_trend_bearish:!values['manual-trend-bearish']?'':Number(values['manual-trend-bearish']),manual_trend_closes:Number(values['manual-trend-closes']||2),supertrend_continuation_enabled:values['supertrend-continuation-enabled']===true,market_structure_enabled:values['market-structure-enabled']===true,higher_timeframe_enabled:values['higher-timeframe-enabled']===true,supertrend_timeframe:values['supertrend-timeframe']||'5 minutes',ema_policy_profile:values['ema-policy-profile']||'all-broker-flexible-atr-v1',ema_momentum_enabled:values['ema-momentum-enabled']===true,ema_proximity_enabled:values['ema-proximity-enabled']===true,ema_proximity_mode:values['ema-proximity-mode']||'ATR',ema_proximity_distance:Number(values['ema-proximity-distance']||.5),zone_target_enabled:values['zone-target-enabled']===true,...Object.fromEntries(DESTINATION_RULES.map(id=>[id.replaceAll('-','_')+'_indicator',migrateDestinations(values)[id+'-indicator']])),supertrend_exit_enabled:values['supertrend-exit-enabled']!==false,ema_slow_exit_enabled:values['ema-slow-exit-enabled']===true,rsi_exit_enabled:values['rsi-exit-enabled']===true,ema_widening_exit_enabled:values['ema-widening-exit-enabled']===true,adx_exit_enabled:values['adx-exit-enabled']===true,market_structure_exit_enabled:values['market-structure-exit-enabled']===true,atr_length:Number(values['atr-length']),factor:Number(values.factor),brick_mode:values['brick-mode'],manual_brick:Number(values['manual-brick']),
      ema_exit_enabled:values['ema-exit-enabled']===true,ema_exit_length:Number(values['ema-exit-length']||10),use_adx:values['use-adx']===true,adx_threshold:Number(values['adx-threshold']),adx_length:Number(values['adx-length']),adx_smoothing:Number(values['adx-smoothing']),widening_window:Number(values['widening-window']),rsi_level_enabled:values['rsi-level-enabled']===true,rsi_level_mode:values['rsi-level-mode']||'THRESHOLD',rsi_bullish_min:Number(values['rsi-bullish-min']??60),rsi_bullish_max:Number(values['rsi-bullish-max']??80),rsi_bearish_min:Number(values['rsi-bearish-min']??35),rsi_bearish_max:Number(values['rsi-bearish-max']??40),rsi_bullish_above:Number(values['rsi-bullish-above']??50),rsi_bearish_below:Number(values['rsi-bearish-below']??40),rsi_slope_enabled:values['rsi-slope-enabled']===true,supertrend_enabled:values['supertrend-enabled']!==false,ema_fast_enabled:values['ema-fast-enabled']!==false,ema_slow_enabled:values['ema-slow-enabled']!==false,ema_third_enabled:values['ema-third-enabled']!==false,ema_widening_enabled:values['ema-widening-enabled']!==false,ema_fast_length:Number(values['ema-fast-length']||10),ema_slow_length:Number(values['ema-slow-length']||30),ema_third_length:Number(values['ema-third-length']??100),rsi_slope_length:Number(values['rsi-length']||14),intrabar_entries:values['intrabar-entries']===true,retest_enabled:values['retest-enabled']===true,retest_engulfing:values['retest-engulfing']===true,retest_harami:values['retest-harami']===true,retest_star:values['retest-star']===true};
  }
  function configurationText({broker,instance,fields,requested,active,revision,savedAt,now=new Date()}){
    const date=new Date(now),ist=new Date(date.getTime()+19800000).toISOString().slice(0,19).replace('T',' ');
    const allowed=new Set(Object.keys(requested).concat(['session_segment','session_exchange','session_open','requested_deadline','session_source','master_regular_session']));
    const clean=source=>Object.fromEntries(Object.entries(source||{}).filter(([k,v])=>allowed.has(k)&&v!==undefined&&(v===null||['string','number','boolean'].includes(typeof v))));
    const body={schema_version:1,strategy:requested.strategy||STRATEGY,exported_at:date.toISOString(),timezone:'Asia/Kolkata',broker,instance,
      runtime_revision:revision||null,preferences_saved_at:savedAt||null,draft_fields:fields,
      requested_start_configuration:clean(requested),active_runner_configuration:active?clean(active):null};
    const lines=['Sector Pulse — Renko configuration',`Exported: ${ist} IST (Asia/Kolkata)`,
      `Broker: ${broker} · Instance: ${instance}`,`Strategy: ${requested.strategy||STRATEGY} · Export schema: 1`,
      'DRAFT: visible settings, including unsaved edits. Editing or saving does not apply them to an active runner.',
      'ACTIVE: separately recorded below from the last runner snapshot; historical signals are not fills.',
      savedAt?`Preferences last saved: ${new Date(savedAt*1000).toISOString()}`:'Preferences save not confirmed for this draft.',
      '',...fields.map(f=>`${f.label} [${f.id}]: ${f.value===''?'(blank / optional default)':f.value}`),'',
      'Rule references: strategies/renko_supertrend/signals.py, runner.py, ema_proximity.py, trailing_stop.py.',
      'Chart-only formulas: Wilder RSI 14; selected SMA of RSI; five-minute broker OHLC zones.',
      'Serialized configuration (text JSON):',JSON.stringify(body,null,2)];
    const symbol=String(requested.underlying||'unselected').replace(/[^A-Za-z0-9_-]/g,'_');
    return {filename:`sector-pulse-${broker}-${symbol}-${ist.replace(/[: ]/g,'-')}-IST.txt`,text:lines.join('\n')+'\n'};
  }
  function toggleState(state,busy=false){
    const exposure=!!state.position||!!state.pending;
    const recovery=!state.running&&exposure;
    const draining=!!state.shutdown_pending||!!state.running&&state.accepting_entries===false&&!state.management_only;
    return {label:busy?'Please wait…':recovery?'Resume position monitoring':draining?'Stopping…':state.running?'Stop Runner':'Start Runner',disabled:busy||draining||(recovery&&(!state.position||!!state.pending||state.position_recovery_revision!=='management-only-recovery-v1'))};
  }
  function costPnlValues(s){const net=s.cost_pnl||{};return s.broker==='DELTA_INDIA'&&!s.position&&!s.pending?{...net,unrealized_net:0,total_net:Number.isFinite(net.realized_net)?net.realized_net:null}:net;}
  function pnlValues(s,connected=true){const p=s.pnl||{},fresh=connected&&p.available===true;return {realized:Number.isFinite(p.realized)?p.realized:null,unrealized:fresh&&Number.isFinite(p.unrealized)?p.unrealized:null,total:fresh&&Number.isFinite(p.realized)&&Number.isFinite(p.unrealized)?p.realized+p.unrealized:null,label:!connected?'Disconnected':s.position?(fresh?'Executable option bid':'Unpriced / stale option quote'):'Flat · no open option',mode:s.config?.mode||'PAPER'};}
  function executionMarkers(history,state,symbol,timeframe){
    const historical=history.map(m=>({...m,text:m.text,size:1}));
    if(state?.config?.underlying!==symbol||state?.config?.timeframe!==timeframe)return historical;
    // Failed assessments stay in the execution audit, rather than obscuring prices.
    const fills=new Map();
    for(const e of state.execution_signals||[]){
      if(e.status!=='FILLED'||!['BULLISH','BEARISH'].includes(e.direction))continue;
      const buy=e.direction==='BULLISH';
      // timestamp is the host candle; event_at remains the execution audit time.
      fills.set(e.timestamp+'|'+e.direction+'|'+e.mode,{time:e.timestamp,position:buy?'belowBar':'aboveBar',shape:buy?'arrowUp':'arrowDown',color:buy?'#2ea043':'#e53935',size:1,text:(buy?'BUY':'SELL')+' · '+e.mode+' · FILLED'});
    }
    for(const row of state.order_history||[]){
      const snap=row.indicator_snapshot,reason=row.reason||snap?.reason;
      if(row.status!=='FILLED'||row.is_entry!==false||row.underlying_symbol!==symbol)continue;
      const filledAt=row.first_fill_confirmed_at||row.filled_at;if(!Number.isFinite(filledAt))continue;
      const seconds=({'1 minute':60,'2 minutes':120,'3 minutes':180,'5 minutes':300,'10 minutes':600,'15 minutes':900,'30 minutes':1800,'1 hour':3600})[timeframe];
      const time=Math.floor(filledAt/seconds)*seconds;
      const entry=(state.order_history||[]).find(r=>r.lifecycle_id===row.lifecycle_id&&r.is_entry===true);
      const direction=entry?.indicator_snapshot?.indicators?.direction||(state.trade_history||[]).find(t=>t.lifecycle_id===row.lifecycle_id)?.direction||snap?.indicators?.direction;
      if(!['BULLISH','BEARISH'].includes(direction))continue;const bullish=direction==='BULLISH';
      const period=snap?.settings?.ema_exit_length||(reason||'').match(/^EMA(\d+)/)?.[1];
      fills.set('exit|'+row.tag,{time,position:bullish?'aboveBar':'belowBar',shape:'circle',color:'#f2c14e',size:1,text:(bullish?'BUY EXIT':'SELL EXIT')+' · '+(row.mode||state.config.mode)+(period?' · EMA'+period:'')+' · FILLED'});
    }
    const execution=[...fills.values()];
    // A fill replaces only its matching entry/provisional glyph, never an exit.
    const signals=historical.filter(m=>!execution.some(e=>e.time===m.time&&e.position===m.position&&(m.shape===e.shape||m.text.startsWith('PROVISIONAL '))));
    return [...signals,...execution].sort((a,b)=>a.time-b.time);
  }
  function rsiStep(state,close,time,length=14){
    if(!Number.isFinite(close)||!Number.isInteger(length)||length<1)throw Error('Valid close and RSI length required');
    const next={...state,previous:close,time};
    if(!Number.isFinite(state.previous))return {state:next,point:{time}};
    const delta=close-state.previous,gain=Math.max(delta,0),loss=Math.max(-delta,0),count=(state.count||0)+1;
    next.count=count;
    if(count<=length){next.gain=(state.gain||0)+gain/length;next.loss=(state.loss||0)+loss/length;}
    else{next.gain=(state.gain*(length-1)+gain)/length;next.loss=(state.loss*(length-1)+loss)/length;}
    const value=count<length?null:next.loss===0?(next.gain===0?50:100):100-100/(1+next.gain/next.loss);
    return {state:next,point:value===null?{time}:{time,value}};
  }
  function rsiHistory(rows,length=14){let state={},points=[];for(const row of rows){const r=rsiStep(state,row.close,row.timestamp,length);state=r.state;points.push(r.point);}return {state,points};}
  function rsiSma(points,length=14){
    if(!Number.isInteger(length)||length<1||length>200)throw Error('SMA period must be 1–200');
    const window=[];let sum=0;
    return points.map(p=>{if(!Number.isFinite(p.value))return {time:p.time};window.push(p.value);sum+=p.value;if(window.length>length)sum-=window.shift();return window.length===length?{time:p.time,value:sum/length}:{time:p.time};});
  }
  function rsiZone(value){return !Number.isFinite(value)?'Warming up':value<40?'0–40':value<60?'40–60':value<80?'60–80':'80–100';}
  function volumePoints(data,view='host'){
    return [...data.rows,...(view==='host'?(data.forming||[]):[])].map(c=>Number.isFinite(c.volume)&&c.volume>=0?{time:c.timestamp,value:c.volume,color:c.close>=c.open?'#26a69a88':'#ef535088'}:{time:c.timestamp});
  }
  function chartAnalysisAvailable(data){return data.data_quality?.analysis_available!==false;}
  function studyHoverValue(points,latest,time){const value=time===null?latest?.value:points.get(Math.floor(time));return {value,available:Number.isFinite(value),hovered:time!==null};}


  function refreshChartViewport(previous,next,range,same){
    if(!same||!range||!previous.length)return {follow:true,range:null};
    const follow=range.to>=previous.length-3,width=range.to-range.from;
    if(follow){const to=next.length-1+Math.max(1,range.to-(previous.length-1));return {follow:true,range:{from:to-width,to}};}
    const index=Math.max(0,Math.min(previous.length-1,Math.floor(range.from))),time=previous[index].time;
    let nextIndex=next.findIndex(r=>r.time>=time);if(nextIndex<0)nextIndex=Math.max(0,next.length-1);
    const from=nextIndex+(range.from-index);return {follow:false,range:{from,to:from+width}};
  }
  function runnerStartContext(rows,state,seconds){
    const start=state?.started_at;
    if(!Number.isFinite(start)||!state?.config)return null;
    const eligible=Number.isFinite(state.eligible_since)?state.eligible_since:start;
    const events=(state.execution_signals||[]).filter(e=>e.run_id===state.run_id&&Number.isFinite(e.event_at)).sort((a,b)=>a.event_at-b.event_at);
    const event=events.at(-1);
    let logical=null,anchorBefore=null,anchorAfter=null,anchorRatio=null;
    const stamps=(rows||[]).map((r,i)=>({i,time:r.time,at:Number(r.source_timestamp??r.time)+seconds})).filter(r=>Number.isFinite(r.at));
    if(stamps.length){
      const after=stamps.find(r=>r.at>start);
      if(!after){logical=stamps.at(-1).i+.5;anchorBefore=stamps.at(-1).time;anchorAfter=stamps.at(-2)?.time??null;anchorRatio=1.5;}
      else if(after.i===0){if(start>=stamps[0].at-seconds){logical=-.5;anchorBefore=stamps[0].time;anchorAfter=stamps[1]?.time??null;anchorRatio=-.5;}}
      else{const before=stamps.filter(r=>r.i<after.i).at(-1);anchorBefore=before.time;anchorAfter=after.time;anchorRatio=(start-before.at)/(after.at-before.at);logical=before.i+(after.i-before.i)*anchorRatio;}
    }
    return {start,eligible,logical,anchorBefore,anchorAfter,anchorRatio,mode:state.config.mode||'PAPER',running:!!state.running,event,
      eventTiming:!event?'NO_SIGNAL':event.event_at<=start?'BEFORE_START':event.eligible===true?'AFTER_START':event.event_at<=eligible?'BEFORE_ELIGIBLE':'AFTER_START'};
  }
  function mountRunnerStartPointer({chart,host,before}){
    const strip=document.createElement('div');strip.setAttribute('aria-label','Runner activation timing');strip.hidden=true;
    strip.style.cssText='display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;margin:8px 0 0;padding:8px 12px;border-left:2px solid #8db9f4;background:#162235;color:#cbd9ec;border-radius:4px;font:12px/1.5 Arial;font-variant-numeric:tabular-nums';
    before.before(strip);
    const layer=document.createElement('div');layer.setAttribute('aria-label','Runner start pointer');layer.style.cssText='position:absolute;inset:0 110px 28px 0;z-index:5;overflow:hidden;pointer-events:none';host.append(layer);
    let context=null;
    const clock=t=>new Date(t*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
    function paint(){
      layer.replaceChildren();strip.replaceChildren();strip.hidden=!context;
      if(!context)return;
      const title=document.createElement('strong');title.textContent=context.mode+' '+(context.running?'started':'last started')+' · '+clock(context.start)+' IST';title.style.cssText='font-size:12px;font-weight:600;color:#a8cafa';strip.append(title);
      const status=document.createElement('span');
      status.textContent=context.event?(context.event.direction==='BULLISH'?'BUY':'SELL')+' confirmed '+clock(context.event.event_at)+' · '+({BEFORE_START:'before start · excluded',BEFORE_ELIGIBLE:'before entry activation · excluded',AFTER_START:'after start · '+(context.event.status||'assessed').toLowerCase()}[context.eventTiming]):'Waiting for a recorded entry signal';
      status.style.color=context.eventTiming==='BEFORE_START'||context.eventTiming==='BEFORE_ELIGIBLE'?'#e4bc7c':'#bac9dc';strip.append(status);
      strip.title='Actual recorded runner start. The pointer is positioned between nearby completed source observations on the compressed Renko axis. Earlier historical signals are not replayed.';
      if(context.logical===null)return;
      const first=chart.timeScale().timeToCoordinate(context.anchorBefore),second=context.anchorAfter===null?null:chart.timeScale().timeToCoordinate(context.anchorAfter);
      const x=Number.isFinite(first)?Number.isFinite(second)?context.anchorRatio===1.5?first+Math.max(6,Math.min(24,Math.abs(first-second)/2)):first+(second-first)*context.anchorRatio:first:null;
      if(!Number.isFinite(x)||x<0||x>layer.clientWidth)return;
      const line=document.createElement('div');line.style.cssText='position:absolute;top:0;bottom:0;border-left:1px dotted #8db9f4aa';line.style.left=x+'px';
      const tag=document.createElement('span');tag.textContent='▼ START';tag.style.cssText='position:absolute;top:30px;left:5px;padding:3px 6px;background:#1b304b;color:#b6d5ff;border:1px solid #43658d;border-radius:4px;font:600 10px Arial;white-space:nowrap';line.append(tag);layer.append(line);
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange(paint);new ResizeObserver(paint).observe(host);
    return {set(rows,state,seconds){context=runnerStartContext(rows,state,seconds);paint();},clear(){context=null;paint();}};
  }
  function chartSessionBreaks(rows,policy={}){
    const match=/^(\d{2})(\d{2})-/.exec(policy.master_regular_session||'');
    const continuous=policy.seven_day_session&&policy.session_source==='CONTINUOUS_CRYPTO';
    if(!match&&!continuous)return [];
    const hours=match?Number(match[1]):0,minutes=match?Number(match[2]):0;
    const result=[],seen=new Set();
    for(const row of rows||[]){
      const source=Number(row.source_timestamp??row.time);
      if(!Number.isFinite(source)||!Number.isFinite(row.time))continue;
      const local=new Date(source*1000+19800000),day=local.toISOString().slice(0,10);
      if(seen.has(day)||local.getUTCHours()*60+local.getUTCMinutes()<hours*60+minutes)continue;
      seen.add(day);
      result.push({time:row.time,source_timestamp:source,day,
        label:(continuous?'Day':'Session')+' · '+day.slice(8)+'/'+day.slice(5,7)+' · '+String(hours).padStart(2,'0')+':'+String(minutes).padStart(2,'0')+' IST'});
    }
    return result;
  }
  function mountSessionBreaks({chart,host,toolbar,storage,scope}){
    const label=document.createElement('label');label.className='renko-session-break-switch';
    const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=true;checkbox.setAttribute('aria-label','Show session breaks');label.append(checkbox,document.createTextNode(' Session breaks'));
    label.title='Display-only session-opening dividers. Uses the selected broker regular session; continuous markets show daily boundaries.';toolbar.append(label);
    const layer=document.createElement('div');layer.className='renko-session-breaks';layer.setAttribute('aria-label','Trading session boundaries');layer.style.cssText='position:absolute;inset:0 110px 28px 0;z-index:4;overflow:hidden;pointer-events:none';host.append(layer);
    let points=[],key='';
    function paint(){
      layer.replaceChildren();layer.hidden=!checkbox.checked;
      if(!checkbox.checked)return;
      for(const point of points){
        const x=chart.timeScale().timeToCoordinate(point.time);
        if(!Number.isFinite(x)||x<0||x>layer.clientWidth)continue;
        const line=document.createElement('div');line.style.cssText='position:absolute;top:0;bottom:0;border-left:1px dashed #8394ad99';line.style.left=x+'px';
        const text=document.createElement('span');text.textContent=point.label;text.style.cssText='position:absolute;top:8px;left:5px;padding:3px 5px;border-radius:3px;background:#182334e8;color:#b8c8dc;font:10px Arial;white-space:nowrap';line.append(text);layer.append(line);
      }
    }
    checkbox.addEventListener('change',()=>{try{storage.setItem(key,String(checkbox.checked));}catch{}paint();});
    chart.timeScale().subscribeVisibleLogicalRangeChange(paint);new ResizeObserver(paint).observe(host);
    return {set(rows,policy){const next='sector-pulse:session-breaks:v1:'+scope();if(next!==key){key=next;try{checkbox.checked=storage.getItem(key)!=='false';}catch{checkbox.checked=true;}}points=chartSessionBreaks(rows,policy);paint();},clear(){points=[];paint();},reset(){checkbox.checked=true;try{storage.setItem(key,'true');}catch{}paint();}};
  }
  function mountChartDrawings({chart,candles,host,scope,formatPrice,storage}){
    const toolbar=document.createElement('div');toolbar.className='renko-drawing-tools';toolbar.setAttribute('role','group');toolbar.setAttribute('aria-label','Chart drawings');
    const label=document.createElement('label');label.textContent='Draw ';const mode=document.createElement('select');mode.setAttribute('aria-label','Drawing tool');for(const [value,text]of [['cursor','Cursor'],['horizontal','Horizontal line'],['trend','Trend line']]){const o=document.createElement('option');o.value=value;o.textContent=text;mode.append(o);}label.append(mode);
    const remove=document.createElement('button');remove.type='button';remove.textContent='Undo drawing';const clear=document.createElement('button');clear.type='button';clear.textContent='Clear drawings';const note=document.createElement('span');note.setAttribute('role','status');toolbar.append(label,remove,clear,note);host.before(toolbar);
    const style=document.createElement('style');style.textContent='.renko-drawing-tools{box-shadow:0 1px 0 #ffffff05;display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:6px 10px;margin-top:10px;background:#131722;border:1px solid #2a2e39;border-radius:5px;color:#d1d4dc;font:12px Arial}.renko-drawing-tools label{display:flex;align-items:center;gap:7px;margin:0}.renko-drawing-tools select,.renko-drawing-tools button{min-height:32px;padding:5px 9px;border:1px solid #354052;border-radius:4px;background:#1e2533;color:#e2e8f0;font:12px Arial}.renko-drawing-tools select:focus-visible,.renko-drawing-tools button:focus-visible{outline:2px solid #63b3ff;outline-offset:2px}.renko-drawing-tools button:disabled{opacity:.45}.renko-drawing-tools [role=status]{flex:1;min-width:180px;color:#a7bad4}@media(max-width:600px){.renko-drawing-tools{padding:8px;gap:6px}.renko-drawing-tools [role=status]{flex-basis:100%;min-width:0}}';document.head.append(style);
    let key='',drawings=[],rendered=[],anchor=null;
    function status(message){remove.disabled=!drawings.length;clear.disabled=!drawings.length;note.textContent=message||`${drawings.length} drawing${drawings.length===1?'':'s'} · drag horizontal lines to move · saved in this browser`;}
    function erase(){for(const item of rendered){if(item.kind==='horizontal')candles.removePriceLine(item.handle);else chart.removeSeries(item.handle);}rendered=[];}
    function paint(){erase();for(const item of drawings){if(item.kind==='horizontal'){rendered.push({kind:item.kind,handle:candles.createPriceLine({price:item.price,color:'#63b3ff',lineWidth:2,lineStyle:2,axisLabelVisible:true,title:'Drawing'})});}else{const series=chart.addLineSeries({color:'#f2c14e',lineWidth:2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,autoscaleInfoProvider:()=>null});series.setData(item.points);rendered.push({kind:item.kind,handle:series});}}status();}
    function save(){try{storage.setItem(key,JSON.stringify(drawings));paint();}catch{paint();status('Drawings shown · browser storage unavailable');}}
    function valid(d){return d?.kind==='horizontal'?Number.isFinite(d.price)&&d.price>0:d?.kind==='trend'&&Array.isArray(d.points)&&d.points.length===2&&d.points.every(p=>Number.isFinite(p.time)&&Number.isFinite(p.value)&&p.value>0)&&d.points[0].time<d.points[1].time;}
    function sync(){const next='sector-pulse:chart-drawings:v1:'+scope();if(next===key)return;key=next;anchor=null;mode.value='cursor';drawings=[];try{const loaded=JSON.parse(storage.getItem(key)||'[]');if(Array.isArray(loaded))drawings=loaded.filter(valid).slice(-100);}catch{}paint();}
    mode.addEventListener('change',()=>{anchor=null;status(mode.value==='horizontal'?'Click the chart at the desired price':mode.value==='trend'?'Click the first point, then the second point':'Drawings are visual annotations only');host.style.cursor=mode.value==='cursor'?'':'crosshair';});
    remove.addEventListener('click',()=>{anchor=null;drawings.pop();save();});clear.addEventListener('click',()=>{anchor=null;drawings=[];save();});
    toolbar.addEventListener('keydown',event=>{if(event.key==='Escape'){mode.value='cursor';anchor=null;host.style.cursor='';status('Drawing cancelled');}});
    host.addEventListener('keydown',event=>{if(event.key==='Escape'){mode.value='cursor';anchor=null;host.style.cursor='';status('Drawing cancelled');}});

    let dragging=null;
    host.addEventListener('pointerdown',event=>{if(mode.value!=='cursor'||event.button!==0)return;const rect=host.getBoundingClientRect(),y=event.clientY-rect.top,x=event.clientX-rect.left;if(x>rect.width-110)return;let best=null,distance=9;for(let i=0;i<drawings.length;i++){if(drawings[i].kind!=='horizontal')continue;const at=candles.priceToCoordinate(drawings[i].price);if(Number.isFinite(at)&&Math.abs(at-y)<distance){best=i;distance=Math.abs(at-y);}}if(best===null)return;dragging={index:best,pointer:event.pointerId};host.setPointerCapture?.(event.pointerId);host.style.cursor='ns-resize';chart.applyOptions({handleScroll:false,handleScale:false});event.preventDefault();event.stopImmediatePropagation();status('Drag horizontal line · release to save');},true);
    host.addEventListener('pointermove',event=>{if(!dragging)return;const value=candles.coordinateToPrice(event.clientY-host.getBoundingClientRect().top);if(!Number.isFinite(value)||value<=0)return;drawings[dragging.index].price=value;rendered[dragging.index]?.handle.applyOptions({price:value});status('Horizontal line '+formatPrice(value));event.preventDefault();event.stopImmediatePropagation();},true);
    const finishDrag=event=>{if(!dragging)return;dragging=null;host.releasePointerCapture?.(event.pointerId);host.style.cursor='';chart.applyOptions({handleScroll:true,handleScale:true});save();event.preventDefault();event.stopImmediatePropagation();};host.addEventListener('pointerup',finishDrag,true);host.addEventListener('pointercancel',finishDrag,true);
    chart.subscribeClick(event=>{sync();if(mode.value==='cursor'||!event.point)return;const price=candles.coordinateToPrice(event.point.y);if(!Number.isFinite(price)||price<=0)return;if(drawings.length>=100){status('Maximum 100 drawings · undo or clear a drawing');return;}if(mode.value==='horizontal'){drawings.push({kind:'horizontal',price});save();status('Horizontal line at '+formatPrice(price)+' · saved');}else{const time=typeof event.time==='number'?event.time:chart.timeScale().coordinateToTime(event.point.x);if(!Number.isFinite(time)){status('Choose a point within the candle history');return;}const point={time,value:price};if(!anchor){anchor=point;status('First point selected · click the second point');return;}if(anchor.time===time){status('Choose a different candle for the second point');return;}drawings.push({kind:'trend',points:[anchor,point].sort((a,b)=>a.time-b.time)});anchor=null;save();}mode.value='cursor';host.style.cursor='';});sync();return {sync};
  }

  function candleInspection({time,symbol,timeframe,settings={},state,rows=[],forming=false}){
    const matching=state?.config?.underlying===symbol&&state.config.timeframe===timeframe;
    const active=matching&&!!(state.running||state.position||state.pending);
    const records=[...(state?.entry_assessments||[]),state?.latest_entry_assessment].filter(Boolean);
    const record=matching?records.findLast(r=>r.run_id===state.run_id&&r.underlying===symbol&&r.timeframe===timeframe&&r.timestamp===time&&!!r.signal?.provisional===forming):null;
    const c=effectiveFamilySettings((record||active)?state.config:settings);
    const reconstructed=rows.flatMap(r=>[r,...(r.brick_events||[])]).find(r=>r.timestamp===time);
    const q=record?.signal||reconstructed||{};
    const n=v=>Number.isFinite(v)?Number(v.toFixed(2)).toString():'unavailable';
    const text=v=>v==null?'unavailable':typeof v==='number'?n(v):typeof v==='boolean'?(v?'on':'off'):typeof v==='object'?Object.entries(v).map(([k,x])=>k.replaceAll('_',' ')+' '+text(x)).join(' · '):String(v);
    const result={time,forming,source:record?'Recorded runner assessment':forming?'Forming chart preview':'Historical chart reconstruction',configSource:record?'Recorded runner Start settings':active?'Active runner Start settings':'Chart settings',mode:(record||active)?c.mode:null,reason:record?(record.code+' · '+record.reason):forming?'Forming display only; no completed-candle decision.':'No matching recorded assessment. These checks reconstruct chart conditions; they do not establish a live rejection.',checks:[],settings:[]};
    const add=(name,on,pass,rule,observed,reason)=>on&&result.checks.push({name,status:!on?'DISABLED':pass===true?'PASS':pass===false?'FAIL':pass==='WAIT'?'WAIT':pass==='INFO'?'INFO':'UNAVAILABLE',rule,observed,reason:!on?'Not selected for entry.':reason||(pass==null?'Candle-specific evidence unavailable.':!record?'Reconstructed from this candle only.':'Evidence saved for this candle.')});
    const bull=q.direction==='BULLISH',bear=q.direction==='BEARISH',directional=bull||bear;
    const compare=(a,b)=>Number.isFinite(a)&&Number.isFinite(b)&&directional?(bull?a>b:a<b):null;
    const fast=c.ema_fast_enabled!==false,slow=c.ema_slow_enabled!==false;
    add('Renko / ST direction',c.supertrend_enabled!==false,directional?true:null,'ATR '+n(c.atr_length)+' × '+n(c.factor)+' · '+(c.brick_mode||'unavailable')+' brick '+n(c.manual_brick), 'Direction '+(q.direction||'unavailable')+' · Supertrend '+n(q.supertrend)+' · calculated brick '+n(q.box),'Directional state only; reversal / entry event is assessed separately.');
    const slope=q.supertrend_slope_filter;
    add('Supertrend slope',c.supertrend_slope_enabled===true,slope?.allowed??null,
      'Lookback '+n(c.supertrend_slope_bars||1)+' · minimum '+n(c.supertrend_slope_min_atr||0)+' ATR / observation',
      slope?'Slope '+n(slope.slope_atr)+' ATR / observation · '+(slope.reason||''):'Waiting for completed Supertrend observations',
      'BUY requires rising Supertrend; SELL requires falling Supertrend. Flat values and flip jumps do not qualify.');

    const alignment=directional&&Number.isFinite(q.close)&&(!fast||Number.isFinite(q.ema10))&&(!slow||Number.isFinite(q.ema30))?(!fast||compare(q.close,q.ema10))&&(!slow||compare(q.close,q.ema30))&&(!(fast&&slow)||compare(q.ema10,q.ema30)):null;
    add('EMA alignment',fast||slow,alignment,'Close and selected EMAs ordered in '+(q.direction||'selected direction'),'Close '+n(q.close)+' · EMA '+n(c.ema_fast_length||10)+' '+n(q.ema10)+' · EMA '+n(c.ema_slow_length||30)+' '+n(q.ema30));
    const prior=slow?q.ema30:fast?q.ema10:null;
    add('Third EMA',!!c.ema_third_enabled,compare(q.close,q.ema100)===null||(prior!==null&&compare(prior,q.ema100)===null)?null:compare(q.close,q.ema100)&&(prior===null||compare(prior,q.ema100)),'EMA '+n(c.ema_third_length||100)+' · close and prior selected EMA on trend side','EMA '+n(q.ema100)+' · prior selected EMA '+n(prior));
    add('EMA widening',c.ema_widening_enabled!==false,typeof q.ema_widening==='boolean'?q.ema_widening:null,'Strict widening for '+n(c.widening_window)+' candles','Gap '+n(Number.isFinite(q.ema10)&&Number.isFinite(q.ema30)?Math.abs(q.ema10-q.ema30):null)+' · widening '+text(q.ema_widening));
    if(c.anti_chop_enabled){const gate=q.anti_chop;for(const item of gate?.checks||[{label:'Anti-chop assessment',passed:null}])add(item.label+(item.mandatory===false?' · alternative support':''),true,item.mandatory===false?'INFO':item.passed,(gate?.mode||'Manual')+' · '+timeframe+' checklist'+(item.required==null?'':' · threshold '+n(item.required)),item.observed==null?'No candle-specific observation':n(item.observed)+(item.reference==null?'':' / reference '+n(item.reference)),gate?.reason||'Current anti-chop assessment unavailable.');}
    const cal=q.calibrated_filter;
    add('Calibrated overlap',!!c.calibrated_enabled,cal?.allowed,'Average overlap ≤ '+n((c.calibrated_overlap_max??.4)*100)+'% · '+n(c.calibrated_overlap_pairs||6)+' pairs',cal?'Observed '+n(cal.average_overlap*100)+'%':'No candle-specific overlap evidence',cal?.reason);
    add('Retest / EMA touch',!!c.retest_enabled,typeof q.retest_signal==='boolean'?(q.retest_signal?true:'WAIT'):null,'Enabled patterns: '+['engulfing','harami','star'].filter(k=>c['retest_'+k]).join(', '),'Touched '+text(q.retest_touched)+' · ready '+text(q.retest_ready)+' · bounce '+text(q.retest_bounce)+' · patterns '+text(q.retest_patterns)+' · touch evidence '+text(q.retest_touch_evidence),q.retest_signal?'Confirmed retest recorded.':q.retest_touch_evidence?'Touch recorded; confirmed qualifying retest still required.':'No confirmed retest / active touch evidence for this candle.');
    add('ADX',!!c.use_adx,Number.isFinite(q.adx)&&Number.isFinite(c.adx_threshold)?q.adx>c.adx_threshold:null,'ADX '+n(c.adx_length)+' / smoothing '+n(c.adx_smoothing)+' > '+n(c.adx_threshold),'ADX '+n(q.adx));
    const rsiRule=(prefix='rsi')=>c[prefix+'_level_mode']==='BETWEEN'?'Bullish '+n(c[prefix+'_bullish_min'])+'–'+n(c[prefix+'_bullish_max'])+' · bearish '+n(c[prefix+'_bearish_min'])+'–'+n(c[prefix+'_bearish_max']):'Bullish > '+n(c[prefix+'_bullish_above'])+' · bearish < '+n(c[prefix+'_bearish_below']);
    const levelPass=Number.isFinite(q.rsi14)&&directional?(c.rsi_level_mode==='BETWEEN'?q.rsi14>=c[bull?'rsi_bullish_min':'rsi_bearish_min']&&q.rsi14<=c[bull?'rsi_bullish_max':'rsi_bearish_max']:bull?q.rsi14>c.rsi_bullish_above:q.rsi14<c.rsi_bearish_below):null;
    add('RSI levels',!!c.rsi_level_enabled,levelPass,rsiRule(),'RSI '+n(q.rsi14));
    add('RSI slope',!!c.rsi_slope_enabled,typeof q.rsi_slope_pass==='boolean'?q.rsi_slope_pass:Number.isFinite(q.rsi14_slope)&&directional?(bull?q.rsi14_slope>0:q.rsi14_slope<0):null,'RSI '+n(c.rsi_slope_length||14)+' · directional slope','RSI '+n(q.rsi14)+' · slope '+n(q.rsi14_slope));
    const gate=(name,on,g,rule)=>add(name,on,/unavailable|incomplete|missing|stale/i.test(g?.reason||'')?null:typeof g?.allowed==='boolean'?g.allowed:null,rule,g?Object.entries(g).filter(([key])=>['direction','state','distance_atr','distance_points','price','completed_atr','counts','required','one_minute','five_minute','rsi','value','levels','bullish_marker','bearish_marker'].includes(key)).map(([key,value])=>(key==='one_minute'?'Host ST':key==='five_minute'?'Higher ST':key.replaceAll('_',' '))+' '+text(value&&typeof value==='object'?Object.fromEntries(Object.entries(value).filter(([k])=>!['timestamp','revision'].includes(k))):value)).join(' · ')||'See the candle-specific reason.':'No evidence saved for this candle.',g?.reason);
    gate('Higher-timeframe Supertrend',!!c.higher_timeframe_enabled,q.mtf_supertrend,'Completed '+(c.supertrend_timeframe||'unavailable')+' agreement');
    for(let i=1;i<=3;i++){const g=q.mtf_rsi?.slots?.find(s=>s.slot===i);gate('Higher-timeframe RSI '+i,!!c['rsi_htf_'+i+'_enabled'],g,'Completed '+(c['rsi_htf_'+i+'_timeframe']||'unavailable')+' · '+rsiRule('rsi_htf_'+i));}
    gate('Market structure',!!c.market_structure_enabled,q.market_structure,'Confirmed directional swing structure');
    gate('Manual trend markers',!!c.manual_trend_enabled,q.manual_trend,n(c.manual_trend_closes)+' closes · bullish > '+n(c.manual_trend_bullish)+' / bearish < '+n(c.manual_trend_bearish));
    gate('Opposing-zone clearance',!!c.zone_entry_enabled,q.zone_entry_filter,'Clearance ≥ '+n(c.zone_entry_min_atr||1)+' ATR · rearm '+text(c.zone_entry_rearm));
    const distance=Number.isFinite(q.close)&&Number.isFinite(q.ema10)?Math.abs(q.close-q.ema10):null;
    add('EMA entry proximity',!!c.ema_proximity_enabled,'WAIT',c.ema_momentum_enabled?'Retest ≤ 0.50 ATR · first momentum ≤ 1.50 ATR':(c.ema_proximity_mode||'ATR')+' limit '+n(c.ema_proximity_distance),'Candle-close distance '+n(distance)+' pts / '+n(Number.isFinite(distance)&&q.host_atr>0?distance/q.host_atr:null)+' ATR · completed ATR '+n(q.host_atr),'Close-distance context only. Fresh quote and preflight EMA evidence are not stored in this candle assessment; no live proximity pass inferred.');
    const body=directional&&Number.isFinite(q.open)&&Number.isFinite(q.close)?(bull?q.close>q.open:q.close<q.open):null;
    const outer=directional&&Number.isFinite(q.high)&&Number.isFinite(q.low)&&Number.isFinite(q.close)&&q.high>q.low?(bull?q.close>=q.high-(q.high-q.low)/3:q.close<=q.low+(q.high-q.low)/3):null;
    add('Momentum directional body',!!c.ema_momentum_enabled,body,'Close above open for bullish / below for bearish','Open '+n(q.open)+' · close '+n(q.close));
    add('Momentum outer-third close',!!c.ema_momentum_enabled,outer,'Bullish close in top third / bearish close in bottom third','High '+n(q.high)+' · low '+n(q.low)+' · close '+n(q.close));
    add('First momentum qualification',!!c.ema_momentum_enabled,'WAIT','New completed qualification · aligned EMAs · widening · directional RSI/body · outer-third close','Entry direction '+text(q.entry_direction)+' · body '+text(body)+' · outer third '+text(outer)+' · RSI slope '+n(q.rsi14_slope),'Qualification episode and live execution context are required; these component values alone do not establish eligibility.');
    add('Momentum chase',!!c.ema_momentum_enabled,'WAIT','Directional advance after signal close ≤ 0.25 completed ATR','Signal close '+n(q.close)+' · ATR '+n(q.host_atr),'Fresh preflight price for this candle is unavailable.');
    add('Entry event',true,typeof q.entry_qualified==='boolean'?(q.entry_qualified?true:'WAIT'):null,c.intrabar_entries?'Intrabar entry enabled':'Completed-candle entry','Entry '+text(q.entry_direction)+' · reversal '+text(q.cross_direction)+' · diagnostic '+text(q.entry_diagnostic),record?'Recorded eligibility: '+text(record.eligible)+' · '+record.code:'Historical simulation only; no recorded execution decision.');
    add('Continuation',!!c.supertrend_continuation_enabled,null,'Selected Supertrend continuation','Candle diagnostic '+text(q.entry_diagnostic),'Continuation episode evidence is not separately saved for this candle.');
    add('Quick-loss range lock',!!c.sideways_enabled,null,'Lock after loss within '+n(c.sideways_max_candles)+' host candles; strict breakout to release','Historical lock boundaries are not saved in this candle record.','Current range-lock state is not substituted for this candle.');
    add('Session / quota / locks',true,null,'Entry cutoff '+(c.session_deadline||'unavailable')+' · trade limit '+n(c.max_trades),'Historical runner lock, quota and fresh order/broker state unavailable','Current runner state is not substituted for this historical candle.');
    const keys=Object.keys(c).filter(k=>/^(anti_chop_|ema_|rsi_|supertrend_|higher_timeframe|atr_|factor$|brick_|manual_brick|widening_|retest_|use_adx$|adx_|calibrated_|zone_entry_|market_structure_|manual_trend_|intrabar_entries$|session_deadline$|carry_policy$|max_trades$|sideways_)/.test(k)&&!k.endsWith('_indicator'));
    const visibleSetting=k=>{if(k.startsWith('anti_chop_')&&!c.anti_chop_enabled)return false;const family=k.startsWith('ema_')?'ema':k.startsWith('rsi_')?'rsi':k.startsWith('adx_')||k==='use_adx'?'adx':k.startsWith('supertrend_')||k.startsWith('higher_timeframe')?'supertrend':k.startsWith('market_structure_')?'structure':k.startsWith('zone_')?'zones':null;if(family&&c[family+'_family_enabled']===false)return false;if(k.startsWith('calibrated_')&&!c.calibrated_enabled)return false;if(k.startsWith('manual_trend_')&&!c.manual_trend_enabled)return false;if(k.startsWith('sideways_')&&!c.sideways_enabled)return false;if(k.startsWith('retest_')&&!c.retest_enabled)return false;return true;};
    result.settings=keys.filter(visibleSetting).sort().map(k=>({name:k.replaceAll('_',' '),value:text(c[k])}));
    if(forming)for(const row of result.checks)if(row.status==='PASS')row.reason='Provisional forming value; '+row.reason;
    return result;
  }

  function coalescedHover(render,schedule){let pending=false,latest;return value=>{latest=value;if(pending)return;pending=true;schedule(()=>{pending=false;render(latest);});};}
  function chartSettingsFailure(error){return error?.status===400&&/RSI|rsi_|Choose Auto\/Manual|must be higher than the host timeframe|timeframe is unavailable/.test(error.message||'');}
  function chartStreamHealth(data={},elapsed=0){
    const tickAt=data.market?.tick_exchange_at??data.forming?.stream_exchange_at;
    const age=Number.isFinite(data.server_at)&&Number.isFinite(tickAt)?data.server_at-tickAt+elapsed:null;
    const recent=elapsed>=0&&elapsed<=5;
    const closed=['CLOSED','OUTSIDE_REGULAR_SESSION'].includes(data.market?.session?.status)||data.market?.status==='CLOSED';
    const fresh=!closed&&recent&&data.market?.connected===true&&data.market?.fresh===true&&age!==null&&age>=0&&age<=15;
    const orders=recent&&data.orders?.connected===true;
    const orderBasis=String(data.orders?.basis||'');
    const restOrders=/^(Delta REST reconciliation|Dhan REST reconciliation|Motilal native orderbook reconciliation)(?:;|$)/.test(orderBasis);
    const tick=age===null?'Tick age unknown':age<0?'Tick timestamp ahead of server':`Tick age ${Math.floor(age)}s`;
    const tickFresh=recent&&data.market?.connected===true&&data.market?.tick_fresh===true&&age!==null&&age>=0&&age<=15;
    const chart=closed?'Market closed':!recent?'Chart updates stale':fresh?'Chart feed is live':tickFresh?'Live ticks · current candle OHLC unavailable':data.market?.connected===false?'Chart feed disconnected':'Chart feed stale / unavailable';
    const marketError=data.runner?.config?.intrabar_entries===false&&/forming OHLC unavailable; intrabar entry blocked/.test(data.market?.error||'')?'Current chart candle unavailable; runner uses confirmed completed candles.':data.market?.error;
    return {live:fresh&&data.runner_snapshot_fresh!==false&&(orders||restOrders||data.runner?.config?.mode==='PAPER'),chartFresh:fresh,tickFresh:!closed&&tickFresh,restOrders,ordersConnected:orders,paper:data.runner?.config?.mode==='PAPER',text:chart+' · '+(orders?'Order stream connected':recent?(restOrders?'Orders: '+orderBasis.split(';')[0]+' · no notification stream':'Order stream unavailable; broker reconciliation active'):'Order-stream status stale')+' · '+tick+(data.runner_snapshot_fresh===false?' · Runner status refresh delayed':'')+(marketError?' · '+marketError:'')};
  }
  function feedPresentation(data={},elapsed=0){
    const health=chartStreamHealth(data,elapsed);
    const label=health.chartFresh?(data.runner_snapshot_fresh===false?'Chart live · runner status stale':health.paper?'Chart live · Paper mode':health.restOrders?'Chart live · orders checked via API':health.ordersConnected?'Feed live':'Chart live · order stream unavailable'):health.text.startsWith('Live ticks')?'Live prices · candle recovering':health.text.startsWith('Market closed')?'Market closed':'Feed delayed · retrying';
    return {label,detail:health.text,live:health.live};
  }
  function feedHealthSummary(data={},elapsed=0){
    const h=chartStreamHealth(data,elapsed),c=data.confirmed_indicators||data.runner?.confirmed_indicators;
    const prices=h.text.startsWith('Market closed')?'outside regular session':h.tickFresh?'live':'awaiting fresh ticks';
    const candles=data.candles?.error?'retrieval recovering':data.candles?.waiting_for_close?'awaiting completed broker candle':data.candles?.busy?'refreshing in background':data.candles?.latest_completed?'broker cache ready':'awaiting broker candles';
    return 'Prices: '+prices+' · Candles: '+candles+' · Indicators: '+(c?'confirmed '+new Date(c.last_at*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'}):'awaiting confirmed state')+' · Orders: '+(h.ordersConnected?'connected':h.restOrders?'API reconciliation':'reconciliation / stream unavailable');
  }
  function lastKnownIndicator(point,fresh=true){
    return Number.isFinite(point?.value)?point.value.toFixed(2)+(fresh?'':' · last known · delayed'):fresh?'Warming up':'Unavailable · retrying';
  }
  function chartStreamStatus(data,elapsed=0){return chartStreamHealth(data,elapsed).text;}
  function overrideState(s={},context={},direction='',busy=false){
    const c=s.config||{},mode=c.mode||'';
    const matches=c.underlying===context.symbol&&c.timeframe===context.timeframe&&(c.broker||'FYERS')===context.broker&&mode===context.mode;
    let reason=s.manual_override_revision!=='explicit-entry-v1'?'Override backend update pending':!matches?'Display the active runner instrument, timeframe and mode':!s.running&&(s.position||s.pending)?'Monitoring stopped; recover existing exposure before authorizing new entries':s.management_only?'Position monitoring only; new entries disabled':!s.running||!s.accepting_entries||s.shutdown_pending?'Start the runner before overriding an entry':s.position||s.pending?'Runner must be flat with no pending order':s.trades_used>=c.max_trades?'Maximum entry trades reached':mode==='LIVE'&&!s.live_available?'Live runtime gate disabled':!['BULLISH','BEARISH'].includes(direction)?'Choose Bullish or Bearish':'';
    return {disabled:busy||!!reason,label:'Override Entry · '+(mode||'loading'),reason:reason||'Bypass entry signal filters; active risk limits and strategy exits apply.'};
  }


  function uniformRenkoBricks(rows,box,maxBricks=50000){
    if(!Number.isFinite(box)||box<=0)throw Error('A positive calculated brick size is required for Renko.');
    const completed=rows.filter(r=>!r.is_forming&&!r.provisional&&Number.isFinite(r.close)).slice().sort((a,b)=>a.timestamp-b.timestamp);
    if(!completed.length)return [];
    let level=Math.floor(completed[0].close/box+1e-10),direction=0;const bricks=[];
    for(const row of completed){
      const ratio=row.close/box,group=[];
      function emit(open,close){if(bricks.length+group.length>=maxBricks)throw Error('Renko display exceeds 50,000 bricks; choose a shorter history range.');group.push({open:open*box,close:close*box,high:Math.max(open,close)*box,low:Math.min(open,close)*box,source_timestamp:row.timestamp,source_close:row.close,box});level=close;}
      if(direction>=0&&ratio>=level+1-1e-10){while(ratio>=level+1-1e-10)emit(level,level+1);direction=1;}
      else if(direction<=0&&ratio<=level-1+1e-10){while(ratio<=level-1+1e-10)emit(level,level-1);direction=-1;}
      else if(direction===1&&ratio<=level-2+1e-10){emit(level-1,level-2);while(ratio<=level-1+1e-10)emit(level,level-1);direction=-1;}
      else if(direction===-1&&ratio>=level+2-1e-10){emit(level+1,level+2);while(ratio>=level+1-1e-10)emit(level,level+1);direction=1;}
      // Coordinate-only subsecond offsets order bricks from the same source candle.
      // Displayed labels/readouts retain the original source candle timestamp.
      group.forEach((b,i)=>bricks.push({...b,time:row.timestamp+i/(group.length+1),brick_index:bricks.length}));
    }
    return bricks;
  }
  function renkoStudyPoints(points,bricks,kind='line'){
    if(!bricks)return points;
    if(kind==='volume'||!points.length)return [];
    if(points.some(p=>Number.isFinite(p.time)&&!Number.isInteger(p.time)))return points;
    const result=[];let index=0,known=null;
    for(const brick of bricks){while(index<points.length&&points[index].time<=brick.source_timestamp){known=points[index++];}if(known&&Number.isFinite(known.value))result.push({...known,time:brick.time});}
    return result;
  }
  function provisionalRenkoBricks(bricks,forming,box,priceConfirmed=false){
    const last=bricks?.at(-1);if(!last||!forming||!Number.isFinite(forming.close)||!(box>0)||(priceConfirmed?forming.timestamp<last.source_timestamp:forming.timestamp<=last.source_timestamp))return [];
    const movement=forming.close-last.close,distance=Math.abs(movement);if(distance<box*1e-10)return [];
    const sign=Math.sign(movement),prior=Math.sign(last.close-last.open),reverse=!!prior&&sign!==prior;
    let opening=last.close+(reverse?sign*box:0);const result=[];
    const count=Math.min(1000,Math.max(1,Math.ceil((distance-(reverse?box:0))/box-1e-10)));
    for(let i=0;i<count;i++){
      const close=opening+sign*box,before=i===0?0:(i+(reverse?1:0))*box,required=i===0&&reverse?2*box:box;
      const progress=Math.max(0,Math.min(1,(distance-before)/required)),fillClose=opening+sign*box*progress;
      result.push({time:forming.timestamp+(i+1)/(count+2),open:opening,high:Math.max(opening,close),low:Math.min(opening,close),close,color:'rgba(0,0,0,0)',borderColor:sign>0?'#26a69a':'#ef5350',wickColor:'transparent',provisional:true,progress,fillClose});opening=close;
    }
    return result;
  }
  function renkoChartSeries(chart,kind){
    const key=kind==='volume'?'addHistogramSeries':'addLineSeries',original=chart[key].bind(chart);
    chart[key]=options=>{const series=original(options),set=series.setData.bind(series),update=series.update.bind(series);let source=[];
      series.setData=points=>{source=points.slice();const title=options?.title||'',key=title==='EMA 10'?'ema10':title==='EMA 30'?'ema30':title==='EMA 100'?'ema100':title==='Exit EMA'?'ema_exit':title==='1-minute Supertrend'?'supertrend':null;const bricks=chart.uniformRenkoRows;if(key&&bricks?.some(b=>Number.isFinite(b[key])))set(bricks.filter(b=>Number.isFinite(b[key])).map(b=>({time:b.time,value:b[key],...(key==='supertrend'?{color:b.close>=b[key]?'#26a69a':'#ef5350'}:{})})));else set(renkoStudyPoints(source,bricks,kind));};
      series.update=point=>{if(!chart.uniformRenkoRows)update(point);};
      return series;
    };
  }

  function activeRunnerFields(current,state){
    const raw=state?.config;
    if(!raw||!(state.running||state.position||state.pending)||current.symbol&&current.symbol!==raw.underlying)return null;
    const config=effectiveFamilySettings(raw),fields={};
    const names={underlying:'symbol',rsi_slope_length:'rsi-length',paper_capital_inr:'paper-capital',execution_route:'delta-execution-route'};
    for(const [key,value] of Object.entries(config)){
      const id=names[key]||key.replaceAll('_','-');
      if(Object.hasOwn(current,id))fields[id]=value==null?'':value;
    }
    fields['supertrend-slope-enabled']=raw.supertrend_slope_enabled===true;fields['supertrend-slope-bars']=raw.supertrend_slope_bars??1;fields['supertrend-slope-min-atr']=raw.supertrend_slope_min_atr??0;fields['strategy-basis']=raw.strategy_basis||'LEGACY';fields['renko-brick-exit-enabled']=raw.renko_brick_exit_enabled===true;fields.mode=raw.mode;fields.timeframe=raw.timeframe;if(raw.execution_route==='CASH_EQUITY'&&Number.isFinite(raw.quantity))fields.lots=raw.quantity;
    for(const [family,ids]of Object.entries(FAMILY_RULES))if(raw[family+'_family_enabled']===false)for(const id of ids){fields[id]=false;if(Object.hasOwn(current,id+'-indicator'))fields[id+'-indicator']=false;}
    return fields;
  }

  function chartCandles(data,view){
    if(view==='synthetic'){if(!chartAnalysisAvailable(data))return [];if(data.settings?.strategy_basis==='RENKO'){return data.rows.flatMap(r=>(r.brick_events||[]).map((b,i,a)=>({time:r.timestamp+(i+1)/(a.length+2),source_timestamp:b.source_timestamp??r.timestamp,source_close:r.host_close??r.close,open:b.open,high:b.high,low:b.low,close:b.close,box:b.box,supertrend:b.supertrend,ema10:b.ema10,ema30:b.ema30,ema_exit:b.ema_exit,lifecycle_event:b.lifecycle_event})));}const box=data.settings?.brick_mode==='Manual'?Number(data.settings.manual_brick):Number(data.rows.at(-1)?.box);return uniformRenkoBricks(data.rows,box);}
    const rows=(view==='synthetic'?data.rows:[...data.rows,...(data.forming||[])]).map(c=>view==='synthetic'?{time:c.timestamp,open:c.synthetic_open,high:Math.max(c.synthetic_open,c.synthetic_close),low:Math.min(c.synthetic_open,c.synthetic_close),close:c.synthetic_close}:{time:c.timestamp,open:c.host_open??c.open,high:c.host_high??c.high,low:c.host_low??c.low,close:c.host_close??c.close});
    if(view!=='synthetic')for(const gap of data.data_quality?.gaps||[])rows.push({time:gap.timestamp});
    return rows.sort((a,b)=>a.time-b.time);
  }
    function table(target,headers,rows){target.replaceChildren();const t=document.createElement('table');t.style.cssText='width:100%;font-size:12px;text-align:left';const h=t.createTHead().insertRow();for(const v of headers){const th=document.createElement('th');th.textContent=v;th.style.padding='10px';h.append(th);}const b=t.createTBody();for(const row of rows){const r=b.insertRow();for(const v of row){const td=r.insertCell();if(v instanceof HTMLElement)td.append(v);else td.textContent=String(v??'—');td.style.padding='10px';}}target.append(t);}
    function drawTradeTable(target,rows,displayBroker){
      const broker=displayBroker||(rows[0]?.orders?.[0]?.broker==='DELTA_INDIA'?'Delta India':'FYERS');
      const stamp=t=>new Date(t*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'});
      const value=n=>broker==='Delta India'?root.DeltaINR.format(n,rows[0]?.quote_currency||'USD'):n==null?'Unavailable':Number(n).toFixed(2),time=t=>t==null?'Open / unavailable':stamp(t);
      const details=t=>{const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('pre');s.textContent='Saved indicators / inputs / events';p.textContent=JSON.stringify({entry:t.entry_indicator_snapshot,exits:t.exit_indicator_snapshots,reconciliations:t.reconciliation_events,provenance:t.snapshot_provenance,costs:t.costs,exposure:t.exposure_range,sideways:t.sideways_lock_trigger,sideways_release:t.sideways_lock_release},null,2);p.style.cssText='max-width:580px;max-height:320px;overflow:auto;white-space:pre-wrap';d.append(s,p);return d;};
      const pnl=(n,label)=>{const span=document.createElement('span'),known=Number.isFinite(n);span.textContent=label+': '+(known?(n>0?'+':n<0?'−':'')+value(Math.abs(n)):'Unavailable');span.style.color=!known||n===0?'#b5c7de':n>0?'#50c878':'#ff6b6b';span.style.fontWeight='600';span.style.display='block';return span;};
      const result=t=>{const box=document.createElement('div');box.style.minWidth='210px';box.append(pnl(t.costs?.realized_net,'Net realized · estimate after costs'),pnl(t.realized_pnl,'Gross realized · before costs'));return box;};
      const costs=t=>{const box=document.createElement('div');box.append(pnl(t.costs?.realized_net,'Net realized · estimate after costs'),pnl(t.costs?.unrealized_net,'Open liquidation · estimate after costs'));const charges=document.createElement('small');charges.textContent='Incurred charges '+value(t.costs?.incurred?.total)+' · Exit cost estimate '+value(t.costs?.estimated_exit_costs?.total);box.append(charges);return box;};
      table(target,['Mode / stable trade ID','Trade result · INR','Instrument / strike / expiry',broker+' IDs or Paper order IDs (entry → exits)','Fill confirmed start → end · IST','Underlying entry → exit (spot/futures)','Fill price entry → exit','Qty requested / filled / remaining','Realized before costs','Unrealized before costs','Exit reason / status','Shares or lots / entry side / reason','Configured exits','Execution valuation · IST','After-cost estimates','Position range / sideways lock','Journal snapshots'],rows.map(t=>[
        t.mode+' · '+t.trade_id+' · '+(t.run_id||'Run unavailable'),result(t),
        t.contract+' · '+t.execution_route==='DELTA_PERPETUAL'?'Perpetual futures · '+(t.entry_side==='SELL'?'SHORT':'LONG')+' · no expiry':(t.execution_route==='CASH_EQUITY'?'Cash equity · '+t.products.join(', '):(t.option_type==='CE'?'Call':t.option_type==='PE'?'Put':'Type unavailable'))+' · strike '+value(t.strike)+' · expiry '+(t.expiry_epoch?new Date(t.expiry_epoch*1000).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata'}):'Unavailable'),
        (t.entry_order_ids.join(', ')||'Pending / unavailable')+' → '+(t.exit_order_ids.join(', ')||'Open / unavailable'),
        time(t.entry_time)+' → '+time(t.end_time),(t.underlying_symbol||'Underlying unavailable')+' · '+value(t.spot_entry)+' → '+value(t.spot_exit),value(t.entry_price)+' → '+value(t.exit_price),
        'Entry '+t.entry_requested+'/'+t.entry_filled+' · Exit '+t.exit_requested+'/'+t.exit_filled+' · Remaining '+(t.remaining_quantity??'Unknown'),
        pnl(t.realized_pnl,'Gross realized · before costs'),pnl(t.unrealized_pnl,'Gross unrealized · before costs'),t.exit_reasons.join(', ')+' · '+t.status,(t.execution_route==='CASH_EQUITY'?'Filled shares '+t.entry_filled:t.execution_route==='DELTA_PERPETUAL'?'Filled contracts '+t.entry_filled:'Filled lots '+(t.lots??'Unavailable'))+' · '+(t.entry_side??'BUY')+' · '+(t.entry_reasons||[]).join(', '),'Target '+(t.spot_target==null?'No fixed target':value(t.spot_target))+' · Stop '+(t.spot_stop==null?'No fixed stop':value(t.spot_stop))+' · EMA '+(t.ema_exit_enabled===false?'Disabled':t.ema_exit_length||10)+' · Trailing '+(t.trailing_enabled==null?'Unavailable':t.trailing_enabled?t.trailing_mode+' '+t.trailing_step:'Disabled'),'Bid '+value(t.valuation?.bid)+' · Exchange '+time(t.valuation?.exchange_at)+' · Observed '+time(t.valuation?.observed_at),costs(t),'High '+value(t.exposure_range?.high)+' · Low '+value(t.exposure_range?.low)+' · Host candles '+(t.exposure_host_candles??'Unavailable')+' · '+(t.sideways_lock_trigger?'Quick net-loss lock':'No lock trigger')+(t.sideways_lock_release?' · '+t.sideways_lock_release.release_reason:''),details(t)]));
      if(!rows.length){const message=document.createElement('p');message.textContent='No actual trades recorded for this strategy.';target.append(message);}
    }
  function preserveJournalView(target,render){
    const view=target.ownerDocument.defaultView,oldHeight=target.style.minHeight,left=target.scrollLeft;
    const before=[...target.querySelectorAll('tbody tr')],anchor=before.find(row=>{const box=row.getBoundingClientRect();return box.bottom>0&&box.top<view.innerHeight;});
    const anchorKey=anchor?.dataset.journalKey,anchorTop=anchor?.getBoundingClientRect().top;
    const details=new Map([...target.querySelectorAll('details')].map(d=>[d.closest('tr')?.dataset.journalKey,{open:d.open,scroll:d.querySelector('pre')?.scrollTop||0,focused:d.contains(target.ownerDocument.activeElement)}]));
    target.style.minHeight=target.getBoundingClientRect().height+'px';
    try{
      render();
      for(const d of target.querySelectorAll('details')){const saved=details.get(d.closest('tr')?.dataset.journalKey);if(!saved)continue;d.open=saved.open;const pre=d.querySelector('pre');if(pre)pre.scrollTop=saved.scroll;if(saved.focused)d.querySelector('summary')?.focus({preventScroll:true});}
      target.scrollLeft=left;
    }finally{target.style.minHeight=oldHeight;}
    const replacement=anchorKey&&[...target.querySelectorAll('tbody tr')].find(row=>row.dataset.journalKey===anchorKey);
    if(replacement){const delta=replacement.getBoundingClientRect().top-anchorTop;if(Math.abs(delta)>1)view.scrollBy({top:delta,left:0,behavior:'instant'});}
  }
  function renderTradeTable(target,rows,displayBroker){
    preserveJournalView(target,()=>{
      drawTradeTable(target,rows,displayBroker);
      [...target.querySelectorAll('tbody tr')].forEach((row,index)=>{const trade=rows[index];row.dataset.journalKey=JSON.stringify([trade.broker,trade.instance_key,trade.trade_id||trade.lifecycle_id,trade.run_id]);});
    });
  }
  // Display-only host OHLC pivots. Input contains completed candles only.
  function hostZones(rows,barSeconds=300,strongOnly=true) {
    const zones={supply:null,demand:null};
    const valid=c=>c&&Number.isFinite(c.timestamp)&&['open','high','low','close'].every(k=>Number.isFinite(c[k]))&&c.low<=Math.min(c.open,c.close)&&c.high>=Math.max(c.open,c.close);
    for(let i=0;i<rows.length;i++){
      const c=rows[i];
      if(!valid(c))return {supply:null,demand:null,error:'Invalid host OHLC'};
      if(i&&c.timestamp<=rows[i-1].timestamp)return {supply:null,demand:null,error:'Unordered host candles'};
      for(const side of ['supply','demand']){
        const z=zones[side];
        if(z&&!z.brokenAt&&(side==='supply'?c.close>z.upper:c.close<z.lower))z.brokenAt=c.timestamp+barSeconds;
      }
      if(i<4)continue;
      const pivot=rows[i-2],neighbors=[rows[i-4],rows[i-3],rows[i-1],c];
      const p=i-2,atr=p>=13?rows.slice(p-13,p+1).reduce((sum,b,j)=>{const prev=rows[p-13+j-1]?.close;return sum+Math.max(b.high-b.low,Number.isFinite(prev)?Math.abs(b.high-prev):0,Number.isFinite(prev)?Math.abs(b.low-prev):0);},0)/14:null;
      const supplyNear=Math.max(pivot.open,pivot.close),demandNear=Math.min(pivot.open,pivot.close);
      const downClose=Math.min(rows[i-1].close,c.close),upClose=Math.max(rows[i-1].close,c.close);
      const supplyStrong=atr>0&&downClose<pivot.low&&supplyNear-downClose>=atr;
      const demandStrong=atr>0&&upClose>pivot.high&&upClose-demandNear>=atr;
      if(neighbors.every(n=>pivot.high>n.high)&&(!strongOnly||supplyStrong))zones.supply={lower:supplyNear,upper:pivot.high,pivotAt:pivot.timestamp,confirmedAt:c.timestamp+barSeconds,brokenAt:null,...(strongOnly?{atr,departure:supplyNear-downClose}: {})};
      if(neighbors.every(n=>pivot.low<n.low)&&(!strongOnly||demandStrong))zones.demand={lower:pivot.low,upper:demandNear,pivotAt:pivot.timestamp,confirmedAt:c.timestamp+barSeconds,brokenAt:null,...(strongOnly?{atr,departure:upClose-demandNear}: {})};
    }
    return zones;
  }
  function fiveMinuteZoneRows(data,symbol,cutoff){
    if(data.symbol!==symbol||data.timeframe!=='5 minutes')throw Error('Five-minute source identity mismatch');
    if(data.history_error||data.history?.history_error)throw Error('Five-minute history stale / failed');
    if(!chartAnalysisAvailable(data))throw Error('Five-minute OHLC validation failed');
    const rows=data.rows||[];
    if(rows.some(c=>c.is_forming||!Number.isFinite(c.timestamp)||c.timestamp+300>cutoff))throw Error('Five-minute source includes unclosed candles');
    const zones=hostZones(rows,300);if(zones.error)throw Error(zones.error);
    if(!rows.length)throw Error('Completed five-minute candles unavailable');
    if(cutoff-(rows.at(-1).timestamp+300)>=300)throw Error('Five-minute source behind displayed history');
    return rows;
  }
  function zoneBandRect(zone,range,width,height,x,upperY,lowerY){
    if(!zone||!range||zone.pivotAt>range.to||![width,height,upperY,lowerY].every(Number.isFinite))return null;
    if(x===null){if(zone.pivotAt<range.from)x=0;else return null;}
    if(!Number.isFinite(x))return null;
    const left=Math.max(0,Math.min(width,x)),top=Math.max(0,Math.min(upperY,lowerY)),bottom=Math.min(height,Math.max(upperY,lowerY));
    if(width<=left||bottom<top)return null;
    const bandHeight=Math.min(height,Math.max(6,bottom-top));
    const bandTop=Math.max(0,Math.min(height-bandHeight,(top+bottom-bandHeight)/2));
    return {x:left,y:bandTop,width:width-left,height:bandHeight};
  }
  function assessedHigherRows(rows,state,context,frame){
    const gate=state?.last_signal?.mtf_supertrend,point=gate?.five_minute;
    if(context?.basis!=='active'||context.runId!==state?.run_id||gate?.higher_timeframe!==frame||!point||!Number.isFinite(point.supertrend))return rows;
    // Only the latest assessed candle is authoritative here; earlier rows remain historical chart research.
    return [...rows.filter(row=>row.timestamp<point.timestamp),{...point,is_forming:false}];
  }
  function fiveMinuteSupertrendPoints(rows,plotted,cutoff,seconds=300){
    const five=rows.filter(c=>!c.is_forming&&c.timestamp+seconds<=cutoff&&Number.isFinite(c.supertrend));
    let index=-1;
    return plotted.map(c=>{
      while(index+1<five.length&&five[index+1].timestamp+seconds<=c.time)index++;
      const h=five[index];
      return h&&c.time-h.timestamp-seconds<seconds?{time:c.time,value:h.supertrend,color:h.direction==='BULLISH'?'#57d6b0':'#ff9e80'}:{time:c.time};
    });
  }
  // Native pane primitive: chart redraws it on pan, zoom, price-scale drag and resize.
  function zoneBandPrimitive(chart,series,getZones){
    const renderer={draw(target){target.useMediaCoordinateSpace(({context,mediaSize})=>{
      const range=chart.timeScale().getVisibleRange();if(!range)return;
      const zones=getZones();
      for(const side of ['supply','demand']){
        const z=zones[side];if(!z)continue;
        const rect=zoneBandRect(z,range,mediaSize.width,mediaSize.height,chart.timeScale().timeToCoordinate(z.pivotAt),series.priceToCoordinate(z.upper),series.priceToCoordinate(z.lower));
        const container=document.getElementById('renko-chart');if(container)container.dataset[side+'ZoneRender']=JSON.stringify({pivotAt:z.pivotAt,upper:z.upper,lower:z.lower,range,rect});
        if(!rect)continue;
        context.save();
        const rgb=side==='supply'?'239,124,134':'67,200,179';
        context.fillStyle=`rgba(${rgb},${z.brokenAt ? .07 : .22})`;
        context.fillRect(rect.x,rect.y,rect.width,rect.height);
        context.strokeStyle=`rgba(${rgb},${z.brokenAt ? .55 : .95})`;context.lineWidth=1;
        if(z.brokenAt)context.setLineDash([5,4]);
        context.strokeRect(rect.x+.5,rect.y+.5,Math.max(0,rect.width-1),Math.max(0,rect.height-1));
        context.setLineDash([]);context.font='600 11px Arial';
        const label=side.toUpperCase()+(z.brokenAt?' · BROKEN':' · CONFIRMED');
        const labelWidth=context.measureText(label).width+10;
        const labelX=Math.min(Math.max(0,mediaSize.width-labelWidth),rect.x+5),labelY=Math.max(14,Math.min(mediaSize.height-4,side==='demand'?rect.y+rect.height+14:rect.y-5));
        context.fillStyle='rgba(19,23,34,.90)';context.fillRect(labelX,labelY-12,labelWidth,16);
        context.fillStyle=`rgb(${rgb})`;context.fillText(label,labelX+5,labelY);
        context.restore();
      }
    });}};
    const view={zOrder:()=> 'top',renderer:()=>renderer};
    let requestUpdate=()=>{};
    return {attached(params){requestUpdate=params.requestUpdate;},detached(){requestUpdate=()=>{};},paneViews:()=>[view],updateAllViews(){},refresh(){requestUpdate();}};
  }
  // Embedded charts retain their own controls: share visual selections only.
  function chartDisplaySelection(fields={}){
    const ids=[...DESTINATION_RULES.map(id=>id+'-indicator'),'volume-enabled','rsi-sma-enabled',...Object.keys(FAMILY_RULES).map(name=>name+'-family-enabled')];
    return Object.fromEntries(ids.filter(id=>typeof fields[id]==='boolean').map(id=>[id,fields[id]]));
  }
  function chartControlState(state={},fresh=false,selected='PAPER',busy=false){
    const exposure=!!state.position||!!state.pending;
    const draining=!!state.shutdown_pending||!!state.running&&state.accepting_entries===false;
    const supported=state.chart_controls_revision==='stopped-flat-chart-controls-v1';
    const next=selected==='PAPER'?'LIVE':'PAPER';
    const modeDisabled=!supported||!fresh||busy||!!state.running||exposure||draining||(next==='LIVE'&&!state.live_available);
    return {next,stopDisabled:!supported||(!fresh&&!state.run_id)||busy||draining||!(state.running||exposure),modeDisabled,
      label:(state.running?'Active runner ':'Stopped · last run ')+(state.config?.mode||'none')+' · Next Start '+selected,
      reason:!supported?'Chart controls await backend update':!fresh?'Runner status stale; refresh required':state.running||exposure||draining?'Stop and finish closing/reconciliation before changing mode':next==='LIVE'&&!state.live_available?'Live authorization/runtime gate is off':'Mode selection only; Start remains separate'};
  }
  function configurationLibrary(raw){
    if(raw==null)return {schema_version:1,records:[],preferred:{}};
    if(raw.schema_version!==1||!Array.isArray(raw.records)||!raw.preferred||typeof raw.preferred!=='object')throw Error('Saved configuration library is unsupported; stored data was preserved.');
    const records=[...new Set(raw.records.map(r=>r.symbol).filter(Boolean))].map(symbol=>chooseConfiguration(raw,symbol)).filter(Boolean).map(r=>({...r,id:JSON.stringify([r.symbol]),name:r.name.startsWith('Previously saved · ')?r.symbol:r.name}));
    return {...raw,records,preferred:Object.fromEntries(records.map(r=>[r.symbol,r.id]))};
  }
  function chooseConfiguration(library,symbol){
    const matches=library.records.filter(r=>r.symbol===symbol&&r.settings&&r.settings.symbol===symbol);
    return matches.find(r=>r.id===library.preferred[symbol])||matches.slice().sort((a,b)=>Number(b.saved_at||0)-Number(a.saved_at||0)||a.id.localeCompare(b.id))[0]||null;
  }
  function storeConfiguration(library,name,fields,now){
    name=String(name||'').trim();if(!name||name.length>80)throw Error('Enter a configuration name of 1–80 characters.');
    if(!fields.symbol)throw Error('Select an exact instrument before saving a configuration.');
    const id=JSON.stringify([fields.symbol]);
    const record={id,name,symbol:fields.symbol,settings:{...fields},saved_at:now};
    return {...library,records:[...library.records.filter(r=>r.symbol!==fields.symbol),record],preferred:{...library.preferred,[fields.symbol]:id},deleted_ids:(library.deleted_ids||[]).filter(x=>x!==id),deleted_symbols:(library.deleted_symbols||[]).filter(x=>x!==fields.symbol)};
  }
  function deleteConfiguration(library,id){
    const record=library.records.find(r=>r.id===id);if(!record)return library;
    const preferred={...library.preferred};if(preferred[record.symbol]===id)delete preferred[record.symbol];
    const next={...library,records:library.records.filter(r=>r.id!==id),preferred,deleted_ids:[...new Set([...(library.deleted_ids||[]),id])],deleted_symbols:[...new Set([...(library.deleted_symbols||[]),record.symbol])]};
    const fallback=chooseConfiguration(next,record.symbol);if(fallback)preferred[record.symbol]=fallback.id;
    return next;
  }
  function restoredConfigurationFields(current,record){
    // Loading a name never changes execution mode or arms a runner.
    return {...current,...inheritRsiHtfFields(migrateDestinations(record.settings)),...(Object.hasOwn(current,'delta-execution-route')?{'delta-execution-route':record.settings['delta-execution-route']||'OPTIONS'}:{}),symbol:record.symbol,mode:current.mode};
  }
  async function mount(initialView) {
    const isEngine=new URLSearchParams(location.search).get('renkoEngine')==='1';
    await root.BrokerForms.ready;
    const fetch=(url,options)=>root.BrokerForms.fetch('renko',url,options);
    const pageParams=new URLSearchParams(location.search),boundAccount=root.BrokerForms.accounts().find(a=>a.id===(pageParams.get('renkoAccount')||pageParams.get('brokerAccount'))),selectedBroker=root.SectorPulseWorkspace?.workspace?.broker||boundAccount?.broker||pageParams.get('renkoBroker')||'FYERS',isDelta=selectedBroker==='DELTA_INDIA',isDhan=selectedBroker==='DHAN',isMotilal=selectedBroker==='MOTILAL_OSWAL',isNative=isDhan||isMotilal,dhanAccount=root.SectorPulseWorkspace?.workspace?.id||pageParams.get('renkoAccount')||pageParams.get('brokerAccount')||'',brokerName=isMotilal?'Motilal Oswal':isDhan?'Dhan':isDelta?'Delta India':'FYERS',apiBase=isMotilal?'/api/renko-motilal/'+encodeURIComponent(dhanAccount)+'/':isDhan?'/api/renko-dhan/'+encodeURIComponent(dhanAccount)+'/':isDelta?'/api/renko-delta/':'/api/renko-supertrend/',registryBase=isNative?apiBase:'/api/renko-instances/',isBatchChartView=pageParams.get('renkoBatchChart')==='1';let instanceId=pageParams.get('renkoInstance')||'default';
    const active=isEngine||initialView==='renko-supertrend'||pageParams.has('renkoBroker');
    if(pageParams.has('renkoBroker')){for(const node of document.querySelectorAll('.view.active'))node.classList.remove('active');for(const node of document.querySelectorAll('[data-view].active')){node.classList.remove('active');node.setAttribute('aria-pressed','false');}}
    document.querySelector('[data-view="ema-cross"]').insertAdjacentHTML('beforebegin',`<button type="button" data-view="renko-supertrend" class="${active?'active':''}" aria-pressed="${active}">Renko Supertrend</button>`);
    document.querySelector('.work').insertAdjacentHTML('beforeend',`<section id="renko-supertrend" class="view ${active?'active':''}">
      <header class="head"><div><span class="label">PINAKI RENKO ST AUTO RESEARCH</span><h1>Renko Supertrend Strategy</h1><small class="muted">Default: Renko Supertrend + slope · EMA and other filters optional</small></div><div id="renko-state" class="status">STOPPED</div></header>
      <section class="panel"><div class="step-title"><div><span class="label">SIGNAL SETTINGS</span><h2>Renko & Supertrend</h2></div><span class="badge">COMPLETED CANDLES</span></div>
      <div class="field-grid" style="margin-top:14px">
      <label class="field">Strategy basis<select id="renko-strategy-basis"><option value="RENKO">Renko bricks</option><option value="CANDLESTICK">Candlestick</option><option value="LEGACY">Legacy synthetic · saved setups</option></select><small>Renko uses confirmed bricks; Candlestick uses confirmed candles. Chart view is display only.</small></label>
      <label class="field">Underlying search<input id="renko-search" placeholder="TRENT, RELIANCE, NIFTY…" autocomplete="off"></label>
      <label class="field">Instrument<select id="renko-symbol"><option value="">Search and select an underlying</option></select></label>
      <label class="field">Timeframe<select id="renko-timeframe"><option>1 minute</option><option>2 minutes</option><option>3 minutes</option><option selected>5 minutes</option><option>10 minutes</option><option>15 minutes</option><option>30 minutes</option><option>1 hour</option></select></label>
      <label class="field">Intrabar entries and EMA exits (OFF: completed candle close; ON: live breach)<input id="renko-intrabar-entries" type="checkbox"></label><label class="field">RSI slope filter (ON: bullish rising / bearish falling; entry candle timing)<input id="renko-rsi-slope-enabled" type="checkbox" checked></label><small id="renko-rsi-slope-status"></small><label class="field">RSI level entry filter (optional)<input id="renko-rsi-level-enabled" type="checkbox" checked></label><label class="field">RSI entry mode<select id="renko-rsi-level-mode"><option value="THRESHOLD">Threshold · above / below</option><option value="BETWEEN">Between · inclusive range</option></select></label><label class="field renko-rsi-band">Bullish RSI range<span class="renko-rsi-band-inputs"><input aria-label="Bullish RSI minimum" id="renko-rsi-bullish-min" type="number" min="0" max="100" step="0.1" value="60"><span>to</span><input aria-label="Bullish RSI maximum" id="renko-rsi-bullish-max" type="number" min="0" max="100" step="0.1" value="70"></span></label><label class="field renko-rsi-band">Bearish RSI range<span class="renko-rsi-band-inputs"><input aria-label="Bearish RSI minimum" id="renko-rsi-bearish-min" type="number" min="0" max="100" step="0.1" value="35"><span>to</span><input aria-label="Bearish RSI maximum" id="renko-rsi-bearish-max" type="number" min="0" max="100" step="0.1" value="40"></span></label><label class="field">Bullish RSI strictly above<input id="renko-rsi-bullish-above" type="number" min="0" max="100" step="0.1" value="50"></label><label class="field">Bearish RSI strictly below<input id="renko-rsi-bearish-below" type="number" min="0" max="100" step="0.1" value="40"></label><label class="field">EMA10 retest entries (optional; matching confirmed pattern)<input id="renko-retest-enabled" type="checkbox" checked disabled></label><label class="field">Retest: bullish / bearish engulfing<input id="renko-retest-engulfing" type="checkbox" checked disabled></label><label class="field">Retest: bullish / bearish harami<input id="renko-retest-harami" type="checkbox" checked disabled></label><label class="field">Retest: morning / evening star (intraday, gap optional)<input id="renko-retest-star" type="checkbox" checked disabled></label><label class="field">EMA gap widening window<input id="renko-widening-window" type="number" min="2" max="100" step="1" value="2"></label><label class="field">ATR length<input id="renko-atr-length" type="number" min="1" step="1" value="5"></label>
      <label class="field">Base factor<input id="renko-factor" type="number" min="0.1" step="0.1" value="3"></label>
      <label class="field">Brick size mode<select id="renko-brick-mode"><option>Auto</option><option>Manual</option></select><small>Renko execution keeps the calculated Auto size fixed from its history anchor. Manual uses your saved brick size.</small></label>
      <label class="field">Manual brick size<input id="renko-manual-brick" type="number" min="0.00000001" step="any" value="12.8" disabled></label>
      <label class="field">Choppy filter (ADX)<input id="renko-use-adx" type="checkbox"></label>
      <label class="field">ADX threshold<input id="renko-adx-threshold" type="number" min="0" max="100" step="any" value="20" disabled></label>
      <label class="field">ADX DI length<input id="renko-adx-length" type="number" min="1" step="1" value="14" disabled></label>
      <label class="field">ADX smoothing<input id="renko-adx-smoothing" type="number" min="1" step="1" value="14" disabled></label></div>
      <p class="muted">Supertrend ports your supplied research indicator; select entry indicators independently below. Every selected Strategy indicator must agree for execution; Indicator selections independently govern chart replay and visible studies. A setup re-arms after it ceases to qualify. Calculated on standard time candles; native Renko bars can produce different values. It has not been verified against the protected original.</p>
      <p id="renko-retest-status" class="muted" role="status">Retest confirmation OFF.</p><p id="renko-provisional-status" class="muted">Intrabar entries are opt-in. Square-off / entry cutoff: NSE/BSE 15:10 IST; MCX selected contract session end, subject to verified master session.</p><div id="renko-status" class="handoff-status" role="status">Select an instrument to load the strategy.</div>
      <div class="risk-strip"><div><b id="renko-direction">—</b><small>Selected direction</small></div><div><b id="renko-event">—</b><small>Selected entry qualification</small></div><div><b id="renko-box">—</b><small>Active brick size</small></div><div><b id="renko-st">—</b><small>Supertrend</small></div></div></section>
      <section class="panel" style="margin-top:15px"><span class="label">PRICE CANDLES & CALCULATED SUPERTREND</span><h2>Strategy chart</h2><label class="field" style="max-width:260px">Chart view<select id="renko-chart-view"><option value="host">Candlestick</option><option value="line">Line</option><option value="synthetic">Renko · uniform bricks</option></select></label><div class="field-grid"><label class="field">History review range<select id="renko-history-preset"><option value="7">Last 7 calendar days</option><option value="45" selected>Last 45 calendar days (~30 sessions)</option><option value="90">Last 90 calendar days</option><option value="custom">Custom date range</option></select></label><label class="field">From · IST<input id="renko-history-from" type="date" disabled></label><label class="field">To · IST<input id="renko-history-to" type="date" disabled></label></div><p id="renko-history-range" class="muted"></p><p id="renko-chart-description" class="muted">Real broker OHLC candles · opening time in IST · calculated Supertrend and historical entry/exit labels. Yellow exit dots use the historical EMA10 simulation; actual runner exits use its active exit setting and appear in the trade journal. Choose Synthetic Renko to inspect calculated bodies separately.</p><button id="renko-latest-signal" class="button" type="button">Show latest historical event</button><p id="renko-signal-range" class="muted"></p><div id="renko-candle-readout" class="muted" aria-live="polite"></div><p id="renko-zone-status" class="muted" role="status"></p><div id="renko-chart-stack"><div id="renko-chart" style="height:380px;margin-top:12px"></div><section aria-label="RSI zone indicator" style="margin-top:12px"><div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><b style="color:#bc8cff">RSI 14 · host close</b><label style="color:#ffd166">SMA of RSI period <input id="renko-rsi-sma-period" type="number" min="1" max="200" step="1" value="14" style="width:60px" aria-label="SMA of RSI period"></label><span id="renko-rsi-sma-readout" style="color:#ffd166">SMA 14 · warming up</span><span id="renko-rsi-readout" role="status">Warming up</span><span id="renko-rsi-hover" style="color:#9598a1"></span><span style="color:#e68b95">0–40</span><span style="color:#a7a9b1">40–60</span><span style="color:#64cfb8">60–80</span><span style="color:#e7bb67">80–100</span></div><div id="renko-rsi-chart" style="height:170px;margin-top:8px;border:1px solid #2a2e39;background:linear-gradient(to top,#39232f 0%,#39232f 40%,#252932 40%,#252932 60%,#163c38 60%,#163c38 80%,#403626 80%,#403626 100%)"></div><small class="muted">Display only · Wilder RSI 14 seeded from loaded host candles · live forming value is provisional.</small></section></div><div id="renko-anchor" class="muted"></div><h3>Historical closed-candle signal simulation — not option fills</h3><button id="renko-older-events" class="button" type="button">Older events</button> <button id="renko-newer-events" class="button" type="button">Newer events</button><span id="renko-events-page" class="muted"></span><div id="renko-events" style="overflow-x:auto;margin-top:12px"></div></section>
      <section class="panel" style="margin-top:15px"><h2>Durable option trade journal</h2><div style="display:flex;align-items:center;gap:12px;margin:16px 0"><a class="button" href="/api/renko-supertrend/journal" download="renko-option-journal.json">Export journal JSON</a> <label>Mode <select id="renko-journal-mode"><option value="ALL">All</option><option value="PAPER">Paper</option><option value="LIVE">Live</option></select></label></div><p class="muted">Paper simulated option fills and live broker-confirmed fills only. Spot observations are captured at local fill confirmation; exact exchange-fill spot may be unavailable. Gross P&amp;L uses option fills and executable bid. Net P&amp;L deducts estimated brokerage, statutory charges and configured additional slippage; broker invoices remain unreconciled.</p><div id="renko-trades" style="overflow-x:auto"></div></section><section class="panel" style="margin-top:15px"><span class="label">FYERS EXECUTION</span><h2>Renko Supertrend runner</h2>
      <p class="muted">Cash equity buys shares for bullish signals and sells shares short for bearish signals using INTRADAY; exits close the held side. Derivatives use whole lots. Qualified bullish EMA setup buys nearest-expiry ATM Call; qualified bearish setup buys ATM Put. When EMA exit is enabled, fresh underlying ticks below the selected host-close EMA close a Call; ticks above it close a Put, independent of ADX. Default period is 10. Optional target/stop are absolute underlying prices and trigger exits on fresh ticks. Changes apply on the next Start Runner. Opposite confirmed Supertrend reversal also exits (optional ADX gate). Wall-clock square-off and entry cutoff: NSE/BSE 15:10 IST; MCX selected contract session end (subject to a stricter verified session). No same-candle re-entry. Orders remain subject to fresh quotes and broker reconciliation.</p>
      <div class="field-grid"><label class="field">Execution mode<select id="renko-mode"><option value="PAPER">Paper</option><option value="LIVE">Live — real FYERS orders</option><option value="BACKTEST">Backtest · historical research</option></select></label>
      <label class="field">Lots<input id="renko-lots" type="number" min="1" max="100" value="1" step="1"></label>
      <label class="field">Virtual Paper capital · INR<input id="renko-paper-capital" type="number" min="1" max="1000000000" step="any" value="100000"></label>
      <label class="field">Trade limit<input id="renko-max-trades" type="number" min="1" max="1000" value="2" step="1"></label>
      <label class="field">Quoted premium cap (₹, optional)<input id="renko-max-premium" type="number" min="1" placeholder="No cap"></label>
      <label><input id="renko-sideways-enabled" type="checkbox"> Sideways filter · quick after-cost loss</label>
      <label class="field">Quick-loss window · host candles touched<input id="renko-sideways-max-candles" type="number" min="1" max="10" step="1" value="3"></label>
      <label class="field">Additional slippage · option premium points per side<input id="renko-additional-slippage-points" type="number" min="0" step="any" value="0"></label>
      <label><input id="renko-ema-exit-enabled" type="checkbox" checked> Enable EMA exit on fresh underlying ticks</label>
      <label class="field">Exit EMA period · selected strategy basis<input id="renko-ema-exit-length" list="renko-exit-ema-periods" type="number" min="1" max="1000" step="1" value="10"></label>
      <label><input id="renko-ema-proximity-enabled" type="checkbox" checked> EMA proximity · first EMA (optional; new entries only)</label>
      <label class="field">EMA10 distance basis<select id="renko-ema-proximity-mode"><option value="ATR">Completed host ATR multiple</option><option value="POINTS">Underlying points</option></select></label>
      <label class="field">Entry distance limit · |price − EMA10| / completed ATR, or points<input id="renko-ema-proximity-distance" type="number" min="0.01" step="any" value="0.5"></label>
      <input id="renko-ema-policy-profile" type="hidden" value="all-broker-flexible-atr-v1"><label class="field">Flexible ATR entries<input id="renko-ema-momentum-enabled" type="checkbox" checked><small>Retests ≤ 0.50 ATR · First momentum entry ≤ 1.50 ATR · Chase cap 0.25 ATR. Completed-candle confirmation required.</small></label>
      <label><input id="renko-trailing-enabled" type="checkbox"> Enable trailing stop-loss (optional)</label>
      <label class="field">Trailing stop basis<select id="renko-trailing-basis"><option value="OPTION_PREMIUM_PERCENT">Option executable bid · percent</option><option value="UNDERLYING_POINTS">Underlying · points</option></select></label>
      <label class="field">Trailing distance · percent or underlying points<input id="renko-trailing-distance" type="number" min="0.01" step="any" value="10"></label>
      <label class="field">Hard target · underlying price (optional)<input id="renko-spot-target" type="number" min="0.01" step="any" placeholder="Blank disables target"></label>
      <label class="field">Hard stop-loss · underlying price (optional)<input id="renko-spot-stop" type="number" min="0.01" step="any" placeholder="Blank disables stop"></label>
      <label class="field">Daily loss budget (₹, optional)<input id="renko-daily-budget" type="number" min="1" placeholder="No budget"></label></div>
      <div class="packet-actions" style="margin-top:12px"><button id="renko-toggle" class="button">Start Runner</button><button id="renko-reconcile-close" class="button secondary" type="button" hidden>Reconcile broker closure</button></div>
      <div id="renko-runner-message" class="handoff-status" role="status">No Renko runner has been started.</div>
      <div id="renko-action-error" role="alert" style="color:#ff8585" hidden></div>
      <div id="renko-pnl"></div><p id="renko-paper-funds" class="renko-small"></p><div id="renko-trailing-status" aria-live="polite"></div><div id="renko-orders" style="overflow-x:auto"></div><h3>Runner entry assessment audit</h3><p>First tick assessment and eventual owned fill are separate. These rows identify the exact candle behind the chart labels.</p><div id="renko-entry-audit" style="overflow-x:auto"></div></section></section>`);
    const el=id=>document.getElementById('renko-'+id),section=document.getElementById('renko-supertrend');
    section.querySelector('header').insertAdjacentHTML('afterend',`<section class="panel renko-workspace" id="renko-workspace">
      <div class="renko-workspace-head"><div><span class="label">STRATEGY WORKSPACE</span><h2>Trade setup</h2><p id="renko-broker-note">Choose an instrument, size and execution mode.</p></div><label class="field renko-broker-field">Broker view<select id="renko-broker"><option value="FYERS">FYERS</option><option value="DELTA_INDIA">Delta India</option></select></label></div>
      <div class="renko-instances-head"><h3>Active & saved instances</h3><span id="renko-instance-count" class="renko-small"></span></div><div id="renko-instances" class="renko-instance-grid"></div>
      <details class="renko-policy" id="renko-policy"><summary>Delta execution policy</summary><div class="field-grid"><label class="field" id="renko-delta-execution-field">Trade product<select id="renko-delta-execution-route"><option value="OPTIONS">Options · buy ATM Call / Put</option><option value="DELTA_PERPETUAL">Perpetual futures · long / short</option></select></label><label class="field">Optional daily strategy cutoff · IST<input id="renko-session-deadline" type="time" value="23:30"></label><label class="field">Price source<select id="renko-price-source"><option value="PERPETUAL_LAST_TRADE">Perpetual traded-price candles</option></select></label><label class="field">Order terms<select id="renko-order-terms"><option value="MARKETABLE_LIMIT_IOC">Marketable limit · IOC</option></select></label><label class="field">Crypto trading schedule<select id="renko-carry-policy"><option value="CONTINUOUS">Continuous · 24/7 · no daily cutoff</option><option value="DAILY_SQUARE_OFF">Optional daily strategy cutoff</option></select></label></div><p class="renko-small">Choose options or perpetual futures explicitly. Options buy ATM Calls / Puts; perpetual futures buy bullish signals and sell bearish signals short. Exits reduce the owned quantity. Perpetual entries require full notional collateral plus fees; broker leverage stays unchanged. Funding and liquidation costs are excluded from estimates. Crypto has no daily market close. Continuous trading retains signal exits, stops and exact held option expiry protection. Existing saved daily cutoffs stay selected.</p></details>
      <div class="renko-launch"><div><h3>Start instruments together</h3><p class="renko-small">Choose instruments below, then apply the same visible settings to each.</p></div><button id="renko-new-instance" class="renko-quiet-button" type="button">Save displayed instrument as an instance</button></div>
    </section>`);
    const workspaceStyle=document.createElement('style');workspaceStyle.textContent=`
      #renko-workspace{background:#172132;border:1px solid #334154;border-radius:12px;padding:24px;margin-bottom:16px;color:#d9e2f0}#renko-workspace h2{font:600 24px/1.25 "Avenir Next",Arial,sans-serif;margin:5px 0 8px;letter-spacing:-.5px}#renko-workspace h3{font:600 15px/1.4 "Avenir Next",Arial,sans-serif;margin:0}#renko-workspace p{margin:5px 0;color:#8fa1ba;font-size:13px;line-height:1.5}.renko-workspace-head{display:flex;justify-content:space-between;align-items:flex-start;gap:24px}.renko-broker-field{min-width:180px;max-width:230px}.renko-instances-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:22px 0 12px}.renko-small{font-size:12px;color:#8fa1ba;line-height:1.5}.renko-instance-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}.renko-instance-card{padding:17px 18px;border:1px solid #334154;border-radius:9px;background:#1a2639;min-width:0}.renko-instance-card.is-selected{border-color:#719fe8;box-shadow:inset 3px 0 #719fe8}.renko-instance-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}.renko-broker-tag{font-size:10px;letter-spacing:1.1px;color:#9bb4d6;text-transform:uppercase;font-weight:600}.renko-state-tag{font-size:10px;font-weight:600;padding:4px 7px;border-radius:4px;color:#a4b1c5;background:#33415466}.renko-state-tag.live{color:#79cbbd;background:#26a69a19}.renko-state-tag.pending{color:#e0bf7c;background:#c4a15f19}.renko-instance-title{font:600 17px/1.3 "Avenir Next",Arial,sans-serif;margin:0 0 5px;overflow-wrap:anywhere}.renko-instance-meta{color:#8fa1ba;font-size:12px}.renko-instance-values{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0}.renko-instance-values small{display:block;font-size:10px;color:#8fa1ba;margin-bottom:4px}.renko-instance-values b{font:500 17px/1.3 Menlo,"SFMono-Regular",monospace;font-variant-numeric:tabular-nums}.renko-instance-footer{border-top:1px solid #334154;padding-top:12px;display:flex;justify-content:space-between;align-items:center;gap:10px}.renko-instance-footer a{font-size:12px;color:#9ebdf1;text-decoration:none;padding:5px 0}.renko-quiet-button{border:1px solid #44556f;background:transparent;color:#b9c9e2;padding:8px 12px;border-radius:6px;font:500 12px Arial,sans-serif;cursor:pointer}.renko-quiet-button.stop{color:#e6b1b1;border-color:#745051}.renko-quiet-button:hover{background:#33415455}.renko-instance-footer a:focus-visible,.renko-quiet-button:focus-visible{outline:2px solid #719fe8;outline-offset:3px}.renko-policy{margin-top:20px;border-top:1px solid #334154;padding-top:15px}.renko-policy summary{font-size:12px;color:#b9c9e2;cursor:pointer}.renko-policy .field-grid{margin-top:14px}.renko-launch{border-top:1px solid #334154;margin-top:20px;padding-top:20px;display:flex;align-items:center;justify-content:space-between;gap:16px}.renko-batch-area{margin-top:14px;display:grid;grid-template-columns:minmax(260px,1fr) 230px;gap:16px;align-items:start}#renko-batch-symbols{min-height:108px;max-height:154px}#renko-batch-result{padding-top:10px;border-top:1px solid #334154;margin-top:16px}#renko-start-selected{width:100%;margin-top:10px}@media(max-width:760px){#renko-workspace{padding:18px}.renko-workspace-head,.renko-launch{flex-direction:column}.renko-broker-field{width:100%;max-width:none}.renko-batch-area{grid-template-columns:1fr}.renko-instance-grid{grid-template-columns:1fr}}`;
    document.head.append(workspaceStyle);
    if(isNative){const option=document.createElement('option');option.value=selectedBroker;option.textContent=brokerName+' · selected account';el('broker').append(option);}el('broker').value=selectedBroker;
    if(root.SectorPulseWorkspace?.workspace){el('broker').disabled=true;el('broker').title='Switch broker accounts through Users & broker accounts.';}
    el('policy').hidden=!isDelta;for(const id of ['session-deadline','price-source','order-terms','carry-policy'])el(id).closest('label').hidden=!isDelta;
    el('broker').onchange=()=>{const url=new URL(location.href);url.searchParams.set('renkoBroker',el('broker').value);url.searchParams.delete('renkoInstance');location.href=url;};
    let batchChartArea=null;const batchChartFrames=new Map();let lastInstanceRows=[];let stopAllBusy=false;
    function syncBatchCharts(rows){
      if(isBatchChartView)return;
      if(pageParams.has('renkoInstance')){
        if(batchChartArea)batchChartArea.hidden=true;
        for(const card of batchChartFrames.values())card.remove();
        batchChartFrames.clear();
        el('chart-stack').closest('.panel').hidden=false;
        return;
      }
      const choices=new Set(Array.from(el('batch-symbols')?.selectedOptions||[]).map(o=>o.value));
      const broker=isDelta?'DELTA_INDIA':'FYERS';const unique=new Map();
      const chartRows=pageParams.has('renkoInstance')?rows.filter(row=>(row.instance_key||'default')===instanceId):rows;
      if(pageParams.has('renkoInstance')){choices.clear();for(const row of chartRows){const symbol=row.instrument||row.config?.underlying;if(symbol)choices.add(symbol);}}
      for(const row of chartRows){const symbol=row.instrument||row.config?.underlying;if(row.broker!==broker||!choices.has(symbol))continue;const prior=unique.get(symbol);if(!prior||row.instance_key!=='default')unique.set(symbol,row);}
      const wanted=[...unique.values()];const chartPanel=el('chart-stack').closest('.panel');
      if(!batchChartArea){batchChartArea=document.createElement('section');batchChartArea.className='panel';batchChartArea.id='renko-batch-charts';const heading=document.createElement('h2');heading.textContent='Batch charts · separate runner per instrument';batchChartArea.append(heading);chartPanel.before(batchChartArea);}
      batchChartArea.hidden=wanted.length===0;chartPanel.hidden=wanted.length>0;
      const keys=new Set(wanted.map(v=>v.instance_key||'default'));
      for(const [key,card] of batchChartFrames)if(!keys.has(key)){card.remove();batchChartFrames.delete(key);}
      if(wanted.length===0)return;
      for(const item of wanted){const key=item.instance_key||'default';let card=batchChartFrames.get(key);if(!card){card=document.createElement('article');card.className='renko-batch-chart-card';const heading=document.createElement('h3');heading.style.cssText='padding:14px 0';const frame=document.createElement('iframe');frame.title=(item.instrument||item.config?.underlying)+' strategy chart';const url=new URL(location.href);url.searchParams.set('renkoBroker',item.broker);url.searchParams.set('renkoInstance',key);url.searchParams.set('renkoBatchChart','1');url.searchParams.set('renkoChartSymbol',item.instrument||item.config?.underlying);frame.src=url.href;frame.loading='lazy';frame.allowFullscreen=true;frame.style.cssText='width:100%;height:850px;border:1px solid #334154;border-radius:8px;display:block';card.append(heading,frame);batchChartArea.append(card);batchChartFrames.set(key,card);}card.querySelector('h3').textContent=(item.instrument||item.config?.underlying)+' · '+(item.config?.mode||'PAPER')+' · '+(item.pending?'Pending reconciliation':item.running?(item.position?'Managing position':'Watching'):'Stopped');}
    }
    async function instanceList(){
      try{
        const response=await fetch(isNative?apiBase+'instances':'/api/renko-instances'),data=await response.json();
        if(!response.ok)throw Error(data.error||'Could not load strategies');
        lastInstanceRows=data.instances||[];if(el('stop-all')){const actionable=lastInstanceRows.some(v=>v.running||v.position||v.pending);el('stop-all').disabled=stopAllBusy||!actionable;el('stop-all').style.opacity=stopAllBusy||!actionable?'0.45':'1';el('stop-all').style.cursor=stopAllBusy||!actionable?'not-allowed':'pointer';}syncBatchCharts(lastInstanceRows);el('instances').replaceChildren();
        el('instance-count').textContent=(data.instances||[]).filter(v=>v.running).length+' running · '+(data.instances||[]).length+' saved';
        for(const v of data.instances||[]){
          const selected=v.broker===(isDelta?'DELTA_INDIA':'FYERS')&&(v.instance_key||'default')===instanceId;
          const card=document.createElement('article');card.className='renko-instance-card'+(selected?' is-selected':'');
          const top=document.createElement('div');top.className='renko-instance-top';
          const broker=document.createElement('span');broker.className='renko-broker-tag';broker.textContent=v.broker==='MOTILAL_OSWAL'?'Motilal Oswal':v.broker==='DHAN'?'Dhan':v.broker==='DELTA_INDIA'?'Delta India':'FYERS';
          const state=document.createElement('span');state.className='renko-state-tag'+(v.pending?' pending':v.running?' live':'');state.textContent=v.pending?'Order pending':v.running?(v.position?'Managing position':'Watching'):v.position?'Monitoring paused':'Stopped';top.append(broker,state);card.append(top);
          const title=document.createElement('h4');title.className='renko-instance-title';title.textContent=v.instrument||v.config?.underlying||'New strategy';card.append(title);
          const meta=document.createElement('div');meta.className='renko-instance-meta';meta.textContent=(v.config?.mode||'Paper')+' · '+(v.config?.timeframe||'Choose timeframe')+(selected?' · Viewing':'');card.append(meta);
          const values=document.createElement('div');values.className='renko-instance-values';
          for(const [label,value] of [['Open P&L · gross',v.position?(v.pnl?.available&&v.stream?.connected?(v.broker==='DELTA_INDIA'?root.DeltaINR.format(v.pnl.unrealized,v.pnl_currency||'USD'):Number(v.pnl.unrealized).toFixed(2)+' INR'):'Unavailable'):'—'],['Entries used',String(v.trades_used||0)+(v.config?.max_trades?' / '+v.config.max_trades:'')]]){const item=document.createElement('div'),small=document.createElement('small'),b=document.createElement('b');small.textContent=label;b.textContent=value;item.append(small,b);values.append(item);}card.append(values);
          const held=document.createElement('p');held.className='renko-small';held.textContent=v.position?v.position.symbol+' · '+v.position.quantity+' units':v.pending?'Waiting for broker confirmation':'No open position';card.append(held);
          const footer=document.createElement('div');footer.className='renko-instance-footer';const view=document.createElement('a');const url=new URL(location.href);url.searchParams.set('renkoBroker',v.broker);url.searchParams.set('renkoInstance',v.instance_key||'default');view.href=url;view.textContent=selected?'Current view':'View settings & chart';footer.append(view);
          if(v.running||v.position||v.pending){const button=document.createElement('button');button.className='renko-quiet-button stop';button.type='button';button.textContent='Stop & close';button.onclick=async()=>{button.disabled=true;try{const endpoint=(['DHAN','MOTILAL_OSWAL'].includes(v.broker)?apiBase:v.broker==='DELTA_INDIA'?'/api/renko-delta/':'/api/renko-supertrend/')+'stop?instance='+encodeURIComponent(v.instance_key||'default');const result=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const body=await result.json();if(!result.ok)throw Error(body.error);await instanceList();}catch(e){el('broker-note').textContent=e.message;}finally{button.disabled=false;}};footer.append(button);}card.append(footer);el('instances').append(card);
        }
      }catch(error){el('broker-note').textContent='Strategies unavailable: '+error.message;}
    }
    el('new-instance').onclick=async()=>{try{if(!el('symbol').value)throw Error('Select an instrument first.');const r=await fetch('/api/renko-instances/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({broker:isDelta?'DELTA_INDIA':'FYERS',underlying:el('symbol').value})});const d=await r.json();if(!r.ok)throw Error(d.error);const u=new URL(location.href);u.searchParams.set('renkoBroker',isDelta?'DELTA_INDIA':'FYERS');u.searchParams.set('renkoInstance',d.instance_key);location.href=u;}catch(e){el('broker-note').textContent=e.message;}};
    instanceList();setInterval(instanceList,5000);
    el('new-instance').closest('.renko-launch').insertAdjacentHTML('afterend','<div class="renko-batch-area"><label class="field">Selected instruments<select id="renko-batch-symbols" multiple size="4" aria-describedby="renko-batch-help"></select><small id="renko-batch-help" class="renko-small">Add choices above, then select instruments to start.</small></label><div><button id="renko-add-batch" class="renko-quiet-button" type="button">Add displayed instrument</button><button id="renko-start-selected" class="button" type="button">Start selected · PAPER</button></div></div><p id="renko-batch-result" role="status">Each selected instrument runs independently with its own trade limit.</p>');
    const batchStorage=(isEngine?'sector-pulse:renko-engine-batch-selection:':'sector-pulse:renko-batch-selection:')+selectedBroker+(isNative?':'+dhanAccount:'');
    function syncDisplayedChartSelection(){
      if(isBatchChartView)return;
      const select=el('batch-symbols'),symbol=el('symbol').value;
      if(!select||!symbol)return;
      const selected=chartSelectionForInstrument(symbol,Array.from(select.selectedOptions).map(o=>o.value));
      for(const value of selected)if(!Array.from(select.options).some(o=>o.value===value))select.add(new Option(value,value));
      for(const option of select.options)option.selected=selected.includes(option.value);
      saveBatchSelection();syncBatchCharts(lastInstanceRows);
    }
    function saveBatchSelection(){try{localStorage.setItem(batchStorage,JSON.stringify(Array.from(el('batch-symbols').options).map(o=>({symbol:o.value,selected:o.selected}))));}catch{}}
    try{for(const item of JSON.parse(localStorage.getItem(batchStorage)||'[]'))if(typeof item.symbol==='string')el('batch-symbols').add(new Option(item.symbol,item.symbol,false,item.selected===true));}catch{}
    el('batch-symbols').addEventListener('change',()=>{saveBatchSelection();controls();syncBatchCharts(lastInstanceRows);});
    el('add-batch').onclick=()=>{const symbol=el('symbol').value;if(symbol){const existing=Array.from(el('batch-symbols').options).find(o=>o.value===symbol);if(existing)existing.selected=true;else el('batch-symbols').add(new Option(symbol,symbol,true,true));saveBatchSelection();controls();syncBatchCharts(lastInstanceRows);}};
    el('mode').addEventListener('change',()=>el('start-selected').textContent='Start selected · '+el('mode').value);
    el('start-selected').onclick=async()=>{
      el('start-selected').disabled=true;
      const original=values();
      const restoreFields=fields=>{if(fields.symbol&&!Array.from(el('symbol').options).some(o=>o.value===fields.symbol))el('symbol').add(new Option(fields.symbol,fields.symbol));for(const id of allIds)if(Object.hasOwn(fields,id)){if(el(id).type==='checkbox')el(id).checked=fields[id]===true;else el(id).value=fields[id];}controls();};
      try{
        const instruments=Array.from(el('batch-symbols').selectedOptions).map(o=>o.value),plans=[];
        for(const symbol of instruments){restoreFields({...original,symbol});await confirmStartConfiguration();plans.push({symbol,settings:requireRsiHtfSupport(payload(),lastRunner)});}
        restoreFields(original);await root.PaperCapital?.ensure(original.mode);
        const results=[];
        for(const plan of plans){const r=await fetch('/api/renko-instances/start-selected',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:crypto.randomUUID(),broker:selectedBroker,instruments:[plan.symbol],settings:plan.settings})});const d=await r.json();if(!r.ok)throw Error(d.error);results.push(...d.results);}
        el('batch-result').textContent=results.map(v=>v.instrument+': '+v.status+(v.error?' · '+v.error:'')).join(' | ');await instanceList();
        const viewed=results.find(v=>v.instrument===original.symbol&&['STARTED','ALREADY_RUNNING'].includes(v.status))||results.find(v=>['STARTED','ALREADY_RUNNING'].includes(v.status));
        if(viewed?.instance_key){const u=new URL(location.href);u.searchParams.set('renkoBroker',selectedBroker);u.searchParams.set('renkoInstance',viewed.instance_key);location.assign(u.href);}
      }catch(e){el('batch-result').textContent=e.message;}finally{restoreFields(original);el('start-selected').disabled=false;}
    };

    if(isDelta){el('delta-execution-field').parentElement.closest('details').before(el('delta-execution-field'));for(const option of Array.from(el('timeframe').options))if(['2 minutes','10 minutes'].includes(option.value))option.remove();el('search').placeholder='BTCUSD, ETHUSD…';el('mode').options[1].text='Live — real Delta India orders';el('lots').closest('label').firstChild.textContent='Whole option contracts';for(const id of ['spot-target','spot-stop'])el(id).closest('label').firstChild.textContent=id==='spot-target'?'Hard target · native underlying quote points (optional)':'Hard stop · native underlying quote points (optional)';for(const id of ['max-premium','daily-budget'])el(id).closest('label').firstChild.textContent=id==='max-premium'?'Premium cap · native quote currency (optional)':'Daily loss budget · native quote currency (optional)';el('provisional-status').textContent='Delta trades seven days. Daily cutoff is explicit; product expiry remains authoritative. Fresh backend WebSocket candles are required for intrabar signals.';section.querySelectorAll('p').forEach(p=>{if(p.textContent.includes('Wall-clock square-off'))p.textContent=p.textContent.replace(/Wall-clock square-off.*?No same-candle re-entry\./,'Daily square-off follows your selected IST cutoff; no same-candle re-entry.');if(p.textContent.includes('brokerage, statutory'))p.textContent='Native contract units and currency; gross P&L uses fills and fresh executable bid. Trading-fee estimates include 18% estimated GST. Options apply the 3.5% premium fee cap; perpetuals use product taker rates on fill notional. Perpetual funding and liquidation costs remain unavailable; all-in net P&L is unknown. INR display uses Delta’s verified fixed settlement conversion; native calculation units are retained.';});}
    const executionPanel=el('toggle').closest('section.panel');
    executionPanel.id='renko-runner-panel';
    el('chart-stack').insertAdjacentElement('afterend',executionPanel);
    const adoptionPanel=document.createElement('section');adoptionPanel.className='panel';adoptionPanel.style.marginTop='16px';
    adoptionPanel.innerHTML='<h2>Attach existing FYERS positions to this strategy</h2><p>Refresh open broker positions, select your filled option position for this underlying, then attach it to the visible strategy. The strategy starts monitoring and can SELL to exit when its configured exit rules trigger. No new entry is placed when attaching. Unfilled or pending orders cannot be attached.</p><button id="renko-broker-refresh" class="button" type="button">Refresh FYERS positions and orders</button><label style="display:flex;align-items:center;gap:8px;margin:14px 0"><input id="renko-adoption-reentry" type="checkbox" style="width:16px;height:16px">Allow new entries after the attached position exits (optional)</label><div id="renko-broker-positions"></div><button id="renko-adopt" class="button" type="button" disabled>Attach selected positions · enable LIVE strategy exits</button><p id="renko-adoption-status" role="status">Refresh to load broker-confirmed exposure. No position selected.</p><div id="renko-adopted-managers" style="overflow-x:auto"></div><h3>Broker order book · acceptance is not a fill</h3><div id="renko-broker-orders" style="overflow-x:auto"></div>';
    executionPanel.insertAdjacentElement('afterend',adoptionPanel);if(isDelta){adoptionPanel.innerHTML=adoptionPanel.innerHTML.replaceAll('FYERS','Delta India').replaceAll('long MARGIN options','long Delta options');executionPanel.querySelector('.label').textContent='DELTA INDIA EXECUTION';}

    const style=document.createElement('style');style.textContent=`#renko-chart-stack{display:flex!important;flex-direction:column!important;min-width:0;width:100%;box-sizing:border-box}#renko-chart-toolbar{min-width:0;max-width:100%;box-sizing:border-box;position:sticky;top:0;z-index:20;background:#131722}#renko-chart-scroll-body{min-width:0;width:100%;box-sizing:border-box}#renko-chart{position:relative;background:#131722;border:1px solid #2a2e39;border-radius:4px;min-height:480px}#renko-candle-readout{font:12px ui-monospace,SFMono-Regular,monospace;color:#d1d4dc;min-height:20px;margin-top:14px}#renko-chart-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}#renko-live-pnl{position:absolute;top:10px;left:12px;z-index:5;display:flex;gap:8px 22px;flex-wrap:wrap;max-width:calc(100% - 110px);background:rgba(19,23,34,.93);border:1px solid #394150;border-radius:5px;padding:10px 14px;color:#d1d4dc;font-variant-numeric:tabular-nums;pointer-events:none;box-shadow:0 2px 8px #0003}#renko-live-pnl small{display:block;color:#9598a1;font-size:10px;margin-bottom:2px}#renko-live-pnl b{font-size:17px}#renko-live-pnl .pnl-context{flex-basis:100%;font-size:14px;line-height:1.4}#renko-sideways-status{position:absolute;bottom:50px;left:12px;z-index:5;color:#d1d4dc;background:#131722e8;padding:6px 9px;border:1px solid #394150;border-radius:4px;font-size:11px;pointer-events:none}#renko-live-pnl .pnl-group{display:flex;flex-wrap:wrap;gap:4px 18px}#renko-live-pnl .pnl-group-title{flex-basis:100%;font-size:11px;color:#d1d4dc}#renko-exit-fullscreen{position:absolute;right:85px;bottom:48px;z-index:8}#renko-chart-stack:not(:fullscreen) #renko-exit-fullscreen{display:none}#renko-chart-stack:fullscreen{display:flex;flex-direction:column;width:100vw;height:100vh;box-sizing:border-box;padding:8px;background:#131722;overflow:hidden}#renko-chart-stack:fullscreen #renko-chart{flex:1;min-height:220px;height:auto!important;margin-top:0!important}#renko-chart-stack:fullscreen section[aria-label="RSI zone indicator"]{flex:none;height:215px}#renko-stream-status{font-size:18px;font-weight:700;color:#f1bb66;padding:8px 12px;border:1px solid currentColor;border-radius:6px;line-height:1.5}#renko-stream-status::before{content:"";display:inline-block;width:9px;height:9px;border-radius:50%;background:currentColor;margin-right:8px;vertical-align:middle}#renko-stream-status[data-live="true"]::before{background:#68e6a3;box-shadow:0 0 5px #68e6a3,0 0 12px #68e6a399;animation:renko-led-pulse 3s ease-in-out infinite}@keyframes renko-led-pulse{50%{box-shadow:0 0 8px #68e6a3,0 0 18px #68e6a3aa}}#renko-stream-status[data-live="true"]{color:#68e6a3;background:#123529;font-weight:700;animation:renko-feed-pulse 3s ease-in-out infinite}@keyframes renko-feed-pulse{50%{box-shadow:0 0 0 3px #68e6a322}}@media(prefers-reduced-motion:reduce){#renko-stream-status[data-live="true"],#renko-stream-status[data-live="true"]::before{animation:none}}`;style.textContent+=`#renko-chart-mode-state{font-size:18px;font-weight:700;line-height:1.5}#renko-chart-toolbar{flex:none}#renko-chart-toggle{min-width:130px}#renko-config-state{flex-basis:100%;font-size:11px;color:#b9c9e2}#renko-chart-action-error{flex-basis:100%;color:#f1bb66}.renko-configuration-tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}.renko-config-name{display:flex;align-items:center;gap:6px;font-size:11px}.renko-config-name input{max-width:160px;padding:6px}#renko-chart-stack:fullscreen #renko-chart-toolbar{margin-top:0;padding:6px;max-height:25vh;overflow:auto}#renko-chart-stack:fullscreen #renko-chart{min-height:80px}@media(max-width:760px){#renko-chart-toolbar{gap:6px}#renko-chart-toolbar button{font-size:11px;padding:7px}.renko-config-name{flex-basis:100%}}`;style.textContent+='#renko-chart-toolbar{align-items:center;min-width:0}#renko-stream-status{flex:0 1 auto;min-width:280px;max-width:100%;box-sizing:border-box;min-height:42px;white-space:normal;padding:7px 12px;font-size:18px;font-weight:700}#renko-stream-status[data-live="true"]{animation:none}#renko-chart-toolbar>button,#renko-chart-toolbar>label{flex-shrink:0}#renko-override-note{flex-basis:100%;font-size:11px}#renko-supertrend .renko-rsi-readout{font-variant-numeric:tabular-nums;min-height:20px}@media(max-width:760px){#renko-stream-status{flex:0 0 100%;width:100%;min-width:0;max-width:100%}}';document.head.append(style);
    el('chart').insertAdjacentHTML('beforebegin','<div id="renko-chart-toolbar"><button id="renko-reset-chart" class="button" type="button">Latest bars</button><button id="renko-readable-chart" class="button" type="button">Reset view</button><button id="renko-fit-chart" class="button" type="button">Fit history</button><button id="renko-full-chart" class="button" type="button">Full screen</button><span id="renko-stream-status" role="status">Stream connecting…</span><button id="renko-chart-toggle" class="button" type="button" disabled>Loading runner…</button><button id="renko-chart-reconcile-close" class="button secondary" type="button" hidden>Reconcile broker closure</button><label>Entry direction<select id="renko-override-direction" aria-label="Override entry direction"><option value="">Choose direction</option><option value="BULLISH">Bullish</option><option value="BEARISH">Bearish</option></select></label><button id="renko-override-entry" class="button" type="button" disabled>Override Entry</button><span id="renko-override-note" role="status">Strategy exits manage the entered position.</span><label class="renko-config-name">Configuration name<span class="renko-config-combo"><input id="renko-config-name" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="renko-config-options" autocomplete="off" maxlength="80" placeholder="Type or select saved name"><button id="renko-config-dropdown" type="button" aria-label="Show saved configurations">▾</button><div id="renko-config-options" role="listbox" aria-label="Saved configurations" hidden></div></span></label><button id="renko-save-settings" class="button" type="button">Save settings</button><button id="renko-export-settings" class="button" type="button">Download settings .txt</button><span id="renko-config-state" role="status">Draft settings · save status loading</span><span id="renko-chart-action-error" role="alert" hidden></span></div>');
    el('chart').insertAdjacentHTML('beforeend','<div id="renko-live-pnl" aria-live="polite" aria-label="Live option profit and loss"></div><div id="renko-sideways-status">Sideways filter off</div><button id="renko-exit-fullscreen" class="button" type="button">Exit fullscreen · Esc</button>');
    el('exit-fullscreen').onclick=()=>document.exitFullscreen();
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&document.fullscreenElement===el('chart-stack'))document.exitFullscreen();});
    el('chart').style.height='480px';
    const exportLink=section.querySelector('a[download="renko-option-journal.json"]');exportLink.href=apiBase+'journal.xlsx?instance='+encodeURIComponent(instanceId);exportLink.download='renko-trading-journal.xlsx';exportLink.textContent='Export board-ready Excel';
    // Move existing controls rather than duplicate them: handlers and saved settings keep their IDs.
    const workspace=el('workspace'),launch=document.createElement('div');launch.className='renko-compact-launch';
    workspace.querySelector('.renko-workspace-head').after(launch);
    launch.insertAdjacentHTML('beforeend','<label class="field">Market<select id="renko-market"></select></label>');
    launch.insertAdjacentHTML('beforeend','<label class="field" id="renko-cash-product-field" hidden>Holding<select id="renko-cash-product"><option value="INTRADAY">Intraday</option><option value="CNC">Carry forward (overnight)</option></select></label>');
    launch.insertAdjacentHTML('beforeend','<label class="field" id="renko-commodity-holding-field" hidden>Holding<select id="renko-commodity-holding"><option value="INTRADAY">Intraday</option><option value="CARRY_FORWARD">Carry forward (overnight)</option></select></label>');
    el('broker-note').insertAdjacentHTML('afterend','<p id="renko-cash-note" class="renko-small" hidden></p>');
    for(const [value,label] of (isDelta?[['CRYPTO','Crypto · Delta perpetual signals']]:[['ALL','All FYERS markets'],['NSE_INDEX','NSE indices'],['BSE_INDEX','BSE indices'],['NSE_EQUITY','NSE cash equity'],['BSE_EQUITY','BSE cash equity'],['NSE_STOCK','NSE stock options'],['BSE_STOCK','BSE stock options'],['MCX','MCX commodities']]))el('market').add(new Option(label,value));
    if(isMotilal){for(const option of Array.from(el('market').options))option.textContent=option.textContent.replace('FYERS','Motilal Oswal');}
    if(isDhan){
      for(const option of Array.from(el('market').options)){
        option.textContent=option.textContent.replace('FYERS','Dhan');
        if(['CRYPTO','NSE_EQUITY','BSE_EQUITY'].includes(option.value))option.disabled=true;
      }
    }
    for(const id of ['search','symbol','timeframe','mode','lots','paper-capital','max-trades'])launch.append(el(id).closest('label'));
    if(isDelta)launch.append(el('delta-execution-field'));
    launch.append(el('add-batch'),el('start-selected'));
    const killButton=document.createElement('button');killButton.id='renko-stop-all';killButton.type='button';killButton.disabled=true;killButton.className='renko-quiet-button stop';killButton.textContent='Stop all Renko · close positions';killButton.title='Stops FYERS and Delta default and batch runners, closes their owned Paper/Live positions, and disables new Telegram Paper entries.';launch.append(killButton);const killResult=document.createElement('p');killResult.id='renko-stop-all-result';killResult.textContent='Stops every FYERS and Delta Renko runner and closes owned positions. Progress and results appear here.';killResult.setAttribute('role','status');killResult.setAttribute('aria-live','polite');killResult.style.cssText='margin:8px 0;color:#e6b1b1;font-size:13px;white-space:pre-line';launch.after(killResult);
    killButton.onclick=async()=>{stopAllBusy=true;killButton.disabled=true;killButton.textContent='Stopping all Renko…';el('start-selected').disabled=true;killResult.textContent='Stopping all Renko runners and closing owned positions…';try{const results=await (isEngine?root.RenkoEngine.stopAll(fetch,apiBase):stopAllRenko(fetch));killResult.textContent=results.length?results.map(v=>v.instrument+': '+v.status+(v.error?' · '+v.error:'')).join(' | '):isEngine?'All Engine runners for this broker account are stopped and flat.':'All Renko runners are stopped and flat. New Telegram Paper entries are disabled.';await instanceList();await status();}catch(e){killResult.textContent='Stop all incomplete: '+e.message;}finally{stopAllBusy=false;killButton.disabled=!lastInstanceRows.some(v=>v.running||v.position||v.pending);killButton.style.opacity=killButton.disabled?'0.45':'1';killButton.style.cursor=killButton.disabled?'not-allowed':'pointer';killButton.textContent=isEngine?'Stop all Renko Engine · close positions':'Stop all Renko · close positions';controls();}};
    const batchArea=workspace.querySelector('.renko-batch-area');launch.after(batchArea);
    batchArea.append(el('batch-result'));const saveButton=el('new-instance');workspace.querySelector('.renko-launch').remove();
    const save=document.createElement('div');save.className='renko-save-row';save.append(saveButton);batchArea.append(save);
    const selected=document.createElement('section');selected.className='renko-selected-status';
    selected.innerHTML='<b>Selected instance</b>';
    selected.append(el('toggle'),el('reconcile-close'),el('runner-message'),el('action-error'),el('pnl'),el('paper-funds'),el('trailing-status'),el('status'));
    batchArea.after(selected);
    function disclosure(title,nodes,parent,before){const d=document.createElement('details');d.className='renko-disclosure';const summary=document.createElement('summary');summary.textContent=title;d.append(summary);if(before)parent.insertBefore(d,before);else parent.append(d);d.append(...nodes);return d;}
    const signalPanel=el('atr-length').closest('section.panel');
    const entryFilterGrid=signalPanel.querySelector('.field-grid');
    for(const id of ['sideways-enabled','sideways-max-candles','ema-proximity-enabled','ema-proximity-mode','ema-proximity-distance','ema-momentum-enabled'])entryFilterGrid.append(el(id).closest('label'));
    disclosure('Signal settings · Renko, Supertrend & entry filters',Array.from(signalPanel.children).filter(n=>!n.classList.contains('risk-strip')),signalPanel,signalPanel.firstChild);
    const executionChildren=Array.from(executionPanel.children);
    const grid=executionPanel.querySelector('.field-grid');
    disclosure('Risk & exit settings',executionChildren.filter(n=>n===grid||n.tagName==='P'||n.tagName==='H2'||n.classList.contains('label')),executionPanel,executionPanel.firstChild);
    disclosure('Orders & entry assessment audit',Array.from(executionPanel.children).filter(n=>n.tagName!=='DETAILS'),executionPanel);
    selected.after(signalPanel,executionPanel);executionPanel.classList.add('renko-compact-settings');
    const chartPanel=el('chart-stack').closest('section.panel');
    const historyNodes=[];let historical=false;for(const n of Array.from(chartPanel.children)){if(n.tagName==='H3')historical=true;if(historical)historyNodes.push(n);}
    disclosure('Historical signal events',historyNodes,chartPanel);
    const chartExtras=[el('history-preset').closest('.field-grid'),el('history-range'),el('chart-description'),el('latest-signal'),el('signal-range'),el('anchor')];
    disclosure('Chart history & display details',chartExtras,chartPanel,el('candle-readout'));
    const journalPanel=exportLink.closest('section.panel');disclosure('Trade journal & Excel export',Array.from(journalPanel.children),journalPanel);
    disclosure('Attach open positions & strategy-managed exits',Array.from(adoptionPanel.children),adoptionPanel);
    section.append(chartPanel,adoptionPanel,journalPanel);
    const settingsRow=document.createElement('div');settingsRow.className='renko-settings-row';selected.after(settingsRow);settingsRow.append(signalPanel,executionPanel);
    const executionRail=document.createElement('div');executionRail.className='renko-execution-rail';launch.after(executionRail);
    for(const id of ['mode','lots','paper-capital','max-trades'])executionRail.append(el(id).closest('label'));
    const executionActions=document.createElement('div');executionActions.className='renko-execution-actions';executionActions.append(el('add-batch'),el('new-instance'),el('toggle'));executionRail.append(executionActions);
    el('add-batch').textContent='Add to batch';el('new-instance').textContent='Save instrument';
    const modeNote=document.createElement('p');modeNote.id='renko-mode-note';modeNote.className='renko-small';executionRail.after(modeNote);
    const configurationTools=document.createElement('div');configurationTools.className='renko-configuration-tools';configurationTools.setAttribute('aria-label','Save and export strategy settings');configurationTools.append(el('config-name').closest('label'),el('save-settings'),el('export-settings'),el('config-state'));const namedConfigNote=document.createElement('small');namedConfigNote.id='renko-named-config-note';namedConfigNote.setAttribute('role','status');namedConfigNote.textContent='Saved names are stored in this browser · loading keeps your selected execution mode.';configurationTools.append(namedConfigNote);const deleteConfigButton=document.createElement('button');deleteConfigButton.id='renko-delete-configuration';deleteConfigButton.type='button';deleteConfigButton.className='button';deleteConfigButton.textContent='Delete saved configuration';deleteConfigButton.disabled=true;configurationTools.insertBefore(deleteConfigButton,el('export-settings'));settingsRow.after(configurationTools);configurationTools.classList.add('renko-settings-footer');configurationTools.insertBefore(deleteConfigButton,el('config-state'));
    if(isDelta){const schedule=document.createElement('div');schedule.className='renko-configuration-tools';schedule.setAttribute('aria-label','Crypto trading schedule');schedule.append(el('carry-policy').closest('label'),el('session-deadline').closest('label'));modeNote.after(schedule);}
    const batchDisclosure=document.createElement('details');batchDisclosure.className='renko-disclosure renko-batch-disclosure';const batchSummary=document.createElement('summary');batchSummary.id='renko-batch-summary';batchSummary.textContent='Batch selection';batchDisclosure.append(batchSummary);batchArea.before(batchDisclosure);batchDisclosure.append(batchArea);batchArea.append(el('start-selected'));
    const savedDisclosure=document.createElement('details');savedDisclosure.className='renko-disclosure renko-saved-disclosure';const savedSummary=document.createElement('summary');savedSummary.textContent='Active & saved strategies · ';savedSummary.append(el('instance-count'));savedDisclosure.append(savedSummary);workspace.querySelector('.renko-instances-head').before(savedDisclosure);savedDisclosure.append(el('instances'));workspace.querySelector('.renko-instances-head').remove();
    const configFooterStyle=document.createElement('style');configFooterStyle.textContent='.renko-settings-footer{box-sizing:border-box;gap:10px;padding:14px;margin:12px 0;border:1px solid #34445a;border-radius:7px;background:#172132}.renko-settings-footer>label{flex:1 1 240px;min-width:0}.renko-settings-footer .renko-config-combo{flex:1;min-width:0;width:100%;max-width:320px}.renko-settings-footer input{box-sizing:border-box;width:100%;min-width:0;max-width:100%!important}.renko-settings-footer>button{min-height:36px;margin:0}.renko-settings-footer>small{flex-basis:100%;font-size:11px;color:#a7bad4}.renko-settings-footer #renko-delete-configuration{background:transparent;border:1px solid #70535d;color:#e5b3bf}@media(max-width:760px){.renko-settings-footer{padding:11px;gap:8px}.renko-settings-footer>label{flex-basis:100%}.renko-settings-footer>button{flex:1 1 140px}}';document.head.append(configFooterStyle);
    const compactStyle=document.createElement('style');compactStyle.textContent=`
      #renko-supertrend>.head{margin-bottom:10px}#renko-workspace{padding:14px;border-radius:8px;margin-bottom:8px}#renko-workspace h2{font-size:19px;margin:0}#renko-workspace .label{display:none}.renko-workspace-head{align-items:center;gap:12px}#renko-broker-note{font-size:11px;margin:3px 0}.renko-compact-launch{display:grid;grid-template-columns:1fr 1fr 1.4fr .8fr .8fr .6fr .8fr auto auto;gap:8px;align-items:end;margin-top:10px}.renko-compact-launch label{font-size:11px;min-width:0}.renko-compact-launch input,.renko-compact-launch select{width:100%;min-width:0;padding:7px}.renko-batch-area{display:flex;gap:12px;margin-top:8px;align-items:center;flex-wrap:wrap}.renko-batch-area>.field{flex:1;min-width:240px}#renko-batch-symbols{min-height:60px;height:60px;max-height:none}.renko-batch-area>div:empty{display:none}#renko-batch-help{font-size:10px}#renko-batch-result{border:0;padding:0;margin:0!important;flex:1}.renko-save-row{margin-left:auto}.renko-selected-status{display:flex;gap:8px 16px;align-items:center;flex-wrap:wrap;padding:10px 0;border-bottom:1px solid #334154}.renko-selected-status>b{font-size:12px}.renko-selected-status .handoff-status{margin:0;padding:6px;font-size:12px}.renko-selected-status #renko-pnl{font:12px Menlo,monospace}.renko-instances-head{margin:10px 0 6px}.renko-instance-grid{display:block}.renko-instance-card{display:grid;grid-template-columns:130px minmax(150px,1fr) 150px 240px 180px;gap:5px 12px;align-items:center;padding:8px 10px;border-radius:4px;margin:4px 0}.renko-instance-top{margin:0;gap:5px;flex-wrap:wrap}.renko-instance-title{font-size:13px;margin:0}.renko-instance-meta{font-size:10px}.renko-instance-values{margin:0;gap:8px}.renko-instance-values b{font-size:12px}.renko-instance-values small{font-size:9px}.renko-instance-card>p{display:none}.renko-instance-footer{border:0;padding:0;justify-content:flex-end}.renko-instance-footer a{font-size:11px}.renko-quiet-button{padding:6px 9px}.renko-disclosure{border-top:1px solid #334154;padding:8px 0}.renko-disclosure summary{font-size:12px;font-weight:600;cursor:pointer;color:#b9c9e2}.renko-disclosure[open]>summary{margin-bottom:12px}#renko-supertrend>.panel:not(#renko-workspace){padding:12px;margin-top:8px!important}#renko-supertrend .field-grid{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}#renko-supertrend h2{font-size:18px}#renko-supertrend .risk-strip{margin:6px 0}#renko-supertrend .risk-strip b{font-size:15px}#renko-supertrend .risk-strip small{font-size:10px}#renko-runner-panel{margin-top:0!important}.renko-settings-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.renko-settings-row>.panel{padding:6px!important;background:transparent;border:0;box-shadow:none}.renko-settings-row .risk-strip{padding:0;gap:5px}.renko-settings-row .risk-strip>div{padding:5px}.renko-settings-row:has(details[open]){grid-template-columns:1fr}.renko-batch-area #renko-batch-result{font-size:11px}.renko-instance-card{grid-template-columns:130px minmax(150px,1fr) 140px 210px 170px}#renko-policy{margin-top:8px;padding-top:8px}#renko-chart{min-height:360px;height:clamp(360px,42vw,620px)!important}#renko-rsi-chart{height:130px!important}#renko-chart-stack:fullscreen #renko-rsi-chart{height:170px!important}#renko-supertrend .risk-strip>div{min-width:0}#renko-supertrend .risk-strip b{overflow-wrap:anywhere;font-size:12px}#renko-chart-stack:fullscreen #renko-chart{height:auto!important}.renko-disclosure summary:focus-visible{outline:2px solid #719fe8;outline-offset:3px}@media(max-width:1200px){.renko-compact-launch{grid-template-columns:repeat(4,minmax(0,1fr))}.renko-instance-card{grid-template-columns:110px minmax(120px,1fr) 120px 190px}.renko-instance-footer{grid-column:2/-1}.renko-instance-values{grid-column:4}}@media(max-width:760px){.renko-settings-row{grid-template-columns:1fr}.renko-compact-launch{grid-template-columns:repeat(2,minmax(0,1fr))}.renko-instance-card{grid-template-columns:90px minmax(0,1fr)}.renko-instance-meta{grid-column:2}.renko-instance-values{grid-column:1/-1}.renko-instance-footer{grid-column:1/-1}.renko-workspace-head{flex-direction:row}.renko-broker-field{min-width:120px}.renko-selected-status{align-items:flex-start}}
    `;document.head.append(compactStyle);
    const uxStyle=document.createElement('style');uxStyle.textContent=`
      #renko-supertrend>.head h1{font:650 24px/1.25 'Avenir Next',Arial,sans-serif;letter-spacing:-.5px}#renko-supertrend>.head .label{display:none}#renko-supertrend>.head{margin-bottom:8px}#renko-workspace{background:#172132;border-color:#34445a;padding:12px 14px}#renko-workspace h2{font-size:16px}#renko-broker-note{margin:2px 0!important}.renko-workspace-head{gap:10px}.renko-broker-field{min-width:160px}#renko-workspace .renko-compact-launch{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.renko-compact-launch>.field{flex:1 1 130px}.renko-compact-launch>.field:has(#renko-symbol){flex:2 1 220px}.renko-compact-launch>.field:has(#renko-timeframe){flex:0 1 120px}.renko-compact-launch>.field:has(#renko-market){flex:1 1 170px}.renko-compact-launch>.field:has(#renko-cash-product){flex:1 1 185px}.renko-compact-launch [hidden]{display:none!important}
      .renko-execution-rail{display:flex;flex-wrap:wrap;gap:8px;align-items:end;background:#1e2d43;border-left:3px solid #77a4cf;padding:9px 10px;margin-top:10px;border-radius:4px}.renko-execution-rail.is-live{border-left-color:#dfa861}.renko-execution-rail>.field{min-width:0;font-size:11px;flex:0 1 130px}.renko-execution-rail>.field:has(#renko-mode){flex:0 1 210px}.renko-execution-rail input,.renko-execution-rail select{width:100%;padding:7px;min-width:0}.renko-execution-actions{display:flex;gap:8px;align-items:center;margin-left:auto;flex-wrap:wrap}.renko-execution-actions button,#renko-start-selected{white-space:nowrap;font-size:12px;margin:0;width:auto;padding:9px 12px}.renko-execution-rail.is-live #renko-toggle{background:#b9813d;color:#fff}.renko-execution-actions #renko-toggle{min-width:155px}.renko-batch-area>.field{flex:1 1 240px}.renko-batch-area>.renko-save-row{display:none}#renko-batch-result{flex:1 1 180px}.renko-batch-disclosure{margin:0}.renko-selected-status{padding:5px 0;gap:5px 14px;align-items:center}.renko-selected-status>b{display:none}.renko-selected-status #renko-runner-message{padding:0;font-size:11px;flex:1 1 200px}.renko-selected-status #renko-status{flex-basis:100%;padding:0;color:#99b4d0;font-size:11px}.renko-selected-status #renko-pnl{font-size:11px}.renko-selected-status #renko-trailing-status{font-size:11px}.renko-settings-row{margin:4px 0}.renko-settings-row>.panel{padding:0!important}.renko-saved-disclosure{padding:7px 0 0}.renko-saved-disclosure summary{display:list-item}#renko-mode-note{font-size:11px;margin:5px 0!important}#renko-mode-note.is-live{color:#e9ba7c}#renko-cash-note{font-size:11px!important;line-height:1.4!important;margin:4px 0!important;max-width:960px}#renko-supertrend .risk-strip{margin:4px 0}.renko-instance-card{grid-template-columns:110px minmax(140px,1fr) 130px 170px 140px}.renko-instance-footer{grid-column:auto}.renko-instance-values{grid-column:auto}
      @media(max-width:1100px){.renko-execution-actions{margin-left:0;flex:1 1 auto;justify-content:flex-end}.renko-instance-card{grid-template-columns:100px minmax(130px,1fr) 150px}.renko-instance-values{grid-column:2}.renko-instance-footer{grid-column:3}.renko-execution-rail>.field:has(#renko-mode){flex:1 1 170px}}
      @media(max-width:760px){body:has(#renko-supertrend.active) .desk{grid-template-columns:minmax(0,1fr)}body:has(#renko-supertrend.active) .work,body:has(#renko-supertrend.active) .side{min-width:0;max-width:100%;box-sizing:border-box}body:has(#renko-supertrend.active) .renko-workspace-head>div{min-width:0}body:has(#renko-supertrend.active) .side{padding:10px;gap:8px}body:has(#renko-supertrend.active) .side .nav{display:flex;overflow-x:auto;gap:5px}body:has(#renko-supertrend.active) .side .trading-strategies-nav{display:contents}body:has(#renko-supertrend.active) .side .trading-strategies-heading{display:none}body:has(#renko-supertrend.active) .side .nav button{flex:none;white-space:nowrap;padding:8px}body:has(#renko-supertrend.active) .side .brand small{display:none}body:has(#renko-supertrend.active) .side .broker-card{margin:0;padding:8px}#renko-workspace{padding:10px}.renko-compact-launch>.field,.renko-compact-launch>.field:has(#renko-symbol),.renko-compact-launch>.field:has(#renko-market),.renko-compact-launch>.field:has(#renko-timeframe),.renko-compact-launch>.field:has(#renko-cash-product){flex:1 1 calc(50% - 8px);min-width:0}.renko-execution-rail>.field{flex:1 1 calc(50% - 8px)}.renko-execution-rail>.field:has(#renko-mode){flex:1 1 100%}.renko-execution-actions{width:100%;justify-content:stretch;gap:6px}.renko-execution-actions button{flex:1;padding:8px;font-size:11px}.renko-execution-actions #renko-toggle{flex:1 1 100%;min-width:0}.renko-instance-card{grid-template-columns:80px minmax(0,1fr)}.renko-instance-values,.renko-instance-footer{grid-column:1/-1}.renko-instance-meta{grid-column:2}.renko-batch-area{gap:6px}.renko-broker-field{min-width:100px;max-width:120px}}
    `;document.head.append(uxStyle);
    uxStyle.textContent += `#renko-supertrend label:not(.renko-setting-row):has(>input[type="checkbox"]){display:flex;align-items:center;gap:8px}#renko-supertrend input[type="checkbox"]{width:16px;height:16px;min-width:16px;max-width:16px;min-height:16px;max-height:16px;flex:0 0 16px;align-self:center;order:-1;margin:0;padding:0;appearance:auto}`;
    entryFilterGrid.insertAdjacentHTML('afterbegin',`<label class="field">Volume · chart only<input id="renko-volume-enabled" type="checkbox"></label><label class="field">RSI moving average · chart only<input id="renko-rsi-sma-enabled" type="checkbox"></label><label class="field">RSI period<input id="renko-rsi-length" type="number" min="1" max="1000" value="14"></label><label class="field">Renko Supertrend<input id="renko-supertrend-enabled" type="checkbox" checked></label><label class="field">EMA 10 · first EMA<input id="renko-ema-fast-enabled" type="checkbox" checked></label><label class="field">First EMA period<input id="renko-ema-fast-length" type="number" min="1" max="1000" value="10"></label><label class="field">EMA 30 · second EMA<input id="renko-ema-slow-enabled" type="checkbox" checked></label><label class="field">Second EMA period<input id="renko-ema-slow-length" type="number" min="1" max="1000" value="30"></label><label class="field">EMA 100 · third EMA<input id="renko-ema-third-enabled" type="checkbox" checked></label><label class="field">Third EMA period<input id="renko-ema-third-length" type="number" min="1" max="1000" value="100"></label><label class="field">EMA gap widening<input id="renko-ema-widening-enabled" type="checkbox" checked></label>`);
        const antiChopPanel=document.createElement('details');antiChopPanel.className='renko-disclosure renko-anti-chop';antiChopPanel.id='renko-anti-chop-panel';antiChopPanel.open=true;
    antiChopPanel.innerHTML='<summary>Anti-chop entry filter <span class="renko-anti-chop-badge" id="renko-anti-chop-badge">Off</span></summary><div class="renko-anti-chop-body"><label class="field">Enable anti-chop filter<input id="renko-anti-chop-enabled" type="checkbox"></label><label class="field">Entry role<select id="renko-anti-chop-role"><option value="Filter">Filter another entry signal</option><option value="Entry">Generate checklist entries</option></select></label><label class="field">Confirmation rule<select id="renko-anti-chop-combination"><option value="All">All four checks</option><option value="Trend">Slope + separation + either ATR or structure</option></select></label><label class="field">Threshold mode<select id="renko-anti-chop-mode"><option>Adaptive</option><option>Manual</option></select></label><p id="renko-anti-chop-status" class="muted" role="status">Checking filter availability…</p><p class="muted">Completed candles only. All-four mode requires every check. Trend mode requires slope and EMA separation, plus either ATR or candle structure. ATR above its average, fast EMA slope, fast/slow EMA separation, and clean directional candle structure. All periods below are configurable. Follows the selected chart and runner timeframe; the historical study covered five-minute Nifty only. Filter mode gates other entry signals. Entry mode generates bullish or bearish signals when the selected confirmation rule passes; use it with other entry rules disabled. Exit rules stay separate.</p><div class="field-grid"><label class="field">ATR period<input id="renko-anti-chop-atr-length" type="number" min="1" max="100" step="1" value="14"></label><label class="field">ATR average period<input id="renko-anti-chop-atr-average-length" type="number" min="1" max="200" step="1" value="20"></label><label class="field">Fast EMA period<input id="renko-anti-chop-ema-fast-length" type="number" min="1" max="500" step="1" value="20"></label><label class="field">Slow EMA period<input id="renko-anti-chop-ema-slow-length" type="number" min="2" max="1000" step="1" value="50"></label><label class="field">Adaptive lookback · observations<input id="renko-anti-chop-adaptive-window" type="number" min="20" max="2000" step="1" value="200"></label><label class="field">Slope threshold · percentile<input id="renko-anti-chop-slope-percentile" type="number" min="1" max="99" step="1" value="60"></label><label class="field">Separation threshold · percentile<input id="renko-anti-chop-gap-percentile" type="number" min="1" max="99" step="1" value="60"></label><label class="field">Overlap ceiling · percentile<input id="renko-anti-chop-overlap-percentile" type="number" min="1" max="99" step="1" value="40"></label><label class="field">Fast EMA slope lookback · candles<input id="renko-anti-chop-slope-bars" type="number" min="1" max="50" step="1" value="3"></label><label class="field">Manual minimum directional slope · ATR<input id="renko-anti-chop-slope-atr" type="number" min="0" max="10" step="0.01" value="0.15"></label><label class="field">Manual minimum EMA separation · ATR<input id="renko-anti-chop-gap-atr" type="number" min="0" max="10" step="0.01" value="0.20"></label><label class="field">No EMA cross during latest · candles<input id="renko-anti-chop-cross-bars" type="number" min="1" max="100" step="1" value="6"></label><label class="field">Directional structure · candles<input id="renko-anti-chop-structure-bars" type="number" min="2" max="20" step="1" value="3"></label><label class="field">Manual maximum average overlap · %<input id="renko-anti-chop-overlap-percent" type="number" min="0" max="100" step="1" value="50"></label></div><small class="muted">Adaptive thresholds use only prior completed observations; the current candle cannot change its own threshold. The lookback and percentiles are configurable; this is rolling calibration, not profit optimization. Manual values are used only in Manual mode. Bullish structure requires higher highs and higher lows; bearish requires lower highs and lower lows. Overlap is measured against the smaller adjacent candle range. Saved values apply on the next Start.</small></div>';
    const antiAdvanced=document.createElement('details');antiAdvanced.className='renko-disclosure';const antiAdvancedTitle=document.createElement('summary');antiAdvancedTitle.textContent='Calibration settings and manual overrides';antiAdvanced.append(antiAdvancedTitle,antiChopPanel.querySelector('.field-grid'));antiChopPanel.querySelector('.renko-anti-chop-body').insertBefore(antiAdvanced,antiChopPanel.querySelector('small'));
    signalPanel.append(antiChopPanel);
    const antiChopStyle=document.createElement('style');antiChopStyle.textContent='.renko-anti-chop{margin-top:12px;border-top:1px solid #34445a;padding:12px 0}.renko-anti-chop>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;font-weight:600;cursor:pointer}.renko-anti-chop-badge{padding:3px 9px;border:1px solid #46556c;border-radius:4px;color:#a7bad4;font-size:11px}.renko-anti-chop-body{padding:12px 0 4px}.renko-anti-chop-body p{font-size:12px;line-height:1.6;margin:8px 0}.renko-anti-chop-body small{display:block;line-height:1.6}#renko-supertrend #renko-anti-chop-panel .field-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px 20px;margin-top:14px}#renko-supertrend #renko-anti-chop-panel label.field{min-width:0;font-size:12px;line-height:1.5}#renko-supertrend #renko-anti-chop-panel .field-grid label.field{display:flex;flex-direction:column;align-items:stretch;gap:7px;padding:0;border:0}#renko-supertrend #renko-anti-chop-panel input[type=number]{box-sizing:border-box;width:100%;max-width:none;min-height:36px;margin:0}#renko-supertrend #renko-anti-chop-panel select{max-width:320px}#renko-supertrend #renko-anti-chop-panel small{margin-top:14px}@media(max-width:1100px){#renko-supertrend #renko-anti-chop-panel .field-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){#renko-supertrend #renko-anti-chop-panel .field-grid{grid-template-columns:minmax(0,1fr)}}';document.head.append(antiChopStyle);
    const signalIds=['supertrend-slope-enabled','supertrend-slope-bars','supertrend-slope-min-atr',...ANTI_CHOP_IDS,'zone-entry-enabled','zone-entry-min-atr','zone-entry-rearm','calibrated-enabled','calibrated-overlap-pairs','calibrated-overlap-max','calibrated-stop-atr','calibrated-target-atr',...RSI_HTF_IDS,'manual-trend-enabled','manual-trend-bullish','manual-trend-bearish','manual-trend-closes',...Object.keys(FAMILY_RULES).map(name=>name+'-family-enabled'),'rsi-level-enabled','rsi-level-mode','rsi-bullish-min','rsi-bullish-max','rsi-bearish-min','rsi-bearish-max','rsi-bullish-above','rsi-bearish-below','rsi-length','supertrend-enabled','ema-fast-enabled','ema-slow-enabled','ema-third-enabled','ema-widening-enabled','ema-fast-length','ema-slow-length','ema-third-length',...(isDelta?['session-deadline','price-source','order-terms','carry-policy']:[]),'symbol','timeframe','atr-length','factor','brick-mode','manual-brick','use-adx','adx-threshold','adx-length','adx-smoothing','widening-window','rsi-slope-enabled','intrabar-entries','retest-enabled','retest-engulfing','retest-harami','retest-star'];
    const historyIds=['history-preset','history-from','history-to'];
    el('ema-exit-enabled').closest('label').insertAdjacentHTML('beforebegin',`<fieldset id="renko-indicator-exits" class="renko-setting-group"><legend>Independent indicator exits</legend><p>Each Strategy criterion can close the position independently. Indicator criteria control chart exit simulations and studies. EMA timing follows the intrabar switch. Strategy edits apply on the next Start.</p><label class="field">Supertrend reversal<input id="renko-supertrend-exit-enabled" type="checkbox"></label><label class="field">Second EMA breach<input id="renko-ema-slow-exit-enabled" type="checkbox"></label><label class="field">RSI slope against the position<input id="renko-rsi-exit-enabled" type="checkbox"></label><label class="field">EMA gap contraction<input id="renko-ema-widening-exit-enabled" type="checkbox"></label><label class="field">ADX below the selected threshold<input id="renko-adx-exit-enabled" type="checkbox"></label><label class="field">Opposing confirmed swing structure<input id="renko-market-structure-exit-enabled" type="checkbox"></label></fieldset>`);
    el('ema-exit-enabled').closest('label').insertAdjacentHTML('afterend',`<label class="field">Opposing strong 5m supply/demand target exit · optional<input id="renko-zone-target-enabled" type="checkbox"></label><p id="renko-zone-target-state" class="muted" role="status"></p><label class="field">Directional swing structure entry filter · selected host timeframe<input id="renko-market-structure-enabled" type="checkbox"></label><p id="renko-market-structure-state" class="muted" role="status"></p>`);
    // Settings are rows, not independent label/control/help grid cells. Move the
    // original nodes to preserve values, IDs, disabled state and event bindings.
    function settingRow(label) {
      if(label.classList.contains('renko-setting-row'))return;
      const control=label.querySelector('input,select');if(!control)return;
      const name=document.createElement('span');name.className='renko-setting-name';
      for(const node of Array.from(label.childNodes))if(node.nodeType===3){name.append(node);}
      label.prepend(name);label.classList.add('renko-setting-row');
      label.htmlFor=control.id;
      const text=name.textContent.trim(),split=text.indexOf(' (');
      if(split>0&&text.endsWith(')')&&!text.endsWith('(HTF)')){
        name.textContent=text.slice(0,split);
        const help=document.createElement('small');help.className='renko-setting-help';help.id=control.id+'-help';help.textContent=text.slice(split+2,-1);
        label.append(help);control.setAttribute('aria-describedby',[control.getAttribute('aria-describedby'),help.id].filter(Boolean).join(' '));
      }
    }
    entryFilterGrid.insertAdjacentHTML('beforeend','<label class="field"><input id="renko-higher-timeframe-enabled" type="checkbox"> Higher timeframe check · optional, default OFF<small>Enable explicitly to require completed higher-timeframe direction agreement. Saved choices are retained; edits apply on the next Start.</small></label><label class="field">Supertrend timeframe (HTF)<select id="renko-supertrend-timeframe"><option>5 minutes</option><option>2 minutes</option><option>3 minutes</option><option>10 minutes</option><option>15 minutes</option><option>30 minutes</option><option>1 hour</option></select><small>Dashed Supertrend line; when checked, choose a timeframe higher than the host chart.</small></label>');
    const rsiHtfFrames=isDelta?['3 minutes','5 minutes','15 minutes','30 minutes','1 hour']:['2 minutes','3 minutes','5 minutes','10 minutes','15 minutes','30 minutes','1 hour'];
    for(const [index,slot] of RSI_HTF_SLOTS.entries())entryFilterGrid.insertAdjacentHTML('beforeend','<label class="field">RSI HTF '+slot+' entry check<input id="renko-rsi-htf-'+slot+'-enabled" type="checkbox"><small>Optional · shared RSI period; independent levels below. Defaults copy the main RSI settings. Completed candles only. Applies on next Start.</small></label><label class="field">RSI HTF '+slot+' timeframe<select id="renko-rsi-htf-'+slot+'-timeframe">'+rsiHtfFrames.map(frame=>'<option'+(frame===RSI_HTF_FRAMES[index]?' selected':'')+'>'+frame+'</option>').join('')+'</select><small>Must be higher than the host timeframe; all enabled RSI checks must qualify.</small></label>');
    for(const slot of RSI_HTF_SLOTS)for(const [key,fallback] of Object.entries(RSI_HTF_LEVELS)){
      const id='renko-rsi-htf-'+slot+'-'+key;
      const input=key==='level-mode'?'<select id="'+id+'"><option value="">Use main settings initially</option><option value="BETWEEN">Inclusive range</option><option value="THRESHOLD">Threshold</option></select>':'<input id="'+id+'" type="number" min="0" max="100" step="0.1" placeholder="Copy main RSI">';
      entryFilterGrid.insertAdjacentHTML('beforeend','<label class="field">RSI HTF '+slot+' '+key.replaceAll('-',' ') +input+'</label>');
    }
    const settingGroups=[
      [entryFilterGrid,'Renko & Supertrend',['supertrend-enabled','atr-length','factor','brick-mode','manual-brick']],
      [entryFilterGrid,'EMA indicators',['ema-fast-enabled','ema-fast-length','ema-slow-enabled','ema-slow-length','ema-third-enabled','ema-third-length','ema-widening-enabled','widening-window']],
      [entryFilterGrid,'Entry timing & confirmation',[...RSI_HTF_IDS,'intrabar-entries','rsi-level-enabled','rsi-level-mode','rsi-bullish-min','rsi-bullish-max','rsi-bearish-min','rsi-bearish-max','rsi-bullish-above','rsi-bearish-below','rsi-slope-enabled','rsi-length','rsi-sma-enabled','volume-enabled','market-structure-enabled','higher-timeframe-enabled','supertrend-timeframe']],
      [entryFilterGrid,'ADX filter',['use-adx','adx-threshold','adx-length','adx-smoothing']],
      [entryFilterGrid,'EMA10 retest patterns',['retest-enabled','retest-engulfing','retest-harami','retest-star']],
      [entryFilterGrid,'Entry distance & quick-loss lock',['ema-proximity-enabled','ema-proximity-mode','ema-proximity-distance','ema-momentum-enabled','sideways-enabled','sideways-max-candles']],
      [grid,'Capital & cost limits',['max-premium','daily-budget','additional-slippage-points']],
      [grid,'EMA & zone exits',['ema-exit-enabled','ema-exit-length','zone-target-enabled']],
      [grid,'Trailing stop',['trailing-enabled','trailing-basis','trailing-distance']],
      [grid,'Absolute underlying prices',['spot-target','spot-stop']]
    ];
    for(const [container,title,ids] of settingGroups){
      const group=document.createElement('fieldset');group.className='renko-setting-group';
      const legend=document.createElement('legend');legend.textContent=title;group.append(legend);container.append(group);
      for(const id of ids){const label=el(id).closest('label');settingRow(label);group.append(label);}
    }
    const indicatorExitGroup=el('indicator-exits');
    indicatorExitGroup.insertBefore(el('zone-target-enabled').closest('label'),el('supertrend-exit-enabled').closest('label'));
    for(const group of grid.querySelectorAll('fieldset'))if(group.querySelector('legend')?.textContent==='EMA & zone exits'&&!group.querySelector('input'))group.hidden=true;
    for(const label of indicatorExitGroup.querySelectorAll('label'))settingRow(label);
    indicatorExitGroup.insertBefore(el('ema-exit-enabled').closest('label'),el('ema-slow-exit-enabled').closest('label'));
    indicatorExitGroup.insertBefore(el('ema-exit-length').closest('label'),el('ema-slow-exit-enabled').closest('label'));
    el('ema-exit-enabled').closest('label').querySelector('.renko-setting-name').textContent='EMA breach · configurable exit period';
    const adxDetails=document.createElement('details');adxDetails.innerHTML='<summary>ADX settings</summary>';el('use-adx').closest('fieldset').append(adxDetails);for(const id of ['adx-threshold','adx-length','adx-smoothing'])adxDetails.append(el(id).closest('label'));
    for(const group of entryFilterGrid.querySelectorAll('fieldset')){const title=group.querySelector('legend')?.textContent;if(!['Entry timing & confirmation','ADX filter','EMA10 retest patterns','Entry distance & quick-loss lock'].includes(title))continue;const fold=document.createElement('details');fold.open=true;fold.className='renko-disclosure';const summary=document.createElement('summary');summary.textContent=title;group.before(fold);fold.append(summary,group);group.querySelector('legend').style.cssText='position:absolute;clip:rect(0,0,0,0);width:1px;height:1px;overflow:hidden';}
    for(const [setting,statusId] of [['rsi-slope-enabled','rsi-slope-status'],['retest-enabled','retest-status'],['intrabar-entries','provisional-status'],['zone-target-enabled','zone-target-state'],['market-structure-enabled','market-structure-state']]){
      const help=el(statusId);help.classList.add('renko-setting-help');el(setting).closest('label').append(help);
      el(setting).setAttribute('aria-describedby',[el(setting).getAttribute('aria-describedby'),help.id].filter(Boolean).join(' '));
    }
    // Native selects clip long option captions; repeat the full selection below its row.
    for(const select of section.querySelectorAll('.renko-setting-row>select')){
      const caption=document.createElement('small');caption.className='renko-setting-help';
      select.closest('label').append(caption);
      const update=()=>{const text=select.selectedOptions[0]?.textContent||'';caption.textContent=text.length>24?text:'';select.title=text;};
      select.addEventListener('change',update);new MutationObserver(update).observe(select,{childList:true,subtree:true});update();
    }
    const executionOverview=grid.previousElementSibling;
    if(executionOverview?.tagName==='P')disclosure('Execution behavior & session rules',[executionOverview],grid.parentElement,grid);
    for(const container of [launch,executionRail,workspace.querySelector('.renko-broker-field'),workspace.querySelector('.renko-policy')]){
      if(!container)continue;
      if(container.matches('label'))settingRow(container);else for(const label of container.querySelectorAll('label.field'))settingRow(label);
    }
    const settingsStyle=document.createElement('style');settingsStyle.id='renko-aligned-settings-style';settingsStyle.textContent=`
      #renko-supertrend .renko-settings-row{gap:16px;margin:12px 0}
      #renko-supertrend .renko-settings-row .field-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:18px;margin-top:12px!important;align-items:start}
      #renko-supertrend .renko-setting-group{min-width:0;margin:0;padding:8px 16px 12px;border:1px solid #34445a;border-radius:8px;background:#172132}
      #renko-supertrend .renko-setting-group legend{padding:0 6px;color:#9ebdf1;font:600 13px/1.5 'Avenir Next',Arial,sans-serif}
      #renko-supertrend label.renko-setting-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,48%);align-items:center;gap:6px 16px;margin:0;padding:12px 0;border-bottom:1px solid #34445a;font-size:13px;line-height:1.45;min-width:0}
      #renko-supertrend .renko-setting-group label:last-child{border-bottom:0}
      #renko-supertrend label.renko-setting-row[hidden]{display:none!important}
      #renko-workspace .renko-broker-field{max-width:none;width:100%}
      #renko-supertrend .renko-setting-name{color:#d9e2f0;min-width:0;overflow-wrap:anywhere}
      #renko-supertrend .renko-setting-row>input,#renko-supertrend .renko-setting-row>select{grid-column:2;grid-row:1;width:100%;min-width:0;height:38px;min-height:38px;box-sizing:border-box;padding:8px 10px;font-size:13px;line-height:1.3;align-self:center}
      #renko-supertrend .renko-setting-row>input[type="checkbox"]{order:0;justify-self:start;width:18px;height:18px;min-height:18px;max-height:18px;min-width:18px;max-width:18px;margin:0;padding:0;accent-color:#719fe8}
      #renko-supertrend .renko-setting-row>:is(.renko-setting-help,small){grid-column:1/-1;margin:0;padding:0;color:#9aabc1;font-size:12px;line-height:1.5}
      #renko-supertrend .renko-setting-help:empty{display:none}
      #renko-supertrend .renko-setting-row>:is(input,select):focus-visible{outline:2px solid #9ebdf1;outline-offset:3px}
      #renko-workspace .renko-compact-launch,#renko-supertrend .renko-execution-rail{display:grid;grid-template-columns:minmax(0,1fr);gap:0 24px;align-items:start}
      #renko-workspace .renko-compact-launch .renko-setting-row,#renko-supertrend .renko-execution-rail .renko-setting-row{max-width:none}
      #renko-supertrend .renko-execution-actions{grid-column:1/-1;justify-content:flex-end;margin-top:12px}
      #renko-supertrend .renko-disclosure>summary{font-size:14px;padding:8px 0}
      @media(max-width:1000px){#renko-supertrend .renko-settings-row .field-grid{grid-template-columns:1fr}}
      @media(max-width:760px){#renko-workspace .renko-compact-launch,#renko-supertrend .renko-execution-rail{grid-template-columns:1fr}#renko-supertrend .renko-setting-group{padding:6px 12px 10px}#renko-supertrend label.renko-setting-row{gap:6px 12px;grid-template-columns:minmax(0,1fr) minmax(0,52%)}#renko-supertrend .renko-execution-actions{grid-column:1}}
    `;document.head.append(settingsStyle);
    el('chart-toolbar').insertAdjacentHTML('afterend','<p id="renko-history-health" role="status"></p>');
    // Keep the original execution input in its row; add an independent visual destination.
    for(const id of DESTINATION_RULES){
      const input=el(id),row=input.closest('label'),name=row.querySelector('.renko-setting-name').textContent.trim();
      row.classList.add('renko-destination-row');row.removeAttribute('for');
      input.setAttribute('aria-label',name+' · Strategy');
      const visual=document.createElement('input');visual.type='checkbox';visual.id='renko-'+id+'-indicator';visual.checked=input.checked;visual.setAttribute('aria-label',name+' · Indicator');row.insertBefore(visual,input.nextSibling);
    }
    for(const group of new Set(DESTINATION_RULES.map(id=>el(id).closest('fieldset')))){
      const headings=document.createElement('div');headings.className='renko-destination-headings';headings.innerHTML='<span>Rule</span><span>Strategy</span><span>Indicator</span>';group.querySelector('legend').after(headings);
    }
    const destinationsNote=document.createElement('p');destinationsNote.textContent='Strategy controls automated trading. Indicator controls chart studies and historical signals. Both applies to both; neither disables both. Chart signals are simulations; actual fills remain visible as execution evidence.';entryFilterGrid.prepend(destinationsNote);
    settingsStyle.textContent+=`#renko-supertrend label.renko-destination-row,.renko-destination-headings{display:grid;grid-template-columns:minmax(0,1fr) 80px 80px;gap:6px 12px;align-items:center}.renko-destination-headings{color:#9ebdf1;font-size:12px;text-align:center;padding:8px 0;border-bottom:1px solid #34445a}.renko-destination-headings span:first-child{text-align:left}#renko-supertrend .renko-destination-row>input[type=checkbox]{justify-self:center}#renko-supertrend .renko-destination-row>input[type=checkbox]:nth-of-type(1){grid-column:2}#renko-supertrend .renko-destination-row>input[type=checkbox]:nth-of-type(2){grid-column:3}#renko-supertrend .renko-destination-row>.renko-setting-help{grid-column:1/-1}`;
    const continuationRow=document.createElement('label');continuationRow.className='field';continuationRow.textContent='Allow continuation entries (optional)';
    const continuationInput=document.createElement('input');continuationInput.type='checkbox';continuationInput.id='renko-supertrend-continuation-enabled';continuationRow.append(continuationInput);
    const continuationHelp=document.createElement('small');continuationHelp.textContent='OFF: fresh reversal required in Supertrend-only mode. ON: fresh completed close above both Supertrends for buy, below both for sell. Requires higher-timeframe check; applies on next Start.';continuationRow.append(continuationHelp);entryFilterGrid.append(continuationRow);settingRow(continuationRow);
    for(const [id,title,type,value,min,max,step] of [
      ['supertrend-slope-enabled','Supertrend slope entry filter','checkbox',false],
      ['supertrend-slope-bars','Slope lookback · completed bricks / candles','number',1,1,100,1],
      ['supertrend-slope-min-atr','Minimum slope · ATR per brick / candle','number',0,0,100,0.01]]){
      const row=document.createElement('label');row.className='field';row.textContent=title;
      const input=document.createElement('input');input.id='renko-'+id;input.type=type;
      if(type==='checkbox')input.checked=value;else{input.value=value;input.min=min;input.max=max;input.step=step;}
      row.append(input);
      if(type==='checkbox'){const help=document.createElement('small');help.textContent='Entry only: rising for BUY, falling for SELL; flat values and direction-flip jumps wait. Uses completed observations of the selected strategy basis. Reset Defaults enables this filter.';row.append(help);}
      entryFilterGrid.append(row);settingRow(row);
    }
    const sessionHoursRow=document.createElement('label');sessionHoursRow.className='field';sessionHoursRow.textContent='Trading session hours';sessionHoursRow.title='The trading session interval for a day';
    const sessionHoursInput=document.createElement('input');sessionHoursInput.id='renko-trading-session-hours';sessionHoursInput.type='number';sessionHoursInput.step='any';sessionHoursInput.readOnly=true;sessionHoursInput.title='The trading session interval for a day';sessionHoursInput.setAttribute('aria-label','Trading session hours');sessionHoursInput.placeholder='Awaiting verified session';sessionHoursRow.append(sessionHoursInput);
    const sessionHoursHelp=document.createElement('small');sessionHoursHelp.textContent='Hours per day from the verified broker session.';sessionHoursRow.append(sessionHoursHelp);entryFilterGrid.append(sessionHoursRow);settingRow(sessionHoursRow);
    function paintTradingSessionHours(policy,symbol=el('symbol').value){
      const match=/^(\d{2})(\d{2})-(\d{2})(\d{2})$/.exec(policy?.master_regular_session||'');
      if(match){const start=Number(match[1])*60+Number(match[2]),end=Number(match[3])*60+Number(match[4]);if(start>=0&&start<1440&&end>=0&&end<=1440&&start!==end){const minutes=end>start?end-start:1440-start+end;sessionHoursInput.value=String(minutes/60);sessionHoursInput.dataset.symbol=symbol;sessionHoursHelp.textContent=match[1]+':'+match[2]+'–'+match[3]+':'+match[4]+' IST · broker regular session';return;}}
      if(policy?.seven_day_session&&policy?.session_source==='CONTINUOUS_CRYPTO'){sessionHoursInput.value='24';sessionHoursInput.dataset.symbol=symbol;sessionHoursHelp.textContent='Continuous broker market · 24 hours per day';return;}
      if(sessionHoursInput.dataset.symbol!==symbol){sessionHoursInput.value='';sessionHoursInput.dataset.symbol=symbol;sessionHoursHelp.textContent='Awaiting selected segment’s broker session start and end.';}

    }
    root.addEventListener('message',event=>{
      if(isBatchChartView||event.origin!==location.origin||event.data?.type!=='sector-pulse:renko-session-policy')return;
      const card=[...batchChartFrames.values()].find(card=>card.querySelector('iframe')?.contentWindow===event.source);
      if(!card)return;
      const expected=new URL(card.querySelector('iframe').src).searchParams.get('renkoChartSymbol');
      if(expected!==el('symbol').value||event.data.symbol!==expected)return;
      paintTradingSessionHours(event.data.policy,expected);
    });
    const familyRows={
      supertrend:['supertrend-slope-enabled','supertrend-slope-bars','supertrend-slope-min-atr','supertrend-continuation-enabled','trading-session-hours','supertrend-enabled','atr-length','factor','brick-mode','manual-brick','supertrend-exit-enabled','higher-timeframe-enabled','supertrend-timeframe'],
      ema:['ema-fast-enabled','ema-fast-length','ema-slow-enabled','ema-slow-length','ema-third-enabled','ema-third-length','ema-widening-enabled','widening-window','ema-proximity-enabled','ema-proximity-mode','ema-proximity-distance','ema-momentum-enabled','retest-enabled','retest-engulfing','retest-harami','retest-star','ema-exit-enabled','ema-exit-length','ema-slow-exit-enabled','ema-widening-exit-enabled'],
    rsi:['rsi-level-enabled','rsi-level-mode','rsi-bullish-min','rsi-bullish-max','rsi-bearish-min','rsi-bearish-max','rsi-bullish-above','rsi-bearish-below','rsi-slope-enabled','rsi-length','rsi-sma-enabled','rsi-exit-enabled',...RSI_HTF_IDS],
      adx:['use-adx','adx-threshold','adx-length','adx-smoothing','adx-exit-enabled'],
      structure:['market-structure-enabled','market-structure-exit-enabled'],
      zones:['zone-target-enabled']
    };
    const familyTitles={supertrend:'Renko Supertrend',ema:'EMA',rsi:'RSI',adx:'ADX',structure:'Market structure',zones:'Supply / demand zones'};
    for(const [name,ids] of Object.entries(familyRows)){
      const group=document.createElement('details');group.open=false;group.className='renko-setting-group renko-family-group';group.id='renko-family-'+name;
      const foldKey='sector-pulse:renko-family-fold:'+brokerName+':'+dhanAccount+':'+name;try{group.open=localStorage.getItem(foldKey)==='open';}catch{};group.addEventListener('toggle',()=>{try{localStorage.setItem(foldKey,group.open?'open':'closed');}catch{}});
      group.innerHTML='<summary>'+familyTitles[name]+'</summary><label class="field renko-family-master">Enable '+familyTitles[name]+' strategy rules<input type="checkbox" id="renko-'+name+'-family-enabled" checked></label><p id="renko-'+name+'-family-status" role="status"></p><div class="renko-destination-headings"><span>Rule</span><span>Strategy</span><span>Chart only</span></div>';
      entryFilterGrid.append(group);settingRow(group.querySelector('label'));
      if(name==='structure'||name==='zones')el(name+'-family-enabled').checked=false;
      const moved=new Set();
      for(const id of ids){const row=el(id).closest('label');if(!moved.has(row)){group.append(row);moved.add(row);}}
    }
    const rsiHtfActive=document.createElement('p');rsiHtfActive.id='renko-rsi-htf-active';rsiHtfActive.setAttribute('role','status');el('family-rsi').append(rsiHtfActive);
    const rsiHtfChart=document.createElement('p');rsiHtfChart.id='renko-rsi-htf-chart';rsiHtfChart.setAttribute('role','status');el('rsi-chart').after(rsiHtfChart);
    const manualTrendGroup=document.createElement('details');manualTrendGroup.className='renko-setting-group';manualTrendGroup.id='renko-manual-trend-group';manualTrendGroup.open=false;
    manualTrendGroup.innerHTML='<summary><span>Manual trend filter</span> <label style="margin-left:auto">Enable<input type="checkbox" id="renko-manual-trend-enabled"></label></summary><label class="field">Bullish marker<input id="renko-manual-trend-bullish" type="number" min="0.00000001" step="any"></label><label class="field">Bearish marker<input id="renko-manual-trend-bearish" type="number" min="0.00000001" step="any"></label><label class="field">Consecutive completed closes<input id="renko-manual-trend-closes" type="number" min="1" max="100" step="1" value="2"></label><p>Above bullish marker: bullish entries only. Below bearish marker: bearish entries only. Equal markers allowed; a close at or across a marker resets that count. Uses completed chart-timeframe candles. Other entry rules still apply; exits remain active. Applies on next Start.</p><p id="renko-manual-trend-status" role="status"></p>';
    entryFilterGrid.append(manualTrendGroup);
    manualTrendGroup.querySelector('summary label').addEventListener('click',event=>event.stopPropagation());
    for(const row of manualTrendGroup.querySelectorAll('label'))settingRow(row);
    function syncManualTrendControls(){
      const ready=lastRunner?.manual_trend_revision==='manual-price-marker-consecutive-v1';
      el('manual-trend-enabled').disabled=!ready;
      for(const id of ['manual-trend-bullish','manual-trend-bearish','manual-trend-closes'])el(id).disabled=!ready||!el('manual-trend-enabled').checked;
      const gate=lastRunner?.last_signal?.manual_trend;
      el('manual-trend-status').textContent=!ready?'Backend reload pending; filter unavailable.':el('manual-trend-enabled').checked?'Next Start: ON · '+(gate?.enabled?JSON.stringify(gate.counts)+' / '+gate.required:'runner settings unchanged until Start'):'Next Start: OFF · saved markers retained.';
    }
    el('manual-trend-enabled').addEventListener('change',syncManualTrendControls);
    const calibratedGroup=document.createElement('details');
    calibratedGroup.className='renko-calibrated-group';
    calibratedGroup.setAttribute('aria-label','Calibrated Renko setup');
    calibratedGroup.innerHTML='<summary><span>Calibrated setup · tested NIFTY defaults</span><label class="renko-calibrated-switch"><span>Enable</span><input id="renko-calibrated-enabled" type="checkbox"></label></summary><p class="muted">NIFTY 50 · five-minute completed candles. Adds overlap and opposing-zone entry checks with frozen ATR protection and the selected supply/demand exit. Historical comparison is not verified option performance.</p><div class="renko-calibrated-fields"><label class="field">Overlap window · pairs<input id="renko-calibrated-overlap-pairs" type="number" min="2" max="30" step="1" value="6"></label><label class="field">Maximum average overlap<input id="renko-calibrated-overlap-max" type="number" min="0" max="1" step="0.01" value="0.4"></label><label class="field">Initial stop · underlying ATR<input id="renko-calibrated-stop-atr" type="number" min="0.1" max="20" step="0.1" value="3"></label><label class="field">Target · underlying ATR<input id="renko-calibrated-target-atr" type="number" min="0.1" max="20" step="0.1" value="1.5"></label></div><div class="renko-calibrated-fields"><label class="field renko-zone-switch"><span>Opposing-zone entry filter</span><input id="renko-zone-entry-enabled" type="checkbox"></label><label class="field"><span>Minimum opposing-zone clearance · ATR</span><input id="renko-zone-entry-min-atr" type="number" min="0.1" max="10" step="0.1" value="1"></label><label class="field renko-zone-switch"><span>Allow rejected setups to qualify again</span><input id="renko-zone-entry-rearm" type="checkbox" checked></label></div><p class="muted">Longs need clearance below supply; shorts need clearance above demand. Tested defaults retain the 3-ATR stop and 1.5-ATR target and add the completed-candle supply/demand exit.</p><div class="renko-calibrated-comparison"><p>Two-year reference · underlying points · two-point friction</p><table><thead><tr><th>Metric</th><th>Calibrated</th><th>With zone rules</th></tr></thead><tbody><tr><td>Win rate</td><td>52.99%</td><td>56.59%</td></tr><tr><td>Profit factor</td><td>1.18</td><td>1.34</td></tr><tr><td>Realized drawdown · points</td><td>416.60</td><td>182.50</td></tr></tbody></table><p>Reference settings only; edits are not recalculated here. With four-point friction, both longest loss streaks are seven; results depend on thresholds. Actual option fills and costs remain unverified.</p></div><div class="packet-actions"><button type="button" class="button secondary" id="renko-apply-calibrated">Use tested defaults</button><button type="button" class="button secondary" id="renko-use-baseline">Use existing baseline</button></div><p id="renko-calibrated-status" role="status"></p><p class="muted">Levels freeze separately for each new position from a fresh underlying quote and completed ATR. Existing positions retain their levels. Edits apply on the next Start; these buttons do not start a runner.</p>';
    manualTrendGroup.after(calibratedGroup);
    calibratedGroup.querySelector('.renko-calibrated-switch').addEventListener('click',event=>event.stopPropagation());
    if(!document.getElementById('renko-calibrated-style')){
      const style=document.createElement('style');style.id='renko-calibrated-style';
      style.textContent='#renko-supertrend .renko-calibrated-group{display:block;margin:16px 0;padding:16px;border:1px solid #304057;border-radius:12px;background:#142033;min-width:0}#renko-supertrend .renko-calibrated-group>summary{display:flex;align-items:center;justify-content:space-between;gap:16px;cursor:pointer;min-height:32px;list-style:none}#renko-supertrend .renko-calibrated-group>summary>span{flex:1;min-width:0;font-weight:600}#renko-supertrend .renko-calibrated-switch{display:inline-flex;flex-direction:row;align-items:center;gap:10px;width:auto;min-height:0;padding:0;margin:0;border:0;flex:none}#renko-supertrend .renko-calibrated-switch input{width:18px;height:18px;min-width:18px;margin:0;flex:none}#renko-supertrend .renko-calibrated-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 18px;margin:16px 0}#renko-supertrend .renko-calibrated-fields>label{display:flex;flex-direction:column;align-items:stretch;gap:7px;padding:0;margin:0;border:0;min-width:0}#renko-supertrend .renko-calibrated-fields input{width:100%;max-width:none;box-sizing:border-box;height:40px}#renko-supertrend .renko-zone-switch{display:flex!important;flex-direction:row!important;align-items:center!important;justify-content:space-between;gap:12px!important}#renko-supertrend .renko-zone-switch>span{order:0;flex:1;text-align:left}#renko-supertrend .renko-zone-switch input{order:1;margin-left:auto;width:18px!important;height:18px!important;min-width:18px;flex:none}#renko-supertrend .renko-calibrated-comparison{margin:16px 0;overflow:auto}#renko-supertrend .renko-calibrated-comparison table{width:100%;min-width:0!important;table-layout:fixed;border-collapse:collapse;font-size:13px}#renko-supertrend .renko-calibrated-comparison th,#renko-supertrend .renko-calibrated-comparison td{text-align:left;min-width:0;white-space:normal;overflow-wrap:anywhere;padding:9px 8px;border-bottom:1px solid #304057}#renko-supertrend .renko-calibrated-comparison p{font-size:12px;color:#a8b7cc;line-height:1.5}#renko-supertrend .renko-calibrated-group>.packet-actions{display:flex;gap:10px;flex-wrap:wrap}@media(max-width:600px){#renko-supertrend .renko-calibrated-group{padding:12px}#renko-supertrend .renko-calibrated-fields{grid-template-columns:1fr}#renko-supertrend .renko-calibrated-group>summary{gap:10px;align-items:flex-start;padding-right:30px}#renko-supertrend .renko-calibrated-comparison th,#renko-supertrend .renko-calibrated-comparison td{padding:8px 4px;font-size:12px}}';
      document.head.append(style);
    }

    function syncCalibratedControls(){
      const compatible=!isEngine&&!isDelta&&!isDhan&&!isMotilal&&el('symbol').value==='NSE:NIFTY50-INDEX'&&el('timeframe').value==='5 minutes';
      const ready=lastRunner?.calibrated_profile_revision==='overlap-atr-profile-v1';
      const on=el('calibrated-enabled').checked;
      const zoneReady=lastRunner?.zone_entry_revision==='opposing-zone-entry-v1';
      el('zone-entry-enabled').disabled=!compatible||!on;
      el('zone-entry-min-atr').disabled=el('zone-entry-rearm').disabled=!compatible||!on||!el('zone-entry-enabled').checked;
      el('calibrated-enabled').disabled=!compatible;
      el('apply-calibrated').disabled=!compatible;
      for(const id of ['calibrated-overlap-pairs','calibrated-overlap-max','calibrated-stop-atr','calibrated-target-atr'])el(id).disabled=!compatible||!on;
      const gate=lastRunner?.latest_entry_assessment?.signal?.calibrated_filter;
      el('calibrated-status').textContent=!compatible?'Select FYERS NIFTY 50 on five-minute candles for this tested setup.':!ready?'Backend activation pending for this setup · existing baseline remains available; running settings are unchanged.':on?'Draft: calibrated profile ON · '+(gate?gate.reason+' · overlap '+Number(gate.average_overlap??0).toFixed(2):'completed-candle overlap assessment will appear after Start'):'Draft: existing baseline · calibrated rules OFF.';
      if(on&&el('zone-entry-enabled').checked)el('calibrated-status').textContent+=' · zone entry '+(zoneReady?'ON · '+Number(el('zone-entry-min-atr').value).toFixed(2)+' ATR clearance':'activation pending');
      if(on&&(!ready||el('zone-entry-enabled').checked&&!zoneReady)&&!(lastRunner?.running||lastRunner?.position||lastRunner?.pending)){el('toggle').disabled=true;el('start-selected').disabled=true;}
    }
    el('apply-calibrated').onclick=()=>{if(el('apply-calibrated').disabled)return;const next=testedNiftyDefaults(values());for(const id of allIds)if(Object.hasOwn(next,id)){if(el(id).type==='checkbox')el(id).checked=next[id];else el(id).value=next[id];}el('calibrated-enabled').dispatchEvent(new Event('change',{bubbles:true}));indicatorControls();controls();configurationState();};
    el('use-baseline').onclick=()=>{for(const id of ['calibrated-enabled','zone-entry-enabled','zone-target-enabled','zone-target-enabled-indicator','zones-family-enabled'])el(id).checked=false;el('calibrated-enabled').dispatchEvent(new Event('change',{bubbles:true}));};


    const thirdNote=document.createElement('small');thirdNote.id='renko-ema-third-status';thirdNote.className='renko-small';el('ema-third-length').closest('label').append(thirdNote);
    function syncThirdEmaControls(){
      const ready=lastRunner?.ema_third_revision==='third-ema-entry-v1';
      const enabled=el('ema-third-enabled').checked&&el('ema-family-enabled').checked;
      thirdNote.textContent=ready?'Same trend-side and ordered EMA rules · applies on next Start.':'Selected for next Start · dashboard activation required before saving or starting.';
      if(!isEngine&&enabled&&!ready&&!lastRunner?.running&&!lastRunner?.position&&!lastRunner?.pending)for(const id of ['toggle','chart-toggle','start-selected'])el(id).disabled=true;
    }
    for(const group of section.querySelectorAll('.renko-setting-group'))if(!group.classList.contains('renko-family-group')&&!group.querySelector('input,select')){group.hidden=true;if(group.parentElement.tagName==='DETAILS')group.parentElement.hidden=true;}
    // Exit controls belong to the exit panel; family masters still govern their IDs.
    const exitGroups=[
      ['EMA exits',['ema-exit-enabled','ema-exit-length','ema-slow-exit-enabled','ema-widening-exit-enabled']],
      ['Supertrend exit',['supertrend-exit-enabled']],
      ['RSI exit',['rsi-exit-enabled']],
      ['ADX exit',['adx-exit-enabled']],
      ['Market structure exit',['market-structure-exit-enabled']],
      ['Supply / demand targets',['zone-target-enabled']]
    ];
    const exitChoiceIds=[];
    const exitSectionSync=[];
    const exitAnchor=grid.firstChild;
    for(const [title,ids] of exitGroups){
      const group=document.createElement('details');group.className='renko-setting-group renko-exit-group';
      const legend=document.createElement('summary');legend.textContent=title;group.append(legend);
      const ruleIds=ids.filter(id=>id.endsWith('-enabled'));
      const sectionKey=ruleIds[0]+'-section-choices';
      const savedChoices=document.createElement('input');savedChoices.type='hidden';savedChoices.id='renko-'+sectionKey;savedChoices.value='{}';group.append(savedChoices);exitChoiceIds.push(sectionKey);
      const masterLabel=document.createElement('label');masterLabel.className='field renko-exit-section-master';
      masterLabel.append(document.createTextNode('Enable '+title.toLowerCase()));
      const master=document.createElement('input');master.type='checkbox';master.id='renko-'+ruleIds[0]+'-section-toggle';master.setAttribute('aria-label','Enable '+title.toLowerCase());
      master.title='Switch this section’s strategy exits off together, or restore their previous selections. Entry rules and chart visibility are unchanged. Applies on the next Start.';
      masterLabel.append(master);group.append(masterLabel);
      const sync=()=>{
        const count=ruleIds.filter(id=>el(id).checked).length;master.checked=count>0;master.indeterminate=count>0&&count<ruleIds.length;
        const family=Object.keys(FAMILY_RULES).find(name=>FAMILY_RULES[name].includes(ruleIds[0]));
        master.disabled=!!family&&!el(family+'-family-enabled').checked;
        for(const input of group.querySelectorAll('input,select,textarea')){
          if(input===master||input.type==='hidden')continue;
          if(count===0){if(!Object.hasOwn(input.dataset,'exitLocked'))input.dataset.exitLocked=String(input.disabled);input.disabled=true;}
          else if(Object.hasOwn(input.dataset,'exitLocked')){input.disabled=input.dataset.exitLocked==='true';delete input.dataset.exitLocked;}
        }
      };
      exitSectionSync.push(sync);
      master.addEventListener('change',()=>{
        if(!master.checked){
          savedChoices.value=JSON.stringify(Object.fromEntries(ruleIds.map(id=>[id,el(id).checked])));
          ruleIds.forEach(id=>{el(id).checked=false;});
        }else{
          let saved={};try{saved=JSON.parse(savedChoices.value||'{}');}catch{}
          const hasSelection=ruleIds.some(id=>saved[id]===true);
          ruleIds.forEach(id=>{el(id).checked=hasSelection?saved[id]===true:true;});
        }
        el(ruleIds[0]).dispatchEvent(new Event('change',{bubbles:true}));sync();
      });
      ruleIds.forEach(id=>el(id).addEventListener('change',sync));
      sync();
      const note=document.createElement('p');note.textContent='Section switch controls strategy exits only and restores your selections when re-enabled. The indicator-family master must also be on. Edits apply on the next Start.';group.append(note);
      const headings=document.createElement('div');headings.className='renko-destination-headings';headings.innerHTML='<span>Exit rule</span><span>Strategy</span><span>Chart only</span>';group.append(headings);
      for(const id of ids)group.append(el(id).closest('label'));
      grid.insertBefore(group,exitAnchor);
    }
    const riskSectionState={};
    // Header switches remain reachable when their settings are collapsed.
    for(const group of [...section.querySelectorAll('.renko-family-group,.renko-exit-group'),...grid.querySelectorAll('fieldset.renko-setting-group')]){
      if(group.hidden||!group.querySelector('input,select,textarea'))continue;
      let panel=group;
      if(group.tagName==='FIELDSET'){
        panel=document.createElement('details');panel.className=group.className;
        const heading=document.createElement('summary');heading.textContent=group.querySelector('legend')?.textContent||'Settings';
        group.querySelector('legend')?.remove();panel.append(heading,...group.childNodes);group.replaceWith(panel);
      }
      const heading=panel.querySelector(':scope>summary');
      let masterRow=panel.querySelector('.renko-family-master,.renko-exit-section-master')||panel.querySelector('#renko-trailing-enabled')?.closest('label');
      if(!masterRow){
        const riskIds=[...panel.querySelectorAll('input,select,textarea')].map(input=>input.id.replace(/^renko-/,''));
        const riskKey=riskIds.join(',');
        masterRow=document.createElement('label');masterRow.textContent='Enable section';
        const master=document.createElement('input');master.type='checkbox';master.checked=true;master.setAttribute('aria-label','Enable '+heading.textContent.trim());masterRow.append(master);
        const savedKey='sector-pulse:renko-risk-master:'+brokerName+':'+dhanAccount+':'+riskKey;
        try{master.checked=localStorage.getItem(savedKey)!=='off';}catch{}
        const sync=()=>{riskSectionState[riskKey]=master.checked;for(const id of riskIds)el(id).disabled=!master.checked;};
        master.addEventListener('change',()=>{try{localStorage.setItem(savedKey,master.checked?'on':'off');}catch{}sync();});exitSectionSync.push(sync);sync();
        panel.dataset.riskIds=riskKey;
      }
      if(masterRow){
        heading.append(masterRow);masterRow.classList.add('renko-heading-switch');
        masterRow.addEventListener('click',event=>event.stopPropagation());
      }
      const title=heading.firstChild.textContent.trim();
      const key='sector-pulse:renko-section-fold:'+brokerName+':'+dhanAccount+':'+title;
      panel.open=false;try{panel.open=localStorage.getItem(key)==='open';}catch{}
      panel.addEventListener('toggle',()=>{try{localStorage.setItem(key,panel.open?'open':'closed');}catch{}});
    }
    settingsStyle.textContent+=`#renko-supertrend .renko-setting-group>summary{cursor:pointer;font-weight:700;padding:10px 0;color:#c5d7ed}#renko-supertrend .renko-setting-group>summary .renko-heading-switch{display:inline-flex;float:right;align-items:center;gap:10px;margin:0 0 0 16px;font-size:12px;font-weight:400;max-width:65%}#renko-supertrend .renko-setting-group>summary .renko-setting-help{display:none}#renko-supertrend .renko-setting-group>summary .renko-setting-name{font-size:12px}`;
    const jumpTargets=[['Trade setup','renko-workspace'],['Entry rules','renko-family-ema'],['Exit rules','renko-ema-exit-length'],['Chart','renko-chart-stack']];
    async function jumpToRule(id){
      if(document.fullscreenElement)await document.exitFullscreen();
      const targetDocument=isBatchChartView?window.parent.document:document;
      let target=id==='renko-chart-stack'&&!isBatchChartView?targetDocument.querySelector('#renko-batch-charts:not([hidden])'):null;
      target=target||targetDocument.getElementById(id);
      if(!target)return;
      for(let node=target;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
      const block=target.closest('fieldset')||target;
      block.scrollIntoView({behavior:'instant',block:'start'});
    }
    function jumpNavigation(){
      const nav=document.createElement('nav');nav.className='renko-jump-nav';nav.setAttribute('aria-label','Strategy section navigation');
      for(const [title,id] of jumpTargets){const button=document.createElement('button');button.type='button';button.className='renko-quiet-button';button.textContent=title;button.onclick=()=>jumpToRule(id);nav.append(button);}
      return nav;
    }
    if(!isBatchChartView)section.querySelector('.head').after(jumpNavigation());
    el('chart-toolbar').append(jumpNavigation());
    settingsStyle.textContent+='.renko-jump-nav{display:flex;gap:8px;flex-wrap:wrap;padding:8px;background:#172132;border:1px solid #334154;border-radius:8px;z-index:15}#renko-supertrend>.renko-jump-nav{position:fixed;top:auto;bottom:18px;right:20px;max-width:calc(100vw - 32px);margin:0;box-shadow:0 5px 20px #0008}#renko-chart-toolbar>.renko-jump-nav{flex-basis:100%}#renko-supertrend fieldset,#renko-workspace,#renko-batch-charts{scroll-margin-top:78px}#renko-chart-scroll-body{overflow-y:scroll!important;scrollbar-gutter:stable;scrollbar-width:auto;scrollbar-color:#7899bd #172132}#renko-chart-scroll-body::-webkit-scrollbar{width:14px}#renko-chart-scroll-body::-webkit-scrollbar-thumb{background:#7899bd;border:3px solid #172132;border-radius:8px}#renko-chart-scroll-body::-webkit-scrollbar-track{background:#172132}';
    const chartOnly=document.createElement('fieldset');chartOnly.className='renko-setting-group';chartOnly.innerHTML='<legend>Chart display only</legend><p>These controls and the Chart only column do not enable strategy entries or exits.</p>';entryFilterGrid.append(chartOnly);
    for(const id of ['volume-enabled','rsi-sma-enabled'])chartOnly.append(el(id).closest('label'));
    destinationsNote.textContent='Each family master governs its entry rules here and its exit rules under Risk & exit settings. OFF locks all settings in that section and disables its strategy/chart rules. Choices and periods are retained for ON. Edits apply on the next Start, not to an active runner.';
    settingsStyle.textContent+='#renko-supertrend .renko-family-group[data-strategy-off="true"] .renko-destination-row>input:first-of-type{opacity:.4}#renko-supertrend .renko-family-master{font-weight:600}#renko-supertrend .renko-family-group>p{font-size:12px;line-height:1.5;color:#a9bad0}';
    settingsStyle.textContent+='#renko-supertrend .renko-family-group>summary{cursor:pointer;font-weight:700;padding:10px 0;color:#c5d7ed}#renko-supertrend .renko-family-group>summary:focus-visible{outline:2px solid #a9dcff;outline-offset:3px}';
    function familyControls(){
      for(const input of section.querySelectorAll("[data-family-disabled]")){input.disabled=input.dataset.familyDisabled==='true';delete input.dataset.familyDisabled;}
      paintTradingSessionHours(lastRunner?.config?.underlying===el('symbol').value?lastRunner.config:null);
      el('supertrend-continuation-enabled').disabled=lastRunner?.supertrend_continuation_revision!=='optional-completed-continuation-v1';
      continuationHelp.textContent=(lastRunner?.supertrend_continuation_revision==='optional-completed-continuation-v1'?'':'Pending stopped-worker reload. ')+ 'OFF: reversal-only. ON: fresh completed close above both Supertrends for buy, below both for sell; higher-timeframe check required. Next Start only.';
      el('supertrend-continuation-enabled').title=el('supertrend-continuation-enabled').disabled?'Backend reload pending; current runner remains unchanged.':'Optional continuation entry on a fresh completed candle. OFF by default.';
      const ready=lastRunner?.indicator_family_revision==='indicator-family-masters-v1';
      for(const [name,ids] of Object.entries(FAMILY_RULES)){
        const enabled=el(name+'-family-enabled').checked,group=el('family-'+name);
        el(name+'-family-enabled').disabled=!ready;group.dataset.strategyOff=String(!enabled);
        const active=lastRunner?.config?.[name+'_family_enabled']!==false;
        el(name+'-family-status').textContent=(ready?'Next Start: '+(enabled?'enabled':'OFF — all section settings disabled; choices retained'):'Backend deployment pending — master unavailable')+' · Active runner: '+(lastRunner?.running?(active?'family enabled':'family OFF'):'stopped')+'. Chart selections are retained and disabled with this section.';
        if(!enabled)for(const id of familyRows[name]){
          const control=el(id);if(!control)continue;
          for(const input of control.closest('label').querySelectorAll('input,select,textarea')){
            if(!Object.hasOwn(input.dataset,'familyDisabled'))input.dataset.familyDisabled=String(input.disabled);
            input.disabled=true;
          }
        }
      }
      if(!el('ema-family-enabled').checked||!el('supertrend-family-enabled').checked){if(!Object.hasOwn(el('retest-enabled').dataset,'familyDisabled'))el('retest-enabled').dataset.familyDisabled=String(el('retest-enabled').disabled);el('retest-enabled').disabled=true;}
      exitSectionSync.forEach(sync=>sync());
      const selected=Object.values(familySettings(values())).some(v=>!v);
      if(!ready&&selected&&!lastRunner?.running){el('toggle').disabled=true;el('start-selected').disabled=true;}
    }
    const manualReferenceInput=document.createElement('input');
    manualReferenceInput.type='hidden';manualReferenceInput.id='renko-manual-brick-reference';
    section.append(manualReferenceInput);
    let modeEdited=false;el('mode').addEventListener('change',()=>{modeEdited=true;});
    const historySourceControl=document.createElement('details');historySourceControl.hidden=!isMotilal;
    historySourceControl.innerHTML='<summary>Historical candle source <label><input id="renko-fyers-history-enabled" type="checkbox"> Use FYERS historical candles</label></summary><label class="field">FYERS history account<select id="renko-fyers-history-account-id"><option value="">Select a FYERS account</option></select></label><p class="muted">OFF: Motilal native captured candles only. ON: explicitly staged FYERS history with Motilal live data. Orders, ATM strikes, expiry, tokens and executable quotes remain Motilal-specific. Changes apply to the displayed analysis and next Start; active runner settings stay unchanged.</p>';
    el('search').closest('label').before(historySourceControl);
    historySourceControl.querySelector('input').addEventListener('click',event=>event.stopPropagation());
    const fyersAccounts=root.BrokerForms.accounts().filter(a=>a.broker==='FYERS');
    for(const account of fyersAccounts)el('fyers-history-account-id').add(new Option(account.label+' · '+account.account_ref,account.id));
    if(fyersAccounts.length===1)el('fyers-history-account-id').value=fyersAccounts[0].id;
    const emaPeriods=document.createElement('datalist');emaPeriods.id='renko-exit-ema-periods';emaPeriods.innerHTML='<option value="10">EMA 10</option><option value="30">EMA 30</option>';section.append(emaPeriods);
    const brickExitLabel=document.createElement('label');brickExitLabel.className='field';brickExitLabel.innerHTML='Exit on opposing completed Renko brick<input id="renko-renko-brick-exit-enabled" type="checkbox">';el('supertrend-exit-enabled').closest('label').after(brickExitLabel);
    const allIds=[...new Set(['supertrend-slope-enabled','supertrend-slope-bars','supertrend-slope-min-atr','strategy-basis','renko-brick-exit-enabled','ema-policy-profile','fyers-history-enabled','fyers-history-account-id','supertrend-continuation-enabled',...exitChoiceIds,'manual-brick-reference',...DESTINATION_RULES.map(id=>id+'-indicator'),'supertrend-exit-enabled','ema-slow-exit-enabled','rsi-exit-enabled','ema-widening-exit-enabled','adx-exit-enabled','market-structure-exit-enabled','volume-enabled','rsi-sma-enabled','higher-timeframe-enabled','supertrend-timeframe','market','cash-product','commodity-holding','delta-execution-route',...signalIds,...historyIds,'zone-target-enabled','market-structure-enabled','mode','lots','paper-capital','max-trades','max-premium','daily-budget','spot-target','spot-stop','ema-exit-enabled','ema-exit-length','sideways-enabled','sideways-max-candles','additional-slippage-points','ema-proximity-enabled','ema-proximity-mode','ema-proximity-distance','ema-momentum-enabled','trailing-enabled','trailing-basis','trailing-distance','chart-view'])];
    const factoryFields=universalStrategyDefaults(Object.fromEntries(allIds.map(id=>[id,el(id).type==='checkbox'?el(id).checked:el(id).value])));
    if(!isEngine)for(const [id,value] of Object.entries(factoryFields)){if(!el(id))continue;if(el(id).type==='checkbox')el(id).checked=value===true;else el(id).value=value;}
    if(isEngine)root.RenkoEngine.install({el,allIds,signalPanel,executionPanel,workspace,isDelta,isDhan});
    function indicatorControls(changed=null){
      const antiReady=lastRunner?.anti_chop_revision==='host-timeframe-anti-chop-v4-combination',antiOn=el('anti-chop-enabled').checked;el('anti-chop-enabled').disabled=isEngine||!antiReady;for(const id of ANTI_CHOP_IDS.slice(1))el(id).disabled=isEngine||!antiOn||!antiReady;el('anti-chop-badge').textContent=antiOn?'On':'Off';for(const id of ['anti-chop-slope-atr','anti-chop-gap-atr','anti-chop-overlap-percent'])el(id).disabled=!antiReady||!antiOn||el('anti-chop-mode').value!=='Manual';for(const id of ['anti-chop-adaptive-window','anti-chop-slope-percentile','anti-chop-gap-percentile','anti-chop-overlap-percentile'])el(id).disabled=!antiReady||!antiOn||el('anti-chop-mode').value!=='Adaptive';el('anti-chop-status').textContent=!antiReady?'Backend activation pending · current runners and saved choices are unchanged.':el('intrabar-entries').checked?'Uses completed candles. Turn off intrabar entries before enabling.':el('anti-chop-mode').value+' mode · follows '+el('timeframe').value+' candles · changes apply on the next Start.';
      if(isEngine){root.RenkoEngine.lockLegacy(el);return;}
      const both=(el('ema-fast-enabled').checked||el('ema-fast-enabled-indicator').checked)&&(el('ema-slow-enabled').checked||el('ema-slow-enabled-indicator').checked);
      if(changed==='ema-fast-enabled'&&!el('ema-fast-enabled').checked)el('retest-enabled').checked=false;
      if(changed==='ema-fast-enabled-indicator'&&!el('ema-fast-enabled-indicator').checked)el('retest-enabled-indicator').checked=false;
      if(changed==='supertrend-enabled'&&!el('supertrend-enabled').checked)el('retest-enabled').checked=false;
      if(changed==='supertrend-enabled-indicator'&&!el('supertrend-enabled-indicator').checked)el('retest-enabled-indicator').checked=false;
      if(changed&&Number(el('ema-fast-length').value)!==10){el('retest-enabled').checked=false;el('retest-enabled-indicator').checked=false;}
      const noEma=!(el('ema-fast-enabled').checked||el('ema-fast-enabled-indicator').checked)&&!(el('ema-slow-enabled').checked||el('ema-slow-enabled-indicator').checked);

      el('ema-widening-enabled').disabled=false;
      adxDetails.hidden=!((el('use-adx').checked||el('use-adx-indicator').checked)||(el('adx-exit-enabled').checked||el('adx-exit-enabled-indicator').checked));if(changed==='use-adx')adxDetails.open=(el('use-adx').checked||el('use-adx-indicator').checked);
      const htfRsiEnabled=RSI_HTF_SLOTS.some(i=>el('rsi-htf-'+i+'-enabled').checked);
      const groups=[['rsi-level-enabled',['rsi-level-mode','rsi-bullish-min','rsi-bullish-max','rsi-bearish-min','rsi-bearish-max','rsi-bullish-above','rsi-bearish-below']],['rsi-slope-enabled',['rsi-length']],['supertrend-enabled',['atr-length','factor','brick-mode','manual-brick']],['ema-fast-enabled',['ema-fast-length']],['ema-slow-enabled',['ema-slow-length']],['ema-third-enabled',['ema-third-length']],['ema-widening-enabled',['widening-window']],['use-adx',['adx-threshold','adx-length','adx-smoothing']],['retest-enabled',['retest-engulfing','retest-harami','retest-star']],['ema-proximity-enabled',['ema-proximity-mode','ema-proximity-distance']],['higher-timeframe-enabled',['supertrend-timeframe']],['ema-exit-enabled',['ema-exit-length']],['sideways-enabled',['sideways-max-candles']],['trailing-enabled',['trailing-basis','trailing-distance']]];
      for(const [toggle,ids]of groups)for(const id of ids)el(id).closest('label').hidden=!(el(toggle).checked||(DESTINATION_RULES.includes(toggle)&&el(toggle+'-indicator').checked));
      el('ema-fast-length').closest('label').hidden=!((el('ema-fast-enabled').checked||el('ema-fast-enabled-indicator').checked)||(el('ema-widening-enabled').checked||el('ema-widening-enabled-indicator').checked)||el('ema-proximity-enabled').checked||(el('ema-widening-exit-enabled').checked||el('ema-widening-exit-enabled-indicator').checked));el('ema-slow-length').closest('label').hidden=!((el('ema-slow-enabled').checked||el('ema-slow-enabled-indicator').checked)||(el('ema-widening-enabled').checked||el('ema-widening-enabled-indicator').checked)||(el('ema-slow-exit-enabled').checked||el('ema-slow-exit-enabled-indicator').checked)||(el('ema-widening-exit-enabled').checked||el('ema-widening-exit-enabled-indicator').checked));el('rsi-length').closest('label').hidden=!(htfRsiEnabled||(el('rsi-slope-enabled').checked||el('rsi-slope-enabled-indicator').checked)||el('rsi-sma-enabled').checked||(el('rsi-exit-enabled').checked||el('rsi-exit-enabled-indicator').checked));el('manual-brick').closest('label').hidden=!((el('supertrend-enabled').checked||el('supertrend-enabled-indicator').checked)||(el('supertrend-exit-enabled').checked||el('supertrend-exit-enabled-indicator').checked))||el('brick-mode').value!=='Manual';
      for(const i of RSI_HTF_SLOTS){const on=el('rsi-htf-'+i+'-enabled').checked;el('rsi-htf-'+i+'-timeframe').disabled=!on;
        for(const key of Object.keys(RSI_HTF_LEVELS)){const input=el('rsi-htf-'+i+'-'+key);input.disabled=!on;input.closest('label').hidden=key!=='level-mode'&&((el('rsi-htf-'+i+'-level-mode').value||el('rsi-level-mode').value)==='BETWEEN'?key.endsWith('above')||key.endsWith('below'):key.endsWith('min')||key.endsWith('max'));}}
      if(htfRsiEnabled)for(const id of ['rsi-length','rsi-level-mode','rsi-bullish-min','rsi-bullish-max','rsi-bearish-min','rsi-bearish-max','rsi-bullish-above','rsi-bearish-below'])el(id).disabled=false;
      const rangeMode=true,rsiLevelVisible=htfRsiEnabled||el('rsi-level-enabled').checked||el('rsi-level-enabled-indicator').checked;
      for(const id of ['rsi-bullish-min','rsi-bullish-max','rsi-bearish-min','rsi-bearish-max'])el(id).closest('label').hidden=!rsiLevelVisible||!rangeMode;
      for(const id of ['rsi-bullish-above','rsi-bearish-below'])el(id).closest('label').hidden=!rsiLevelVisible||rangeMode;
      for(const id of ['atr-length','factor','brick-mode'])el(id).closest('label').hidden=!((el('supertrend-enabled').checked||el('supertrend-enabled-indicator').checked)||(el('supertrend-exit-enabled').checked||el('supertrend-exit-enabled-indicator').checked));
      el('widening-window').closest('label').hidden=!((el('ema-widening-enabled').checked||el('ema-widening-enabled-indicator').checked)||(el('ema-widening-exit-enabled').checked||el('ema-widening-exit-enabled-indicator').checked));
      for(const id of ['adx-threshold','adx-length','adx-smoothing']){el(id).closest('label').hidden=!((el('use-adx').checked||el('use-adx-indicator').checked)||(el('adx-exit-enabled').checked||el('adx-exit-enabled-indicator').checked));el(id).disabled=!((el('use-adx').checked||el('use-adx-indicator').checked)||(el('adx-exit-enabled').checked||el('adx-exit-enabled-indicator').checked));}
      el('ema-fast-enabled').closest('label').querySelector('.renko-setting-name').textContent='EMA '+el('ema-fast-length').value+' · first EMA';
      el('ema-slow-enabled').closest('label').querySelector('.renko-setting-name').textContent='EMA '+el('ema-slow-length').value+' · second EMA';
      el('ema-third-enabled').closest('label').querySelector('.renko-setting-name').textContent='EMA '+el('ema-third-length').value+' · third EMA';
      if(el('rsi-chart')){el('rsi-chart').closest('section').querySelector('b').textContent='RSI '+el('rsi-length').value+' · host close';const showRsi=chartChoice('rsi-slope-enabled-indicator')||chartChoice('rsi-sma-enabled')||chartChoice('rsi-exit-enabled-indicator');el('rsi-chart').hidden=!showRsi;el('rsi-chart').closest('section').hidden=!showRsi;}
      if(el('rsi-sma-period'))el('rsi-sma-period').closest('label').hidden=!chartChoice('rsi-sma-enabled');
      familyControls();
    }
    function initializeRsiHtf(){for(const i of RSI_HTF_SLOTS)for(const [key,fallback] of Object.entries(RSI_HTF_LEVELS)){const input=el('rsi-htf-'+i+'-'+key);if(input.value==='')input.value=el('rsi-'+key)?.value||fallback;}}
    const values=()=>{initializeRsiHtf();return Object.fromEntries(allIds.map(id=>[id,(el(id).type==='checkbox')?el(id).checked:el(id).value]));};
    const payload=()=>{const result=rawPayload();if(isMotilal){result.fyers_history_enabled=el('fyers-history-enabled').checked;result.fyers_history_account_id=el('fyers-history-account-id').value;}for(const [ids,enabled] of Object.entries(riskSectionState))if(!enabled)for(const id of ids.split(',')){if(id==='additional-slippage-points')continue;result[id.replaceAll('-','_')]='';}return result;};
    const rawPayload=()=>({...signalSettings(values()),higher_timeframe_enabled:el('higher-timeframe-enabled').checked,supertrend_timeframe:el('supertrend-timeframe').value,...(isNative?{broker:selectedBroker,account_id:dhanAccount}:{}),...(isDelta?{broker:'DELTA_INDIA',price_source:el('price-source').value,session_deadline:el('session-deadline').value,order_terms:el('order-terms').value,carry_policy:el('carry-policy').value}:{}),commodity_holding:!isDelta&&(el('market').value==='MCX'||el('symbol').value.startsWith('MCX:'))?el('commodity-holding').value:undefined,execution_route:isDelta?el('delta-execution-route').value:cashEquity()?'CASH_EQUITY':'OPTIONS',cash_product:cashEquity()?el('cash-product').value:undefined,quantity:cashEquity()?el('lots').value:undefined,underlying:el('symbol').value,timeframe:el('timeframe').value,strategy:STRATEGY,exit_policy:'OPPOSITE_CONFIRMED_SIGNAL',configuration_revision:lastRunner?.runtime_revision,paper_capital_inr:Number(el('paper-capital').value),mode:el('mode').value,lots:el('lots').value,max_trades:el('max-trades').value,max_premium:el('max-premium').value,daily_budget:el('daily-budget').value,spot_target:el('spot-target').value,spot_stop:el('spot-stop').value,zone_target_enabled:el('zone-target-enabled').checked,market_structure_enabled:el('market-structure-enabled').checked,ema_exit_enabled:el('ema-exit-enabled').checked,ema_exit_length:el('ema-exit-length').value,sideways_enabled:el('sideways-enabled').checked,sideways_max_candles:el('sideways-max-candles').value,additional_slippage_points:el('additional-slippage-points').value,ema_momentum_enabled:el('ema-momentum-enabled').checked,ema_proximity_enabled:el('ema-proximity-enabled').checked,ema_proximity_mode:el('ema-proximity-mode').value,ema_proximity_distance:el('ema-proximity-distance').value,trailing_enabled:el('trailing-enabled').checked,trailing_basis:el('trailing-basis').value,trailing_distance:el('trailing-distance').value,...(isEngine?root.RenkoEngine.executionSettings(values()):{})});
    if(!isEngine&&!isBatchChartView)root.RenkoSupertrend.backtestCapture=()=>({settings:requireRsiHtfSupport({...payload(),mode:'BACKTEST'},lastRunner),account_id:root.BrokerForms?.account('renko')?.id||dhanAccount,broker:selectedBroker,instance_id:instanceId,active:!!(lastRunner?.running||lastRunner?.position||lastRunner?.pending)});
    // Embedded Start must use the visible editor, never a stale instance draft.
    root.addEventListener('message',async event=>{
      if(isBatchChartView||event.origin!==location.origin||event.data?.type!=='sector-pulse:renko-start-settings-request')return;
      const card=[...batchChartFrames.values()].find(card=>card.querySelector('iframe')?.contentWindow===event.source);
      if(!card)return;
      const expected=new URL(card.querySelector('iframe').src).searchParams.get('renkoChartSymbol');
      const reply={type:'sector-pulse:renko-start-settings-response',id:event.data.id};
      if(expected!==el('symbol').value||event.data.symbol!==expected){reply.error='Select this chart instrument in Trade setup before Start; displayed settings were not applied.';}
      else if(!Array.from(el('timeframe').options).some(option=>option.value===event.data.timeframe)){reply.error='Chart timeframe is unavailable for this instrument; Start blocked.';}
      else{try{if(el('timeframe').value!==event.data.timeframe)throw Error('Chart timeframe differs from Trade setup. Wait for chart synchronization before Start.');await confirmStartConfiguration();reply.settings=values();reply.payload=payload();}catch(error){reply.error=error.message;}}
      event.source.postMessage(reply,location.origin);
    });
    root.addEventListener('message',event=>{
      if(isBatchChartView||event.origin!==location.origin||event.data?.type!=='sector-pulse:renko-timeframe-selection')return;
      const card=[...batchChartFrames.values()].find(card=>card.querySelector('iframe')?.contentWindow===event.source);if(!card)return;
      const expected=new URL(card.querySelector('iframe').src).searchParams.get('renkoChartSymbol');
      if(expected!==el('symbol').value||event.data.symbol!==expected||!Array.from(el('timeframe').options).some(option=>option.value===event.data.timeframe))return;
      el('timeframe').value=event.data.timeframe;
      const higher={'1 minute':'5 minutes','5 minutes':'15 minutes'}[event.data.timeframe];if(higher)el('supertrend-timeframe').value=higher;
      controls();configurationState();void persistDraft({syncFrames:false}).catch(error=>{el('action-error').textContent='Timeframe draft save failed: '+error.message;el('action-error').hidden=false;});
    });
    async function confirmStartConfiguration(){
      const current=values(),record=chooseConfiguration(namedLibrary,current.symbol);
      if(!record)return;
      const changed=allIds.filter(id=>Object.hasOwn(record.settings,id)&&String(current[id])!==String(record.settings[id]));
      if(!changed.length)return;
      const choice=await new Promise(resolve=>{
        const dialog=document.createElement('dialog');dialog.id='renko-configuration-choice';dialog.setAttribute('aria-label','Choose runner configuration');dialog.style.cssText='max-width:1000px;width:94vw;background:#172132;color:#e5edf7;border:1px solid #719fe8;border-radius:10px;padding:24px';
        const heading=document.createElement('h2');heading.textContent='Form differs from saved configuration';
        const note=document.createElement('p');note.textContent='Choose which parameters to use for '+current.symbol+'. Form mode: '+current.mode+'; saved mode: '+(record.settings.mode||current.mode)+'. Your choice determines the mode and parameters. Saved configuration changes only when you press Save settings.';
        const list=document.createElement('div');list.style.cssText='max-height:55vh;overflow:auto';
        const table=document.createElement('table');table.style.cssText='width:100%;border-collapse:collapse;text-align:left;font-size:13px;table-layout:fixed';
        const header=document.createElement('tr');for(const text of ['Parameter','Saved configuration','Current form']){const cell=document.createElement('th');cell.textContent=text;cell.style.cssText='padding:10px;border-bottom:1px solid #719fe8;position:sticky;top:0;background:#172132';header.append(cell);}table.append(header);
        for(const id of changed){for(const item of configurationComparisonRows(id,record.settings[id],current[id])){const row=document.createElement('tr');for(const [index,text] of [item.label,item.saved,item.current].entries()){const cell=document.createElement(index===0?'th':'td');cell.textContent=index===0&&id!=='manual-brick-reference'?(el(id).closest('label')?.firstChild?.textContent||text).trim():text;cell.style.cssText='padding:10px;vertical-align:top;border-bottom:1px solid #34465b;white-space:pre-wrap;overflow-wrap:anywhere;font-weight:'+ (index===0?'600':'400');if(index>0&&item.saved!==item.current)cell.style.background='#c9982220';row.append(cell);}table.append(row);}}
        list.append(table);
        const details=document.createElement('details'),summary=document.createElement('summary'),raw=document.createElement('pre');summary.textContent='Technical calculation details';raw.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px';raw.textContent=JSON.stringify(Object.fromEntries(changed.map(id=>[id,{saved:record.settings[id],form:current[id]}])),null,2);details.append(summary,raw);list.append(details);
        const actions=document.createElement('div');actions.style.cssText='display:flex;gap:12px;flex-wrap:wrap;margin-top:20px';
        const finish=value=>{dialog.close();dialog.remove();resolve(value);};
        for(const [text,value]of [['Use form parameters','form'],['Use saved configuration','saved'],['Cancel','cancel']]){const button=document.createElement('button');button.type='button';button.textContent=text;button.className='button';button.onclick=()=>finish(value);actions.append(button);}
        dialog.addEventListener('cancel',event=>{event.preventDefault();finish('cancel');});dialog.append(heading,note,list,actions);document.body.append(dialog);dialog.showModal();
      });
      if(choice==='cancel')throw Error('Start cancelled. No runner was started.');
      if(choice==='saved'){if(record.settings.mode)el('mode').value=record.settings.mode;applyNamedFields(record);controls();}
    }
    async function selectedStartPayload(){
      if(!isBatchChartView||root.parent===root){await confirmStartConfiguration();return requireRsiHtfSupport(payload(),lastRunner);}
      const result=await new Promise((resolve,reject)=>{
        const id=crypto.randomUUID();
        const receive=event=>{
          if(event.origin!==location.origin||event.source!==root.parent||event.data?.type!=='sector-pulse:renko-start-settings-response'||event.data.id!==id)return;
          clearTimeout(timeout);root.removeEventListener('message',receive);
          if(event.data.error)reject(Error(event.data.error));else resolve(event.data);
        };
        const timeout=setTimeout(()=>{root.removeEventListener('message',receive);reject(Error('Displayed settings could not be confirmed. Refresh and retry Start.'));},300000);
        root.addEventListener('message',receive);root.parent.postMessage({type:'sector-pulse:renko-start-settings-request',id,symbol:el('symbol').value,timeframe:el('timeframe').value},location.origin);
      });
      if(result.payload?.underlying!==el('symbol').value||!result.settings)throw Error('Displayed settings instrument mismatch; Start blocked.');
      for(const id of allIds)if(Object.hasOwn(result.settings,id)){
        if(el(id).type==='checkbox')el(id).checked=result.settings[id]===true;else el(id).value=result.settings[id];
      }
      controls();
      if(el('brick-mode').value==='Manual'){
        await deriveManualBrick();
        if(manualBrickPending||manualBrickError)throw Error(manualBrickError||'Reference brick calculation is still loading.');
        result.payload.manual_brick=el('manual-brick').value;
      }
      await persistDraft();
      return requireRsiHtfSupport(result.payload,lastRunner);
    }
    const stamp=t=>new Date(t*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'});
    const fmt=x=>x==null?'Warming up':Number(x).toFixed(2);
    const price=x=>isDelta?root.DeltaINR.format(x,lastRunner?.pnl_currency||'USD'):fmt(x);
    function inrPolicy(s){if(!isDelta)return;if(Object.hasOwn(s,'inr_conversion'))root.DeltaINR.set(s.inr_conversion);if(!el('inr-policy-note')){const n=document.createElement('p');n.id='renko-inr-policy-note';n.className='renko-small';el('broker-note').after(n);}el('inr-policy-note').replaceChildren(document.createTextNode(root.DeltaINR.note()+' · '));const a=document.createElement('a');a.href=root.DeltaINR.source;a.textContent='Conversion source';a.target='_blank';el('inr-policy-note').append(a);if(chart)for(const series of [candles,line,fiveMinuteLine,ema10Line,ema30Line,ema100Line,syntheticLine])series?.applyOptions({priceFormat:{type:'custom',minMove:.01,formatter:price}});}
    let bindingPromise=null,boundSelectionSymbol='';
    async function bindDisplayedInstrument(){
      if(isBatchChartView||!el('symbol').value)return;
      if(bindingPromise)return bindingPromise;
      const symbol=el('symbol').value,broker=selectedBroker;
      bindingPromise=(async()=>{const response=await fetch(isNative?apiBase+'instances':'/api/renko-instances');const data=await response.json();if(!response.ok)throw Error(data.error||'Unable to select runner');let row=(data.instances||[]).find(v=>v.broker===broker&&v.instance_key!=='default'&&(v.instrument||v.config?.underlying)===symbol);
        if(!row){const r=await fetch(registryBase+'create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({broker,underlying:symbol})});row=await r.json();if(!r.ok)throw Error(row.error||'Unable to save instrument');}
        if(el('symbol').value!==symbol)return;
        instanceId=row.instance_key;boundSelectionSymbol=symbol;const url=new URL(location.href);url.searchParams.set('renkoInstance',instanceId);history.replaceState(null,'',url);stream?.close();streamKey='';await status();connectStream();await instanceList();
      })();try{await bindingPromise;}finally{bindingPromise=null;}
    }
    function syncManualBrickFrames(draft){
      if(isBatchChartView||draft['brick-mode']!=='Manual'||!draft['manual-brick-reference'])return;
      const signature=JSON.stringify([draft.symbol,draft['manual-brick'],draft['manual-brick-reference']]);
      const card=batchChartFrames.get(instanceId),frame=card?.querySelector('iframe');
      if(!frame||frame.dataset.manualBrickSignature===signature)return;
      frame.dataset.manualBrickSignature=signature;
      frame.src=frame.src;
    }
    let manualBrickGeneration=0,manualBrickPending=false,manualBrickError='';
    const manualBrickNote=document.createElement('small');
    manualBrickNote.style.cssText='display:block;line-height:1.4;white-space:normal;max-width:32em';
    el('manual-brick').closest('label').append(manualBrickNote);
    function manualBrickKey(){return 'sector-pulse:fixed-reference-brick-v1:'+apiBase+':'+dhanAccount+':'+el('symbol').value+':atr='+el('atr-length').value;}
    async function deriveManualBrick(){
      const generation=++manualBrickGeneration,symbol=el('symbol').value;
      manualBrickPending=false;manualBrickError='';
      if(el('brick-mode').value!=='Manual'||!symbol){manualBrickNote.textContent='';return;}
      try{
        const stored=JSON.parse(el('manual-brick-reference').value||'null');
        const saved=stored?.symbol===symbol&&(stored.user_override||Number(stored.rule?.atr_length)===Number(el('atr-length').value))?stored:JSON.parse(localStorage.getItem(manualBrickKey())||'null');
        if(saved?.symbol===symbol&&(saved.user_override||Number(saved.rule?.atr_length)===Number(el('atr-length').value))&&Number(saved.manual_brick)>0&&(isDelta||saved.user_override||saved.revision==='broker-session-reference-atr-v2')&&(!isDelta||saved.user_override||Number(saved.rule?.divisor)===46)){
          saved.manual_brick=Number(Number(saved.manual_brick).toFixed(2));el('manual-brick').value=saved.manual_brick;el('manual-brick-reference').value=JSON.stringify(saved);
          paintTradingSessionHours(saved.session_policy||null,symbol);
          manualBrickNote.textContent='Fixed reference brick · preserved across chart timeframes';
          invalidate();return;
        }
      }catch{}
      manualBrickPending=true;
      manualBrickNote.textContent='Calculating completed reference ATR…';
      try{
        // Reference history is account-bound, not owned by a strategy instance.
        // Do not wait for runner inventory/status to calculate a read-only brick.
        stream?.close();streamKey='';
        const result=await request('manual-brick?'+new URLSearchParams({symbol,atr_length:el('atr-length').value}));
        if(generation!==manualBrickGeneration||symbol!==el('symbol').value||el('brick-mode').value!=='Manual')return;
        if(Number(result.rule?.atr_length)!==Number(el('atr-length').value))throw Error('Selected ATR length is not supported by the loaded sizing backend; reload pending');
        if(!(Number(result.manual_brick)>0)||result.symbol!==symbol)throw Error('Invalid reference brick response');
        result.manual_brick=Number(Number(result.manual_brick).toFixed(2));el('manual-brick').value=result.manual_brick;el('manual-brick-reference').value=JSON.stringify(result);
        localStorage.setItem(manualBrickKey(),JSON.stringify(result));
        paintTradingSessionHours(result.session_policy||null,symbol);
        manualBrickNote.textContent='ATR '+result.rule.atr_length+' / '+result.rule.divisor+' = '+Number(result.manual_brick).toPrecision(8)+' · fixed across chart timeframes';
        manualBrickPending=false;invalidate();load();
      }catch(error){
        if(generation!==manualBrickGeneration)return;
        manualBrickError=error.message;
        manualBrickNote.textContent='Reference brick unavailable: '+error.message+' · Start blocked until calculated';
      }finally{if(generation===manualBrickGeneration){manualBrickPending=false;connectStream();}}
    }
    const recalculateManual=document.createElement('button');recalculateManual.type='button';recalculateManual.textContent='Recalculate reference brick';
    recalculateManual.style.cssText='display:block;margin-top:6px;white-space:normal';
    el('manual-brick').closest('label').append(recalculateManual);
    recalculateManual.addEventListener('click',()=>{
      if(el('brick-mode').value!=='Manual'||manualBrickPending)return;
      localStorage.removeItem(manualBrickKey());el('manual-brick-reference').value='';
      deriveManualBrick();
    });
    el('brick-mode').addEventListener('change',deriveManualBrick);
    el('atr-length').addEventListener('change',deriveManualBrick);
    el('symbol').addEventListener('change',deriveManualBrick);
    el('manual-brick').addEventListener('change',()=>{
      if(el('brick-mode').value==='Manual'&&Number(el('manual-brick').value)>0&&!manualBrickPending){
        el('manual-brick').value=Number(Number(el('manual-brick').value).toFixed(2));const record=JSON.stringify({symbol:el('symbol').value,manual_brick:Number(el('manual-brick').value),user_override:true});el('manual-brick-reference').value=record;localStorage.setItem(manualBrickKey(),record);
        manualBrickError='';manualBrickNote.textContent='Manual override · fixed across chart timeframes';
      }
    });
    async function request(path,body){if(body&&(path==='preview'||path==='start'))await bindDisplayedInstrument();if(body&&(path==='preview'||path==='start')){if(lastRunner?.indicator_destinations_revision!=='strategy-indicator-destinations-v2')throw Error('Indicator selection backend update pending; refresh before starting.');await root.PaperCapital?.ensure(body.mode);}const r=await fetch(apiBase+path+(path.includes('?')?'&':'?')+'instance='+encodeURIComponent(instanceId),body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{signal:AbortSignal.timeout(30000)});const d=await r.json();if(!r.ok||d.error)throw Object.assign(Error(isDelta&&(d.error||'').includes('Selected segment entry cutoff has passed')?'Optional saved crypto daily strategy cutoff '+el('session-deadline').value+' IST has passed. Crypto trades 24/7. Choose Continuous trading above for no daily cutoff, or keep this daily risk policy.':d.error||'Strategy request failed'),{status:r.status});return d;}
    let adoptionBusy=false,attachedExitUpdateReady=false;
    function managerTable(rows){
      el('live-pnl').querySelector('.adopted-pnl')?.remove();
      const exposure=rows.filter(r=>r.position);if(exposure.length){const summary=document.createElement('div');summary.className='pnl-context adopted-pnl';summary.textContent=exposure.map(r=>'LIVE adopted · '+r.position.symbol+' · Qty '+r.position.quantity+' · Unrealized '+(r.pnl?.available&&r.stream?.connected&&streamConnected?price(r.pnl.unrealized):'Unavailable')+' gross · '+r.status).join(' | ');el('live-pnl').append(summary);}
      table(el('adopted-managers'),['Manager','Contract','Quantity','Entry average','Status','Re-entry','Unrealized · gross','Realized · gross','Control','Saved audit'],rows.map(r=>{
      const b=document.createElement('button');b.type='button';b.className='button';b.textContent=r.running?'Stop monitoring':r.position||r.pending?'Start monitoring':'Complete';b.disabled=adoptionBusy||r.snapshot_fresh===false||(!r.running&&(!attachedExitUpdateReady||!r.position||r.pending));
      b.onclick=async()=>{if(adoptionBusy)return;adoptionBusy=true;try{await request('adoption-control',{id:r.id,action:r.running?'pause':'resume',...(!r.running?{config:payload(),confirmation:'START LIVE STRATEGY MONITORING'}:{})});await refreshBroker();}catch(e){el('adoption-status').textContent=e.message;}finally{adoptionBusy=false;}};
      const controls=document.createElement('div');controls.append(b);
      const audit=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Broker adoption / order evidence';pre.style.cssText='max-width:650px;max-height:300px;overflow:auto;white-space:pre-wrap';pre.textContent=JSON.stringify({adoption:r.adoption_evidence,settings:r.config,orders:r.order_history||[]},null,2);audit.append(summary,pre);
      return [r.id,r.position?.symbol||'Flat',r.position?.quantity??0,price(r.position?.entry_price),r.status+' · EMA exit '+(r.config?.ema_exit_enabled?'EMA'+r.config.ema_exit_length:'OFF')+' · Supertrend exit '+(r.config?.supertrend_exit_enabled?'ON':'OFF'),r.adoption_reentry?'Enabled':'Off',r.pnl?.available?price(r.pnl.unrealized):'Unavailable',price(r.realized_pnl??0),controls,audit];
    }));}
    async function refreshBroker(){
      el('adopt').disabled=true;el('broker-positions').replaceChildren();
      try{const d=await request('broker-positions');attachedExitUpdateReady=d.exit_policy_update_revision==='latest-settings-attached-exit-v2';
        for(const p of d.positions){const label=document.createElement('label');label.style.cssText='display:flex;align-items:center;gap:10px;margin:12px 0';const box=document.createElement('input');box.type='checkbox';box.style.cssText='width:16px;height:16px;flex:none';box.value=p.selection||'';box.disabled=!p.eligible;box.className='renko-adoption-choice';box.onchange=()=>{el('adopt').disabled=adoptionBusy||!adoptionPanel.querySelector('.renko-adoption-choice:checked');};label.append(box,document.createTextNode(`${p.symbol} · Qty ${p.netQty} · Avg ${isDelta?price(p.netAvg??p.avgPrice??p.buyAvg):p.netAvg??p.avgPrice??p.buyAvg??'Unavailable'} · ${p.productType} · ${p.reason}`));el('broker-positions').append(label);}
        el('adoption-status').textContent=d.ownership_error|| (d.positions.length?'Fresh broker snapshot · '+stamp(d.observed_at)+' · Select filled positions, then attach them to enable the visible strategy’s exit rules.':'No open '+brokerName+' positions.');
        table(el('broker-orders'),['ID','Symbol','Side','Requested','Filled','Product','Status'],d.orders.map(o=>[o.id,o.symbol,o.side===1?'BUY':'SELL',o.qty,o.filledQty,o.productType,({1:'CANCELLED',2:'FILLED',4:'IN TRANSIT',5:'REJECTED',6:o.filledQty>0?'PARTIAL FILL · PENDING REMAINDER':'PENDING',7:'EXPIRED'})[o.status]||'UNKNOWN']));managerTable(d.managers);
      }catch(e){el('adoption-status').textContent='Broker exposure unavailable: '+e.message;}
    }
    el('broker-refresh').onclick=refreshBroker;
    el('adopt').onclick=async()=>{if(adoptionBusy)return;adoptionBusy=true;el('adopt').disabled=true;try{await request('adopt',{...payload(),mode:'LIVE',selections:Array.from(adoptionPanel.querySelectorAll('.renko-adoption-choice:checked')).map(c=>c.value),reentry_enabled:el('adoption-reentry').checked});await refreshBroker();}catch(e){el('adoption-status').textContent=e.message;}finally{adoptionBusy=false;}};
    el('chart').insertAdjacentHTML('beforeend','<aside id="renko-chart-controls" aria-label="Runner controls on chart"><b id="renko-chart-mode-state"></b><div><button type="button" class="button" id="renko-chart-stop" disabled>Stop runner · close owned exposure</button><button type="button" class="button" id="renko-chart-mode" disabled>Select Live for next Start</button></div><small id="renko-chart-control-note" role="status"></small></aside>');
    const chartControlStyle=document.createElement('style');chartControlStyle.textContent='#renko-chart-controls{position:absolute;right:85px;bottom:78px;z-index:8;max-width:calc(100% - 120px);background:#131722ed;border:1px solid #394150;border-radius:5px;padding:8px 10px;color:#d1d4dc;font:11px Arial}#renko-chart-controls b,#renko-chart-controls small{display:block;margin:3px 0}#renko-chart-controls div{display:flex;gap:6px;flex-wrap:wrap}#renko-chart-controls button{padding:6px 8px;font-size:11px}';document.head.append(chartControlStyle);
    let chartControlBusy=false;
    function paintChartControls(){
      if(!el('chart-mode-state'))return;
      const c=chartControlState(lastRunner||{},streamConnected&&runnerStatusFresh&&statusReceived>0&&(performance.now()-statusReceived)<5000,el('mode').value,chartControlBusy);
      el('chart-mode-state').textContent=c.label;el('chart-stop').disabled=c.stopDisabled;el('chart-mode').disabled=c.modeDisabled;
      el('chart-mode').textContent='Select '+(c.next==='LIVE'?'Live':'Paper')+' for next Start';el('chart-control-note').textContent=c.reason;
    }
    const chartIdentity=s=>({controls_revision:'stopped-flat-chart-controls-v1',run_id:s.run_id??null,mode:s.config?.mode??null});
    el('chart-stop').onclick=async()=>{if(chartControlBusy)return;chartControlBusy=true;paintChartControls();try{
      const s=lastRunner;if(!s?.run_id||chartControlState(s,runnerStatusFresh,el('mode').value).stopDisabled)throw Error('No identified runner is available to stop.');
      applyStatus(await request('stop',{run_id:s.run_id,started_at:s.started_at}));
    }catch(error){el('chart-action-error').textContent=error.message;el('chart-action-error').hidden=false;}finally{chartControlBusy=false;paintChartControls();}};
    el('chart-mode').onclick=async()=>{if(chartControlBusy)return;chartControlBusy=true;paintChartControls();try{
      const s=await request('runner'),gate=chartControlState(s,true,el('mode').value);
      if(gate.modeDisabled)throw Error(gate.reason);
      const result=await request('chart-mode',{...chartIdentity(s),next_mode:gate.next});
      el('mode').value=result.next_start_mode;
      const saved=JSON.parse(localStorage.getItem(storage)||'{}');localStorage.setItem(storage,JSON.stringify({...saved,mode:result.next_start_mode,__saved_at:result.settings.saved_at}));
      applyStatus(result.runner);controls();configurationState();
    }catch(error){el('chart-action-error').textContent=error.message;el('chart-action-error').hidden=false;}finally{chartControlBusy=false;paintChartControls();}};
    const assessmentBox=document.createElement('aside');assessmentBox.id='renko-assessment';assessmentBox.setAttribute('aria-label','Latest runner assessment');assessmentBox.setAttribute('aria-live','polite');el('chart').append(assessmentBox);
    const assessmentWire=document.createElementNS('http://www.w3.org/2000/svg','svg');assessmentWire.id='renko-assessment-wire';assessmentWire.setAttribute('aria-hidden','true');el('chart').append(assessmentWire);
    const assessmentStyle=document.createElement('style');assessmentStyle.textContent=`#renko-assessment{position:absolute;left:12px;top:180px;z-index:7;width:310px;max-width:calc(100% - 110px);box-sizing:border-box;padding:10px 12px;background:#182334ed;border-left:3px solid #7ba7d1;color:#d9e4ef;font:12px/1.45 Arial,sans-serif;pointer-events:none;box-shadow:0 2px 8px #0003}#renko-assessment strong{display:block;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#96b9d8;margin-bottom:4px}#renko-assessment p{margin:0 0 5px}#renko-assessment small{display:block;color:#9dafc3;font:10px/1.5 ui-monospace,monospace}#renko-assessment .assessment-checks{font-size:10px;color:#c0d2e4;margin:5px 0}#renko-assessment-wire{position:absolute;inset:0;width:100%;height:100%;z-index:6;pointer-events:none}@media(max-width:650px){#renko-assessment{width:260px;font-size:11px;padding:8px}#renko-assessment .assessment-checks{font-size:9px}#renko-assessment-wire{display:none}}`;document.head.append(assessmentStyle);
    const chartRail=document.createElement('div');chartRail.id='renko-chart-rail';
    el('chart').before(chartRail);chartRail.append(el('live-pnl'),el('chart-controls'),el('sideways-status'));
    const assessmentDetails=document.createElement('details');assessmentDetails.innerHTML='<summary>Entry assessment · expand details</summary>';assessmentDetails.append(assessmentBox);chartRail.append(assessmentDetails);
    el('chart-toolbar').append(el('exit-fullscreen'));
    const railStyle=document.createElement('style');railStyle.textContent=`#renko-chart-rail{display:flex;gap:8px;flex-wrap:wrap;align-items:start;padding:8px 0;flex:none}#renko-chart-rail #renko-live-pnl,#renko-chart-rail #renko-chart-controls,#renko-chart-rail #renko-sideways-status,#renko-chart-rail #renko-assessment{position:static;max-width:100%;width:auto;margin:0;box-sizing:border-box;box-shadow:none}#renko-chart-rail #renko-live-pnl{flex:1;padding:6px 9px;gap:4px 16px}#renko-chart-rail #renko-live-pnl b{font-size:13px}#renko-chart-rail details{flex-basis:100%;font-size:12px}#renko-chart-rail details summary{cursor:pointer;color:#96b9d8}#renko-chart-rail #renko-assessment{padding:8px}#renko-assessment-wire{display:none}#renko-chart-toolbar #renko-exit-fullscreen{position:static}#renko-chart-stack:fullscreen #renko-chart-rail{max-height:30vh;overflow:auto}#renko-chart-stack:fullscreen section[aria-label="RSI zone indicator"]{height:auto;flex:0 0 auto}#renko-chart-stack:fullscreen #renko-rsi-chart{height:clamp(90px,18vh,170px)!important}`;document.head.append(railStyle);
    // Folding a view changes its footprint only; selected trading rules stay intact.
    const layoutStorage='sector-pulse:chart-layout-v1:'+brokerName+':'+instanceId;
    let layoutPreferences={};try{layoutPreferences=JSON.parse(localStorage.getItem(layoutStorage)||'{}');}catch{}
    function chartFold(key,title,content,parent,before=null,defaultOpen=true){
      const fold=document.createElement('details');fold.id='renko-fold-'+key;fold.className='renko-chart-fold';fold.open=layoutPreferences[key]??defaultOpen;
      const summary=document.createElement('summary'),caption=document.createElement('span');caption.className='renko-fold-title';caption.textContent=title;summary.append(caption);fold.append(summary);
      if(before)parent.insertBefore(fold,before);else parent.append(fold);
      fold.append(content);fold.addEventListener('toggle',()=>{layoutPreferences[key]=fold.open;try{localStorage.setItem(layoutStorage,JSON.stringify(layoutPreferences));}catch{}});
      return {fold,summary,caption};
    }
    const pnlFold=chartFold('pnl','Running P&L',el('live-pnl'),chartRail,chartRail.firstChild,false);
    const pnlSummary=document.createElement('b');pnlSummary.id='renko-running-pnl';pnlSummary.textContent='Loading…';pnlFold.summary.append(pnlSummary);
    chartFold('controls','Runner controls',el('chart-controls'),chartRail,null,false);
    chartFold('range','Quick-loss range',el('sideways-status'),chartRail,null,false);
    assessmentDetails.classList.add('renko-chart-fold');
    const rsiSection=el('rsi-chart').closest('section'),rsiBody=document.createElement('div');rsiBody.className='renko-study-body';
    while(rsiSection.firstChild)rsiBody.append(rsiSection.firstChild);
    const rsiFold=chartFold('rsi','RSI',rsiBody,rsiSection,null,true);
    const rsiHeading=rsiBody.querySelector('b');rsiFold.caption.replaceWith(rsiHeading);rsiFold.summary.append(el('rsi-readout'),el('rsi-sma-readout'));
    const chartLayoutStyle=document.createElement('style');chartLayoutStyle.textContent=`
      #renko-chart-stack .renko-chart-fold{flex:none;min-width:0;border:1px solid #2a394b;border-radius:5px;background:#141e2b;margin:0;overflow:hidden}
      #renko-chart-stack .renko-chart-fold>summary{display:flex;gap:12px;align-items:center;padding:7px 10px;min-height:30px;box-sizing:border-box;cursor:pointer;color:#b8cbe3;font:12px/1.3 Arial,sans-serif;list-style:none}
      #renko-chart-stack .renko-chart-fold>summary::before{content:'▸';color:#7d9bbb;flex:none}
      #renko-chart-stack .renko-chart-fold[open]>summary::before{content:'▾'}
      #renko-chart-stack .renko-chart-fold>summary:focus-visible{outline:2px solid #719fe8;outline-offset:-2px}
      #renko-chart-stack .renko-chart-fold>summary>#renko-running-pnl,#renko-chart-stack .renko-study-value{margin-left:auto;font-variant-numeric:tabular-nums}
      #renko-chart-stack .renko-study-body{padding:4px 8px 6px}#renko-chart-stack .renko-study-body>div:first-child{gap:6px!important}
      #renko-chart-stack .renko-study-body>small{display:block;font-size:10px;margin-top:3px}
      #renko-chart-stack .renko-study-body #renko-rsi-sma-period{padding:2px 5px;width:56px!important}
      #renko-chart-rail{display:flex;gap:6px;flex-wrap:wrap;padding:4px 0;align-items:start}
      #renko-chart-rail>details.renko-chart-fold{flex:1 1 190px;font-size:12px}
      #renko-chart-rail>details.renko-chart-fold[open]{flex-basis:100%}
      #renko-chart-stack:fullscreen{display:flex!important;flex-direction:column!important;gap:5px;padding:8px!important;box-sizing:border-box;overflow:auto!important}
      #renko-chart-stack:fullscreen #renko-chart-toolbar{gap:5px;margin:0;flex:none;align-items:center}
      #renko-chart-stack:fullscreen #renko-chart-toolbar button{padding:6px 9px;font-size:12px}
      #renko-chart-stack:fullscreen #renko-full-chart{display:inline-flex}
      #renko-chart-stack:fullscreen #renko-override-note:empty{display:none}
      #renko-chart-stack:fullscreen #renko-chart-rail{max-height:none;overflow:visible;margin:0;padding:0;flex:none}
      #renko-chart-stack:fullscreen #renko-chart{flex:1 0 50vh!important;min-height:50vh!important;height:auto!important;margin:0!important}
      #renko-chart-stack:fullscreen section[aria-label="RSI zone indicator"]{margin:0!important;flex:none;height:auto}
      #renko-chart-stack:fullscreen #renko-rsi-chart{height:clamp(75px,10vh,110px)!important}
      #renko-chart-stack:fullscreen .renko-study-body>small{display:none}
      #renko-chart-stack:fullscreen .renko-study-canvas{height:clamp(75px,10vh,110px)!important;margin:0!important}
      #renko-chart-stack .renko-study-canvas{height:120px;margin:0}
      @media(max-width:650px){#renko-chart-stack .renko-chart-fold>summary{flex-wrap:wrap;gap:5px}#renko-chart-stack:fullscreen #renko-chart{min-height:45vh!important;flex-basis:45vh!important}}
    `;document.head.append(chartLayoutStyle);
    const supertrendVisuals=document.createElement('details');supertrendVisuals.id='renko-supertrend-visuals';supertrendVisuals.innerHTML='<summary>Visuals · Supertrend labels</summary><div style="display:flex;gap:20px;flex-wrap:wrap;padding:10px 0"><label><input type="checkbox" id="renko-show-one-minute-label"> <span id="renko-primary-label-caption">Execution-timeframe Supertrend label</span></label><label><input type="checkbox" id="renko-show-five-minute-label"> Optional higher-timeframe Supertrend label</label></div>';el('chart-stack').before(supertrendVisuals);
    const pointerPreferencesKey='sector-pulse:supertrend-label-visuals-v1';
    let pointerPreferences={};try{pointerPreferences=JSON.parse(localStorage.getItem(pointerPreferencesKey)||'{}');}catch{}
    const oneMinuteLabelToggle=document.getElementById('renko-show-one-minute-label'),fiveMinuteLabelToggle=document.getElementById('renko-show-five-minute-label');
    oneMinuteLabelToggle.checked=pointerPreferences.one===true;fiveMinuteLabelToggle.checked=pointerPreferences.five===true;
    for(const toggle of [oneMinuteLabelToggle,fiveMinuteLabelToggle])toggle.addEventListener('change',()=>{try{localStorage.setItem(pointerPreferencesKey,JSON.stringify({one:oneMinuteLabelToggle.checked,five:fiveMinuteLabelToggle.checked}));}catch{}paintSupertrendPointers();});
    const supertrendPointers=document.createElement('div');supertrendPointers.id='renko-supertrend-pointers';supertrendPointers.setAttribute('aria-label','Supertrend line pointers');el('chart').append(supertrendPointers);
    const pointerStyle=document.createElement('style');pointerStyle.textContent='#renko-supertrend-pointers{position:absolute;inset:0;z-index:6;pointer-events:none;overflow:hidden}.renko-st-pointer{position:absolute;padding:5px 8px;background:#131722ed;border:1px solid currentColor;border-radius:4px;font:600 12px Arial;white-space:nowrap;box-shadow:0 2px 6px #0006}.renko-st-wire{position:absolute;inset:0;width:100%;height:100%;overflow:visible}';document.head.append(pointerStyle);
    let supertrendPointerPoints=[],fiveMinutePointerPoints=[];
    function paintSupertrendPointers(){
      if(!el('supertrend-enabled').checked&&!el('higher-timeframe-enabled').checked){supertrendPointers.replaceChildren();return;}
      supertrendPointers.replaceChildren();if(!chart)return;
      const range=chart.timeScale().getVisibleRange();if(!range)return;
      const width=el('chart').clientWidth,height=el('chart').clientHeight;
      const placements=[];
      for(const [series,points,label,color] of [[line,supertrendPointerPoints,(el('timeframe').value==='1 minute'?'1-minute':el('timeframe').value.replace(' minutes','-minute'))+' Supertrend','#b7e4d0'],[fiveMinuteLine,fiveMinutePointerPoints,el('supertrend-timeframe').value+' Supertrend','#7edbc3']]){
        if(!series||(series===line&&(!oneMinuteLabelToggle.checked||!(chartChoice('supertrend-enabled-indicator')||chartChoice('supertrend-exit-enabled-indicator'))))||(series===fiveMinuteLine&&(!fiveMinuteLabelToggle.checked||!chartChoice('higher-timeframe-enabled-indicator'))))continue;
        const target=points.filter(p=>p.time>=range.from&&p.time<=range.to&&Number.isFinite(p.value)).at(-1);if(!target)continue;
        const x=chart.timeScale().timeToCoordinate(target.time),y=series.priceToCoordinate(target.value);
        if(x===null||y===null||y<0||y>height-30)continue;
        const left=Math.max(8,Math.min(width-195,x+18));let top=Math.max(8,Math.min(height-65,y-42));
        if(placements.some(p=>Math.abs(p.top-top)<35))top=Math.min(height-65,top+44);
        placements.push({top});
        const box=document.createElement('span');box.className='renko-st-pointer';box.textContent=label;box.style.cssText=`left:${left}px;top:${top}px;color:${color}`;
        const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('renko-st-wire');svg.setAttribute('aria-hidden','true');
        const wire=document.createElementNS(svg.namespaceURI,'path'),dot=document.createElementNS(svg.namespaceURI,'circle');wire.setAttribute('d',`M ${left} ${top+15} L ${x} ${y}`);wire.setAttribute('fill','none');wire.setAttribute('stroke',color);wire.setAttribute('stroke-width','1.5');dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.setAttribute('r','3');dot.setAttribute('fill',color);svg.append(wire,dot);supertrendPointers.append(svg,box);
      }
    }
    let latestAssessment;
    function paintAssessment(){
      runnerStartPointer?.set(currentPlotted,lastRunner?.config?.underlying===el('symbol').value?lastRunner:null,({'1 minute':60,'2 minutes':120,'3 minutes':180,'5 minutes':300,'10 minutes':600,'15 minutes':900,'30 minutes':1800,'1 hour':3600})[chartControl('timeframe').value]||300);
      if(!root.RenkoAssessment)return;
      const a=root.RenkoAssessment.assessment(lastRunner,{symbol:el('symbol').value,timeframe:el('timeframe').value},Date.now()/1000,runnerStatusFresh&&performance.now()-lastRunnerReceived<=15000);latestAssessment=a;
      assessmentBox.replaceChildren();assessmentBox.style.fontSize='13px';assessmentBox.style.lineHeight='1.5';
      const accent=a.tone==='blocked'?'#e7af67':a.tone==='pass'?'#50c878':'#7ba7d1';
      const title=document.createElement('strong');title.textContent=a.title;title.style.cssText='display:block;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#b9cde4';
      const reason=document.createElement('p');reason.textContent=a.reason;reason.style.cssText='font-size:15px;font-weight:600;margin:8px 0 12px;padding:10px 12px;background:#0c1726;border-radius:6px;border-left:3px solid '+accent;
      assessmentBox.append(title,reason);
      const metadata=document.createElement('dl');metadata.style.cssText='display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px 16px;margin:0 0 14px';
      const field=(label,value)=>{const group=document.createElement('div'),key=document.createElement('dt'),text=document.createElement('dd');key.textContent=label;key.style.cssText='font-size:11px;color:#9eb2c9;text-transform:uppercase;letter-spacing:.04em';text.textContent=value;text.style.cssText='margin:3px 0 0;color:#e5edf7;font-variant-numeric:tabular-nums';group.append(key,text);metadata.append(group);};
      field('Runner',lastRunner?.running?a.context:a.context.replace(/^Active /,'Stopped · '));field('Candle opens',a.timestamp!==null?stamp(a.timestamp)+' IST':'Unavailable');field('Candle basis',a.provisional?'Forming · can change':'Completed candle');field('Data freshness',!lastRunner?.running?'No assessment while stopped':a.fresh?'Updated '+a.age+' seconds ago':'Current assessment unavailable');
      if(a.assessed_at)field('Entry evaluated',stamp(a.assessed_at)+' IST');if(a.history_revised_at)field('History revised',stamp(a.history_revised_at)+' IST');assessmentBox.append(metadata);
      if(a.checks.length){const table=document.createElement('table');table.style.cssText='width:100%;border-collapse:collapse;text-align:left;margin:8px 0 12px';table.setAttribute('aria-label','Entry rule checks');
        const head=document.createElement('tr');for(const label of ['Result','Entry condition']){const cell=document.createElement('th');cell.textContent=label;cell.style.cssText='padding:7px 10px;color:#9eb2c9;font-size:11px;text-transform:uppercase;border-bottom:1px solid #34465b';head.append(cell);}table.append(head);
        for(const check of a.checks){const parts=check.split(' · '),state=parts.shift(),row=document.createElement('tr'),badge=document.createElement('td'),detail=document.createElement('td');badge.textContent=state;badge.style.cssText='padding:8px 10px;border-bottom:1px solid #26364a;width:80px;font-weight:700;color:'+({PASS:'#65d6a2',WAIT:'#f0bd68',OFF:'#94a4b7',UNKNOWN:'#f0bd68',PENDING:'#8ebcf5'}[state]||'#b9cde4');detail.textContent=parts.join(' · ');detail.style.cssText='padding:8px 10px;border-bottom:1px solid #26364a';row.append(badge,detail);table.append(row);}assessmentBox.append(table);}
      const gate=lastRunner?.latest_entry_assessment?.signal?.mtf_supertrend;
      if(gate?.one_minute&&gate?.five_minute){const group=document.createElement('div');group.style.cssText='display:flex;flex-wrap:wrap;gap:10px;margin:10px 0';for(const [frame,p] of [[gate.host_timeframe,gate.one_minute],[gate.higher_timeframe,gate.five_minute]]){const card=document.createElement('div');card.style.cssText='flex:1;min-width:200px;padding:10px 12px;background:#0c1726;border:1px solid #34465b;border-radius:6px';const heading=document.createElement('strong'),value=document.createElement('div'),at=document.createElement('small');heading.textContent=frame+' · '+p.direction;heading.style.color=p.direction==='BULLISH'?'#65d6a2':'#f08d91';value.textContent='Supertrend '+price(p.supertrend);at.textContent='Candle opens '+stamp(p.timestamp)+' IST';at.style.color='#9eb2c9';card.append(heading,value,at);group.append(card);}assessmentBox.append(group);}
      if(a.rules){const rules=document.createElement('div');rules.textContent=a.rules;rules.style.cssText='padding-top:10px;border-top:1px solid #34465b;color:#9eb2c9;font-size:12px';assessmentBox.append(rules);}assessmentBox.style.borderLeftColor=accent;
      assessmentBox.style.top=Math.max(12,el('live-pnl').offsetTop+el('live-pnl').offsetHeight+8)+'px';positionAssessment();
    }
    function positionAssessment(){
      assessmentWire.replaceChildren();if(assessmentBox.parentElement===assessmentDetails)return;const a=latestAssessment;if(!chart||!candles||!a?.link||el('chart-view').value!=='host')return;
      const x=chart.timeScale().timeToCoordinate(a.timestamp),y=candles.priceToCoordinate(a.close),left=assessmentBox.offsetLeft+assessmentBox.offsetWidth,top=assessmentBox.offsetTop+25;
      if(x===null||y===null||x<left+24||x>el('chart').clientWidth-75||y<0||y>el('chart').clientHeight-30)return;
      const path=document.createElementNS('http://www.w3.org/2000/svg','path'),dot=document.createElementNS('http://www.w3.org/2000/svg','circle');path.setAttribute('d',`M ${left} ${top} L ${left+15} ${top} L ${x} ${y}`);path.setAttribute('fill','none');path.setAttribute('stroke','#7ba7d1');path.setAttribute('stroke-dasharray','3 4');dot.setAttribute('cx',x);dot.setAttribute('cy',y);dot.setAttribute('r','4');dot.setAttribute('fill','#7ba7d1');assessmentWire.append(path,dot);
    }
    new ResizeObserver(()=>{if(lastRunner)paintAssessment();}).observe(el('chart'));
    setInterval(()=>{if(lastRunner)paintAssessment();paintChartControls();paintSupertrendPointers();},1000);
    let journalRows=[];
    let sessionBreaks=null,runnerStartPointer=null;
    let historyRows=[],historyKey='',historyRevision='',lastLoadAt=0,eventPage=0,allEvents=[],currentPlotted=[];
    let runnerStatusFresh=false,overrideBusy=false,overrideAttempt=null,toggleBusy=false,owned=false,version=0,busy=false,chart,candles,volumeSeries,line,liveSupertrendLine,fiveMinuteLine,ema10Line,ema30Line,ema100Line,syntheticLine,lastKey='',running=false,searchTimer,searchVersion=0,prefsSavedAt=0,prefsTimer,latestSignalIndex=null,plottedCount=0;
    const zoneSeries=[];let zoneBands,visibleZones={supply:null,demand:null};let zoneRows=[],zoneError="Five-minute zones awaiting source history";
    function paintZones(rows=zoneRows,end=null,unavailable=zoneError){
      const enabled=chartChoice('zone-target-enabled-indicator');
      if(!enabled){visibleZones={supply:null,demand:null};for(const series of zoneSeries)series.setData([]);zoneBands?.refresh();el('zone-status').hidden=true;return;}el('zone-status').hidden=false;
      if(!chart)return;
      if(!zoneBands){zoneBands=zoneBandPrimitive(chart,candles,()=>visibleZones);candles.attachPrimitive(zoneBands);}
      if(!zoneSeries.length)for(const color of ['#ef7c86','#ef7c86','#43c8b3','#43c8b3'])zoneSeries.push(chart.addLineSeries({color,lineWidth:1,lineStyle:2,priceLineVisible:false,lastValueVisible:true,crosshairMarkerVisible:false,autoscaleInfoProvider:()=>null}));
      const zones=hostZones(rows,300),labels=[];visibleZones=unavailable||zones.error?{supply:null,demand:null}:zones;
      for(const [index,side] of ['supply','demand'].entries()){
        const z=unavailable?null:zones[side];
        for(const [offset,bound] of ['upper','lower'].entries()){
          const series=zoneSeries[index*2+offset];
          series.applyOptions({title:'Strong 5m '+side+' '+bound+(z?.brokenAt?' · broken':' · confirmed'),lineStyle:z?.brokenAt?1:2,priceFormat:{type:'custom',minMove:.01,formatter:price}});
          series.setData(z?[{time:z.pivotAt,value:z[bound]},...(end>z.pivotAt?[{time:end,value:z[bound]}]:[])]:[]);
        }
        labels.push(z?`${side.toUpperCase()} ${price(z.lower)}–${price(z.upper)} · origin ${stamp(z.pivotAt)} IST · confirmed close ${stamp(z.confirmedAt)} IST · departure ${fmt(z.departure/z.atr)}× ATR14${z.brokenAt?' · broken by close '+stamp(z.brokenAt)+' IST':''}`:side.toUpperCase()+' · no qualifying strong zone in loaded history');
      }
      el('zone-status').textContent=unavailable||zones.error||labels.join(' | ');
      el('zone-status').textContent+=' · FIVE-MINUTE broker OHLC zones / Indicator destination · strong = close beyond opposite pivot wick + ≥1× ATR14 departure within two candles · origin-to-confirmation fill is retrospective; forming candles excluded. Thin zones use a minimum 6-pixel display highlight; price-boundary labels retain exact values.'+(el('chart-view').value==='synthetic'?' Same host-price levels on synthetic bodies; these are not Renko-derived zones.':'');zoneBands.refresh();
    }
    let rsiChart,rsiLine,rsiSmaLine,rsiConfirmed={},rsiSync=false,rsiCrosshairSync=false;const rsiPoints=new Map(),rsiSmaPoints=new Map();let confirmedRsiPoints=[],formingRsiPoint=null;
    const smaStorage='sector-pulse:renko-rsi-sma-period:'+brokerName+':'+instanceId;try{const saved=Number(localStorage.getItem(smaStorage));if(Number.isInteger(saved)&&saved>=1&&saved<=200)el('rsi-sma-period').value=saved;}catch{}
    function smaPeriod(){return Number(el('rsi-sma-period').value);}
    function rebuildSma(fresh=true){if(!rsiSmaLine)return;const period=smaPeriod(),points=rsiSma([...confirmedRsiPoints,...(formingRsiPoint?[formingRsiPoint]:[])],period);rsiSmaPoints.clear();for(const p of points)rsiSmaPoints.set(p.time,p.value);rsiSmaLine.applyOptions({title:`RSI SMA ${period}`});rsiSmaLine.setData(points);const last=points.at(-1);el('rsi-sma-readout').textContent=`SMA ${period} · `+(!fresh?lastKnownIndicator(last,false):Number.isFinite(last?.value)?fmt(last.value)+(formingRsiPoint?' · provisional':' · confirmed'):'warming up');}
    el('rsi-sma-period').onchange=()=>{if(!Number.isInteger(smaPeriod())||smaPeriod()<1||smaPeriod()>200)el('rsi-sma-period').value=14;try{localStorage.setItem(smaStorage,smaPeriod());}catch{}rebuildSma();};
    const underlyingPrice=document.createElement('span');underlyingPrice.id='renko-underlying-price';underlyingPrice.style.cssText='padding:6px 10px;border:1px solid #394150;border-radius:5px;font-size:15px;font-weight:600;font-variant-numeric:tabular-nums;color:#d1d4dc';underlyingPrice.textContent='Underlying price · waiting for feed';el('chart-toolbar').prepend(underlyingPrice);
    let lastUnderlyingPrice=null,lastUnderlyingSymbol='',underlyingDirection=0;
    function nativeCashSessionClosed(){
      if(!isMotilal||!el('symbol').value.startsWith('NSE:')&&!el('symbol').value.startsWith('BSE:'))return false;
      const local=new Date(((statusFrame?.server_at||Date.now()/1000)+19800)*1000),minutes=local.getUTCHours()*60+local.getUTCMinutes();
      return [0,6].includes(local.getUTCDay())||minutes<555||minutes>=930;
    }
    function paintUnderlyingPrice(health){
      const symbol=el('symbol').value;
      if(lastUnderlyingSymbol!==symbol){lastUnderlyingSymbol=symbol;lastUnderlyingPrice=null;underlyingDirection=0;}
      const current=health.tickFresh&&Number.isFinite(statusFrame?.market?.tick_price)?statusFrame.market.tick_price:statusFrame?.forming?.close;
      const priceFresh=(health.chartFresh||health.tickFresh)&&Number.isFinite(current)&&current>0;
      if(priceFresh){if(lastUnderlyingPrice!==null&&current!==lastUnderlyingPrice)underlyingDirection=current>lastUnderlyingPrice?1:-1;lastUnderlyingPrice=current;}
      const label=isDelta?symbol+' perpetual':symbol+' underlying';
      const arrow=priceFresh?(underlyingDirection>0?'▲ ':underlyingDirection<0?'▼ ':''):'';underlyingPrice.style.color=!priceFresh||underlyingDirection===0?'#d1d4dc':underlyingDirection>0?'#26a69a':'#ef5350';
      underlyingPrice.textContent=label+' · '+arrow+(lastUnderlyingPrice===null?'Unavailable':price(lastUnderlyingPrice))+' · '+(priceFresh?'Live':health.text.startsWith('Market closed')?'Outside regular session':nativeCashSessionClosed()?'Market closed · native capture resumes next session':'Last known · feed delayed');
      underlyingPrice.title=isDelta?'Underlying perpetual traded price, not spot or option premium':'Selected underlying traded price';
    }
    let lastRunnerReceived=0,streamAttemptAt=0,streamEpoch=0,streamRecoveryAt=0,streamRecoveryBusy=false;
    let statusFrame=null,statusReceived=0,formingRecoveryAt=0,formingRecoveryBar=null,formingRecoveryCount=0;
    function paintStreamHealth(){if(chartSettingsError){el('stream-status').textContent='Chart blocked · check settings';el('stream-status').title=chartSettingsError;el('stream-status').setAttribute('aria-label',chartSettingsError);el('stream-status').dataset.live='false';return;}const health=chartStreamHealth(statusFrame||{},statusReceived?(performance.now()-statusReceived)/1000:Infinity);const presentation=feedPresentation(statusFrame||{},statusReceived?(performance.now()-statusReceived)/1000:Infinity);paintUnderlyingPrice(health);if(el('feed-health'))el('feed-health').textContent=feedHealthSummary(boundChartContext().basis==='draft'?{...(statusFrame||{}),confirmed_indicators:historyRows.length?{last_at:historyRows.at(-1).timestamp}:null,runner:null}:(statusFrame||{}),statusReceived?(performance.now()-statusReceived)/1000:Infinity);el('stream-status').textContent=(!lastRunner?.running&&!lastRunner?.position&&!lastRunner?.pending&&health.chartFresh)?'Chart live · Stopped · Next Start '+el('mode').value:presentation.label;if(nativeCashSessionClosed())el('stream-status').textContent='Market closed · Motilal capture waiting';el('stream-status').title=presentation.detail;el('stream-status').setAttribute('aria-label',presentation.detail);el('stream-status').dataset.live=String(streamConnected&&health.live);if(chartAnalysisReady&&rsiLine&&liveChartEnabled()&&!health.text.startsWith('Chart feed is live'))paintRsi(null,false,false);}
    setInterval(paintStreamHealth,1000);
    let lastStreamCandle='',lastStreamAnalysis='',stream=null,streamKey='',streamConnected=false,barBoundary=null,zoneBoundary=null,historicalMarkers=[],rangeLines=[],rangeKey=null;
    let drawingTools=null,drawingPriceSurface=null,closePriceLine=null,chartStyleScope='';
    const chartStyleKey=()=>['sector-pulse:chart-style:v1',pageParams.get('renkoAccount')||dhanAccount,el('symbol').value].join(':');
    function restoreChartStyle(){if(!el('symbol').value)return;const key=chartStyleKey();chartStyleScope=key;try{const saved=localStorage.getItem(key);if(['host','line','synthetic'].includes(saved))el('chart-view').value=saved;}catch{}}
    function paintPriceStyle(){if(!chart||!candles)return;const lineView=el('chart-view').value==='line';candles.applyOptions({visible:!lineView});if(!closePriceLine)closePriceLine=chart.addLineSeries({color:'#63b3ff',lineWidth:2,priceLineVisible:true,lastValueVisible:true,title:'Close',crosshairMarkerVisible:true,priceFormat:{type:'custom',minMove:.01,formatter:price}});closePriceLine.applyOptions({visible:lineView});closePriceLine.setData(lineView?currentPlotted.map(c=>Number.isFinite(c.close)?{time:c.time,value:c.close}:{time:c.time}):[]);}

    let selectionGuides=[],selectedExitLine;const studyPanes=new Map();let studyHoverTime=null;
    function selectedStudy(key,title,enabled,points){
      let pane=studyPanes.get(key);
      if(!pane&&enabled){
        const host=document.createElement('div');host.id='renko-'+key+'-study';host.className='renko-study-canvas';
        const parent=el('chart-stack'),next=el('rsi-chart').closest('section').nextSibling;
        const folded=chartFold(key,title,host,parent,next,true),value=document.createElement('b');value.className='renko-study-value';folded.summary.append(value);
        const view=root.LightweightCharts.createChart(host,{width:host.clientWidth,height:host.clientHeight||120,layout:{background:{color:'#131722'},textColor:'#d1d4dc'},timeScale:{timeVisible:true,tickMarkFormatter:t=>new Date(t*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false})},localization:{timeFormatter:stamp},rightPriceScale:{minimumWidth:110,borderColor:'#2a2e39'}}),series=view.addLineSeries({title,color:key==='adx'?'#e0b65f':'#4bb9ff',lineWidth:2,priceLineVisible:false});
        pane={host,view,series,fold:folded.fold,value,points:new Map(),latest:null};studyPanes.set(key,pane);bindChartInspection(host);
        const hover=coalescedHover(param=>syncRsiHover(param,true),requestAnimationFrame);
        view.subscribeCrosshairMove(param=>{if(!rsiCrosshairSync)hover(param);});
        chart.timeScale().subscribeVisibleLogicalRangeChange(range=>{if(range&&!pane.fold.hidden)pane.view.timeScale().setVisibleLogicalRange(range);});
        new ResizeObserver(()=>{if(host.clientWidth&&host.clientHeight&&pane.fold.open)view.applyOptions({width:host.clientWidth,height:host.clientHeight});}).observe(host);
        pane.fold.addEventListener('toggle',()=>{if(pane.fold.open&&host.clientWidth){view.applyOptions({width:host.clientWidth,height:host.clientHeight});const range=chart.timeScale().getVisibleLogicalRange();if(range)view.timeScale().setVisibleLogicalRange(range);}});
      }
      if(pane){pane.fold.hidden=!enabled;pane.points=new Map((enabled?points:[]).map(point=>[point.time,point.value]));pane.latest=enabled?points.at(-1):null;pane.series.setData(enabled?points:[]);paintStudyHover(pane,studyHoverTime);if(enabled){const range=chart.timeScale().getVisibleLogicalRange();if(range)pane.view.timeScale().setVisibleLogicalRange(range);}}
    }
    function paintStudyHover(pane,time){
      if(pane.fold.hidden)return;
      const observation=studyHoverValue(pane.points,pane.latest,time);
      pane.value.textContent=(observation.available?observation.value.toFixed(2):time===null?'Warming up':'Unavailable')+(observation.hovered?' · hovered':' · latest');
      pane.value.title=time===null?'Latest completed candle':'Hovered candle '+stamp(time)+' IST';
      pane.value.dataset.hoverTime=time===null?'':String(time);
      if(pane.fold.open&&pane.host.clientWidth&&pane.host.clientHeight&&observation.hovered&&observation.available)pane.view.setCrosshairPosition(observation.value,time,pane.series);else pane.view.clearCrosshairPosition();
    }
    function syncStudyPanes(time){studyHoverTime=time;for(const pane of studyPanes.values())paintStudyHover(pane,time);}
    function chartChoice(id){return effectiveChartChoice(values(),id);}
    function paintSelectedIndicators(){
      indicatorControls();
      el('primary-label-caption').textContent=el('timeframe').value+' Supertrend label';fiveMinuteLabelToggle.closest('label').hidden=!chartChoice('higher-timeframe-enabled-indicator');
      if(!chart)return;
      if(!chartAnalysisReady){for(const series of [line,fiveMinuteLine,ema10Line,ema30Line,ema100Line,syntheticLine,rsiLine,rsiSmaLine,selectedExitLine])series?.applyOptions({visible:false});supertrendPointerPoints=[];fiveMinutePointerPoints=[];paintSupertrendPointers();for(const pane of studyPanes.values()){pane.series.setData([]);pane.value.textContent='Withheld · chart agreement unavailable';}return;}
      for(const id of ['st','box'])el(id).parentElement.hidden=!(chartChoice('supertrend-enabled-indicator')||chartChoice('supertrend-exit-enabled-indicator'));
      const third=chartChoice('ema-third-enabled-indicator');const fast=chartChoice('ema-fast-enabled-indicator'),slow=chartChoice('ema-slow-enabled-indicator')||chartChoice('ema-slow-exit-enabled-indicator'),st=chartChoice('supertrend-enabled-indicator')||chartChoice('supertrend-exit-enabled-indicator'),htf=chartChoice('higher-timeframe-enabled-indicator');
      ema10Line?.applyOptions({visible:fast,title:'EMA '+chartControl('ema-fast-length').value});ema30Line?.applyOptions({visible:slow,title:'EMA '+chartControl('ema-slow-length').value});ema100Line?.applyOptions({visible:third&&historyRows.some(r=>Number.isFinite(r.ema100)),title:'EMA '+chartControl('ema-third-length').value});line?.applyOptions({visible:st,title:isEngine?'Renko Engine':chartControl('timeframe').value+' Supertrend'});fiveMinuteLine?.applyOptions({visible:htf});syntheticLine?.applyOptions({visible:false});
      rsiLine?.applyOptions({visible:chartChoice('rsi-slope-enabled-indicator')||chartChoice('rsi-exit-enabled-indicator')});rsiSmaLine?.applyOptions({visible:chartChoice('rsi-sma-enabled')});volumeSeries?.applyOptions({visible:el('volume-enabled').checked});
      if(chartChoice('ema-exit-enabled-indicator')){if(!selectedExitLine)selectedExitLine=chart.addLineSeries({color:'#ffbb55',lineWidth:1,priceLineVisible:false,title:'Exit EMA'});const period=Number(chartControl('ema-exit-length').value),alpha=2/(period+1);let value=null;selectedExitLine.applyOptions({visible:!fast||period!==Number(chartControl('ema-fast-length').value),title:'Exit EMA '+period});selectedExitLine.setData(historyRows.filter(r=>!r.is_forming).map(r=>{value=value===null?r.close:alpha*r.close+(1-alpha)*value;return {time:r.timestamp,value};}));}else selectedExitLine?.applyOptions({visible:false});
      if(isEngine)root.RenkoEngine.paintContext(chart,historyRows,values());
      supertrendPointerPoints=st?historyRows.map(r=>({time:r.timestamp,value:r.supertrend})):[];if(!htf)fiveMinutePointerPoints=[];paintSupertrendPointers();paintZones();
      for(const guide of selectionGuides)candles.removePriceLine(guide);selectionGuides=[];
      const latest=historyRows.at(-1);
      rsiLine?.applyOptions({title:'RSI '+chartControl('rsi-length').value});
      selectedStudy('adx','ADX',chartChoice('use-adx-indicator')||chartChoice('adx-exit-enabled-indicator'),historyRows.filter(r=>Number.isFinite(r.adx)).map(r=>({time:r.timestamp,value:r.adx})));
      selectedStudy('ema-gap','EMA widening · fast minus slow',chartChoice('ema-widening-enabled-indicator')||chartChoice('ema-widening-exit-enabled-indicator'),historyRows.filter(r=>Number.isFinite(r.ema_gap)).map(r=>({time:r.timestamp,value:r.ema_gap})));
      for(const id of ['rsi-readout','rsi-sma-readout'])if(el(id))el(id).hidden=id==='rsi-readout'?!(chartChoice('rsi-slope-enabled-indicator')||chartChoice('rsi-exit-enabled-indicator')):!chartChoice('rsi-sma-enabled');
      if(chartChoice('ema-proximity-enabled-indicator')&&Number.isFinite(latest?.ema10)){
        const distance=Number(chartControl('ema-proximity-distance').value),margin=chartControl('ema-proximity-mode').value==='ATR'?distance*latest.host_atr:distance;
        for(const [name,p]of [['EMA proximity upper',latest.ema10+margin],['EMA proximity lower',latest.ema10-margin]])selectionGuides.push(candles.createPriceLine({price:p,color:'#4bb9ff',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:name}));
      }
      if(chartChoice('market-structure-enabled-indicator')||chartChoice('market-structure-exit-enabled-indicator')){
        const rows=historyRows.filter(r=>!r.is_forming);let high=null,low=null;
        for(let i=2;i<rows.length-2;i++){const neighbors=rows.slice(i-2,i).concat(rows.slice(i+1,i+3));if(neighbors.every(r=>rows[i].high>r.high))high=rows[i].high;if(neighbors.every(r=>rows[i].low<r.low))low=rows[i].low;}
        for(const [name,p,color]of [['Swing high',high,'#ef5350'],['Swing low',low,'#26a69a']])if(p!==null)selectionGuides.push(candles.createPriceLine({price:p,color,lineWidth:1,lineStyle:2,axisLabelVisible:true,title:name}));
      }
      el('chart-description').textContent=(el('chart-view').value==='synthetic'?'Uniform Renko · box '+price(chart.uniformRenkoRows?.at(-1)?.box)+' · completed closes · two-box reversal':el('chart-view').value==='line'?'Line':'Candlesticks')+' · Selected overlays: '+[st?chartControl('timeframe').value+' Renko Supertrend':null,fast?'EMA '+chartControl('ema-fast-length').value:null,slow?'EMA '+chartControl('ema-slow-length').value:null,third?'EMA '+chartControl('ema-third-length').value:null,(chartChoice('ema-widening-enabled-indicator')||chartChoice('ema-widening-exit-enabled-indicator'))?'EMA widening':null,(chartChoice('rsi-slope-enabled-indicator')||chartChoice('rsi-exit-enabled-indicator'))?'RSI '+chartControl('rsi-length').value+' slope':null,(chartChoice('use-adx-indicator')||chartChoice('adx-exit-enabled-indicator'))?'ADX':null,htf?chartControl('supertrend-timeframe').value+' Supertrend':null,(chartChoice('market-structure-enabled-indicator')||chartChoice('market-structure-exit-enabled-indicator'))?'Confirmed swing high / low':null,chartChoice('ema-proximity-enabled-indicator')?'EMA proximity':null,chartChoice('zone-target-enabled-indicator')?'Strong 5m zones':null].filter(Boolean).join(' · ');
    }
    function paintRsi(point,provisional=false,fresh=true){if(!rsiLine)return;if(fresh&&point){rsiLine.update(point);rsiPoints.set(point.time,point.value);if(provisional)formingRsiPoint=point;}if(fresh)rebuildSma(true);else{const last=[...rsiSmaPoints.entries()].at(-1);el('rsi-sma-readout').textContent=`SMA ${smaPeriod()} · `+lastKnownIndicator(last?{value:last[1]}:null,false);}el('rsi-readout').textContent=!fresh?lastKnownIndicator(formingRsiPoint||confirmedRsiPoints.at(-1),false):point?.value==null?'Warming up':fmt(point.value)+' · zone '+rsiZone(point.value)+' · '+(provisional?'LIVE / provisional':'Confirmed');}
    function syncRsiHover(p,fromRsi){
      if(rsiCrosshairSync||!rsiChart||!chart||fromRsi&&!acceptInspectionHover())return;
      rsiCrosshairSync=true;
      try{
        const time=typeof p.time==='number'?p.time:null;if(time!==null){inspectedCandleTime=time;chart.timeScale().applyOptions({shiftVisibleRangeOnNewBar:false});const inspected=currentPlotted.find(c=>c.time===time);if(fromRsi&&inspected)readCandle(inspected,true);}const value=time===null?undefined:rsiPoints.get(time);
        syncStudyPanes(time);
        el('rsi-hover').textContent=time===null?'':`Hovered host candle ${stamp(time)} IST${chartChoice('rsi-slope-enabled-indicator')||chartChoice('rsi-exit-enabled-indicator')?' · RSI '+chartControl('rsi-length').value+' '+(Number.isFinite(value)?fmt(value):'unavailable / warming up'):''}${chartChoice('rsi-sma-enabled')?' · SMA '+smaPeriod()+' '+(Number.isFinite(rsiSmaPoints.get(time))?fmt(rsiSmaPoints.get(time)):'warming up'):''}${el('chart-view').value==='synthetic'?' · host RSI for synthetic body':''}`;
        if(time===null){chart.clearCrosshairPosition();rsiChart.clearCrosshairPosition();return;}
        if(fromRsi){const candle=currentPlotted.find(c=>c.time===time);if(candle)chart.setCrosshairPosition(candle.close,time,candles);else chart.clearCrosshairPosition();}
        else if(Number.isFinite(value)&&(chartChoice('rsi-slope-enabled-indicator')||chartChoice('rsi-exit-enabled-indicator')))rsiChart.setCrosshairPosition(value,time,rsiLine);else rsiChart.clearCrosshairPosition();
      }finally{rsiCrosshairSync=false;}
    }
    let entryPriceLine=null;
    function paintEntryPrice(){if(!candles)return;if(entryPriceLine)candles.removePriceLine(entryPriceLine);entryPriceLine=null;const entry=ownedEntryPrice(lastRunner,el('symbol').value);if(entry)entryPriceLine=candles.createPriceLine({...entry,title:entry.title+' '+price(entry.price),color:'#f0c75e',lineWidth:2,lineStyle:2,axisLabelVisible:true});}
    let previewBrickSeries=null,previewBrickFillSeries=null;
    function paintBrickPreview(forming,fresh=true){
      if(!chart)return;
      if(!el('brick-preview-status')){const note=document.createElement('small');note.id='renko-brick-preview-status';note.style.cssText='position:absolute;left:12px;bottom:10px;z-index:8;background:#131722e8;color:#b9cde4;padding:5px 8px;border:1px solid #34465b;border-radius:4px;pointer-events:none';el('chart').append(note);}
      if(!previewBrickSeries)previewBrickSeries=chart.addCandlestickSeries({borderVisible:true,wickVisible:false,priceLineVisible:false,lastValueVisible:false,title:''});
      if(!previewBrickFillSeries)previewBrickFillSeries=chart.addCandlestickSeries({borderVisible:false,wickVisible:false,priceLineVisible:false,lastValueVisible:false,title:''});
      const bricks=chart.uniformRenkoRows,box=bricks?.at(-1)?.box;
      const priceDriven=lastRunner?.config?.renko_confirmation==='PRICE';
      if(priceDriven&&forming)forming={...forming,timestamp:forming.stream_exchange_at||statusFrame?.market?.tick_exchange_at||forming.timestamp};
      const preview=fresh&&el('chart-view').value==='synthetic'?provisionalRenkoBricks(bricks,forming,box,priceDriven):[];
      previewBrickSeries.setData(preview);
      previewBrickFillSeries.setData(preview.filter(b=>b.progress>0).map(b=>({time:b.time,open:b.open,high:Math.max(b.open,b.fillClose),low:Math.min(b.open,b.fillClose),close:b.fillClose,color:b.close>b.open?'rgba(38,166,154,0.7)':'rgba(239,83,80,0.7)'})));
      el('brick-preview-status').hidden=!preview.length;
      if(preview.length)el('brick-preview-status').textContent=el('provisional-status').textContent='FORMING '+(preview[0].close>preview[0].open?'BULLISH':'BEARISH')+' RENKO · '+(preview.at(-1).progress*100).toFixed(2)+'% of target · visual preview only · no entry or exit until confirmed';
    }
    function paintMarkers(){paintEntryPrice();if(chart){let markers=executionMarkers(historicalMarkers,lastRunner,el('symbol').value,el('timeframe').value);if(chart.uniformRenkoRows)markers=markers.flatMap(m=>{const b=chart.uniformRenkoRows.find(b=>b.time===m.time)||chart.uniformRenkoRows.filter(b=>b.source_timestamp===Math.floor(m.time)).at(-1);return b?[{...m,time:b.time}]:[];});candles.setMarkers(markers);}}
    function paintPnl(s,connected=true){
      const p=pnlValues(s,connected),money=n=>isDelta?root.DeltaINR.format(n,s.pnl_currency||'USD'):n==null?'Unavailable':new Intl.NumberFormat('en-IN',{style:'currency',currency:isDelta?(s.pnl_currency||'USD'):'INR',signDisplay:'exceptZero'}).format(n);
      el('live-pnl').replaceChildren();
      const net=costPnlValues(s);
      const runningNet=s.position?(p.unrealized===null?null:net.total_net):net.realized_net;
      pnlSummary.textContent=money(Number.isFinite(runningNet)?runningNet:null);pnlSummary.style.color=runningNet==null||runningNet===0?'#d1d4dc':runningNet>0?'#26a69a':'#ef5350';pnlSummary.title='Running total after estimated costs';
      for(const [title,items]of [['Before costs · INR',[['Unrealized',p.unrealized],['Realized · run',p.realized],['Total · run',p.total]]],['After costs · estimate',[['Open liquidation',p.unrealized==null?null:net.unrealized_net],['Realized · run',net.realized_net],['Total · run',p.unrealized==null?null:net.total_net]]]]){
        const group=document.createElement('div');group.className='pnl-group';const heading=document.createElement('div');heading.className='pnl-group-title';heading.textContent=title;group.append(heading);
        for(const [label,n]of items){const d=document.createElement('div'),small=document.createElement('small'),b=document.createElement('b');small.textContent=label;b.textContent=money(n);b.style.color=n==null||n===0?'#d1d4dc':n>0?'#26a69a':'#ef5350';d.append(small,b);group.append(d);}el('live-pnl').append(group);
      }
      const context=document.createElement('div');context.className='pnl-context';
      const trade=(s.trade_history||[]).find(t=>t.lifecycle_id===s.position?.lifecycle_id),quote=trade?.valuation;
      const age=quote?.exchange_at?Math.max(0,Math.floor(Date.now()/1000-quote.exchange_at)):null;
      context.textContent=p.mode+' · '+(s.position?s.position.symbol+' · Qty '+s.position.quantity+' · Entry '+price(s.position.entry_price):'Flat · no open option')+(s.position?' · '+p.label:'')+(isMotilal?' · Motilal charges unverified':isDhan?' · Dhan estimated charges':isDelta?' · Native fees require broker evidence':' · Brokerage ₹15 / executed order');
      const lastTrade=trade||[...(s.trade_history||[])].reverse().find(t=>t.entry_filled);
      const prices=document.createElement('div');prices.className='pnl-group';
      const priceHeading=document.createElement('div');priceHeading.className='pnl-group-title';priceHeading.textContent='Held instrument prices';prices.append(priceHeading);
      const current=s.position&&connected&&s.pnl?.available===true?(quote?.price??quote?.bid):null;
      for(const [label,value,empty] of [['Entry',s.position?.entry_price??lastTrade?.entry_price,'Unavailable'],['Current',current,s.position?'Unavailable / stale':'No open position'],['Exit',lastTrade?.exit_filled?lastTrade.exit_price:null,'Not exited']]){
        const item=document.createElement('div'),caption=document.createElement('small'),amount=document.createElement('b');caption.textContent=label;amount.textContent=Number.isFinite(value)?price(value):empty;item.append(caption,amount);prices.append(item);
      }
      el('live-pnl').append(prices);
      const freshness=document.createElement('div');freshness.className='pnl-context';freshness.textContent=(quote?.exchange_at?'Option quote '+stamp(quote.exchange_at)+' IST · '+age+'s old':s.position?'Option quote timestamp unavailable':s.running?'Waiting for next eligible entry':'Runner stopped · no entry evaluation')+' · '+(s.status||'STOPPED')+(s.config?.underlying!==el('symbol').value?(s.config?' · Chart differs from runner '+s.config.underlying:' · No instance armed'):'');
      freshness.textContent+=' · Extra slippage '+(net.additional_slippage_points??0)+' premium pts / side';
      el('live-pnl').append(context,freshness);
      paintSideways(s);
    }
    function paintSideways(s){
      const v=s.sideways_status||{},lock=v.lock;
      el('sideways-status').textContent=!v.enabled?'Quick-loss range filter OFF':lock?.active?'QUICK-LOSS RANGE LOCK · '+price(lock.low)+' – '+price(lock.high)+' · strict breakout required':'Quick-loss range unlocked · max '+(v.max_candles||3)+' host candles · after-cost loss';
      const show=el('sideways-enabled').checked&&lock&&s.config?.underlying===el('symbol').value;
      const key=show?JSON.stringify([lock.low,lock.high,lock.active,v.enabled]):null;
      if(!candles||key===rangeKey)return;
      for(const line of rangeLines)candles.removePriceLine(line);rangeLines=[];rangeKey=key;
      if(show)for(const [name,price]of [['Position high',lock.high],['Position low',lock.low]])rangeLines.push(candles.createPriceLine({price,color:v.enabled&&lock.active?'#f2c14e':'#758696',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:name}));
    }
    let chartAnalysisReady=false,historyFailures=0,historyRetry=null,historyFailedAt=0,chartSettingsError=null;
    function historyDelay(error){if(chartSettingsFailure(error)){chartSettingsError=error.message;clearTimeout(historyRetry);stream?.close();streamConnected=false;el('history-health').textContent='Chart blocked: '+error.message+' Update the settings to retry.';paintStreamHealth();return;}if(isMotilal&&/No completed Renko host candles|history is warming up/i.test(error.message)){el('history-health').textContent='Motilal history warming up · no complete native candles yet · no alternate broker data';clearTimeout(historyRetry);historyRetry=setTimeout(()=>load(),30000);return;}historyFailures++;historyFailedAt ||= Date.now();el('history-health').textContent=(historyKey?'Showing last loaded history · ':'')+(historyFailures>=3?'History refresh keeps failing: '+error.message:'History refresh delayed · retrying in background')+(lastLoadAt?' · loaded '+stamp(lastLoadAt/1000)+' IST':'');clearTimeout(historyRetry);historyRetry=setTimeout(()=>load(),Math.min(30000,5000*historyFailures));}
    async function connectStream(){await root.BrokerForms.ready;if(!el('symbol').value)return;if(!isBatchChartView&&boundSelectionSymbol!==el('symbol').value){await bindDisplayedInstrument();if(boundSelectionSymbol!==el('symbol').value)return;}const key=JSON.stringify({instance:instanceId,...(isDelta?{execution_route:el('delta-execution-route').value,session_deadline:el('session-deadline').value,carry_policy:el('carry-policy').value}:{}),symbol:el('symbol').value,timeframe:chartControl('timeframe').value,...boundChartContext().settings,...(isEngine?root.RenkoEngine.executionSettings(values()):{})});if(key===streamKey&&stream&&stream.readyState!==2)return;stream?.close();const epoch=++streamEpoch;streamAttemptAt=performance.now();streamKey=key;lastStreamCandle='';lastStreamAnalysis='';barBoundary=null;zoneBoundary=null;streamConnected=false;statusFrame=null;statusReceived=0;paintStreamHealth();stream=new EventSource(root.BrokerForms.route('renko',apiBase+'stream?'+new URLSearchParams({instance:instanceId,...(isDelta?{execution_route:el('delta-execution-route').value,session_deadline:el('session-deadline').value,carry_policy:el('carry-policy').value}:{}),symbol:el('symbol').value,timeframe:chartControl('timeframe').value,...boundChartContext().settings}),root.BrokerForms.account('renko')));stream.onopen=()=>{if(epoch===streamEpoch)streamConnected=true;};stream.onerror=()=>{if(epoch!==streamEpoch||key!==streamKey)return;streamConnected=false;statusFrame=null;statusReceived=0;el('stream-status').dataset.live='false';if(chartAnalysisReady&&rsiChart)paintRsi(null,false,false);el('stream-status').textContent=chartSettingsError?'Chart blocked · check settings':'Feed delayed · reconnecting';el('stream-status').title='Disconnected · last known chart values retained; trading freshness remains required';if(lastRunner)paintPnl(lastRunner,false);};stream.addEventListener('state',event=>{if(epoch!==streamEpoch||key!==streamKey)return;const d=JSON.parse(event.data);streamConnected=true;if(d.runner&&d.runner_snapshot_fresh!==false){applyStatus(d.runner);}else{runnerStatusFresh=false;if(el('recovery-status'))el('recovery-status').textContent='Auto recovery · runner status stale; current health unconfirmed';syncChartControl();el('override-entry').disabled=true;if(lastRunner){paintPnl(lastRunner,false);paintAssessment();}}if(d.adopted_managers)managerTable(d.adopted_managers);
      const confirmed=d.confirmed_indicators;
      if(confirmed&&confirmed.run_id===boundChartContext().runId&&confirmed.revision!==confirmedRevision&&!busy){const previous=confirmedRevision;confirmedRevision=confirmed.revision;if(previous&&!busy)load();}
      if(d.display_analysis&&d.market?.fresh&&chartParity?.verified&&boundChartContext().basis!=='draft'&&liveSupertrendLine){
        const preview=d.display_analysis,base=confirmed?.latest;
        if(base&&preview.timestamp===base.timestamp+d.bar_seconds&&Number.isFinite(preview.supertrend)){
          liveSupertrendLine.setData([{time:base.timestamp,value:base.supertrend},{time:preview.timestamp,value:preview.supertrend}]);
          liveSupertrendLine.applyOptions({visible:chartChoice('supertrend-enabled-indicator')});
          el('provisional-status').textContent='Live provisional Supertrend '+price(preview.supertrend)+' · confirmed strategy unchanged';
        }
      }else if(liveSupertrendLine&&!d.market?.fresh)liveSupertrendLine.setData([]);
      if(chartAnalysisReady&&rsiLine&&JSON.stringify(d.forming)!==lastStreamCandle&&d.forming?.timestamp>rsiConfirmed.time&&d.market.fresh&&liveChartEnabled()){paintRsi(rsiStep(rsiConfirmed,d.forming.close,d.forming.timestamp,Number(chartControl('rsi-length').value)).point,true);}else if(chartAnalysisReady&&rsiLine&&!d.market.fresh&&liveChartEnabled()){paintRsi(null,false,false);}paintBrickPreview(d.forming,d.market?.fresh===true);statusFrame=d;statusReceived=performance.now();paintStreamHealth();const recoveryBar=Math.floor(d.server_at/d.bar_seconds);if(recoveryBar!==formingRecoveryBar||d.market?.fresh){formingRecoveryBar=recoveryBar;formingRecoveryCount=0;}if(!isDelta&&d.market?.connected&&!d.market?.fresh&&/forming OHLC|host candle open/i.test(d.market.error||'')&&liveChartEnabled()&&formingRecoveryCount<3&&Date.now()-formingRecoveryAt>=10000){formingRecoveryCount++;formingRecoveryAt=Date.now();load();}if(d.market?.fresh&&d.forming&&JSON.stringify(d.forming)!==lastStreamCandle&&chart&&el('chart-view').value!=='synthetic'&&liveChartEnabled()){const c=d.forming;lastStreamCandle=JSON.stringify(c);if(c.timestamp>=currentPlotted.at(-1)?.time){candles.update({time:c.timestamp,open:c.open,high:c.high,low:c.low,close:c.close});if(el('chart-view').value==='line')closePriceLine?.update({time:c.timestamp,value:c.close});if(chartAnalysisReady)paintZones(zoneRows,c.timestamp);volumeSeries.update(volumePoints({rows:[c]})[0]);readCandle({...c,time:c.timestamp});}}if(d.market?.fresh&&chartAnalysisReady&&el('chart-view').value!=='synthetic'&&d.display_analysis&&boundChartContext().basis==='draft'&&JSON.stringify(d.display_analysis)!==lastStreamAnalysis&&chart&&liveChartEnabled()){const a=d.display_analysis;el('rsi-htf-chart').textContent=(boundChartContext().basis==='draft'?'Draft chart settings · ':'Runner chart settings · ')+rsiHtfSummary(a.mtf_rsi);lastStreamAnalysis=JSON.stringify(a);if(a.timestamp>=currentPlotted.at(-1)?.time){paintZones(zoneRows,a.timestamp);ema10Line.update({time:a.timestamp,value:a.ema10});ema30Line.update({time:a.timestamp,value:a.ema30});line.update({time:a.timestamp,value:a.supertrend,color:a.pine_direction<0?'#26a69a':'#ef5350'});if(el('chart-view').value==='synthetic'){candles.update({time:a.timestamp,open:a.synthetic_open,high:Math.max(a.synthetic_open,a.synthetic_close),low:Math.min(a.synthetic_open,a.synthetic_close),close:a.synthetic_close});syntheticLine.update({time:a.timestamp,value:a.synthetic_close});readCandle({time:a.timestamp,open:a.synthetic_open,high:Math.max(a.synthetic_open,a.synthetic_close),low:Math.min(a.synthetic_open,a.synthetic_close),close:a.synthetic_close});}}}const boundary=Math.floor(d.server_at/d.bar_seconds);const fiveBoundary=Math.floor(d.server_at/300);if((barBoundary!==null&&boundary!==barBoundary)||(zoneBoundary!==null&&fiveBoundary!==zoneBoundary))load();barBoundary=boundary;zoneBoundary=fiveBoundary;});}
    let chartBasisPreview=false,chartBasisKey='',chartParity=null,confirmedRevision=null;
    const basisLabel=document.createElement('label');basisLabel.className='field';basisLabel.textContent='Chart calculation source';
    const basisSelect=document.createElement('select');basisSelect.id='renko-chart-basis';basisSelect.setAttribute('aria-label','Chart calculation source');
    basisSelect.add(new Option('Selected instrument · active runner when matching','runner'));basisSelect.add(new Option('Draft preview · no execution','draft'));basisLabel.append(basisSelect);
    const basisNote=document.createElement('div');basisNote.id='renko-chart-basis-note';basisNote.setAttribute('role','status');basisNote.style.cssText='flex-basis:100%;padding:8px 10px;border:1px solid #789bc5;border-radius:5px;color:#d1d4dc;font-size:12px';
    const healthNote=document.createElement('div');healthNote.id='renko-feed-health';healthNote.setAttribute('role','status');healthNote.style.cssText='flex-basis:100%;font-size:12px;color:#a9bbcd;padding:6px 0';
    el('chart-toolbar').append(basisLabel,basisNote,healthNote);
    function liveChartEnabled(){return boundChartContext().basis!=='draft'||el('history-preset').value!=='custom';}
    function boundChartContext(){return isEngine?{basis:'draft',settings:chartSettings(values()),history:{},differences:[],label:'Renko Engine chart settings'}:runnerChartContext(values(),lastRunner,chartBasisPreview);}
    function chartControl(id){
      const actual=el(id),context=boundChartContext();if(context.basis==='draft'||id.endsWith('-indicator'))return actual;
      const key=id==='rsi-length'?'rsi_slope_length':id.replaceAll('-','_');
      return Object.hasOwn(context.settings,key)?{value:String(context.settings[key]),checked:context.settings[key]===true}:actual;
    }
    function paintChartBasis(){
      const context=boundChartContext();basisNote.textContent=context.label+(context.basis!=='draft'?(chartParity?' · '+chartParity.reason:' · loading matching chart'):'')+(chartParity?.blocked?' · Indicators show chart-only calculations from validated broker candles; not verified runner values.':'');
      basisNote.dataset.basis=context.basis;basisNote.dataset.verified=String(!!chartParity?.verified);basisNote.dataset.runId=context.runId||'';
      basisNote.style.borderColor=context.basis==='draft'?'#e7af67':chartParity?.blocked?'#f85149':'#789bc5';
    }
    basisSelect.onchange=()=>{chartBasisPreview=basisSelect.value==='draft';chartParity=null;version++;historyKey='';historyRevision=null;streamKey='';clearAnalysis();paintChartBasis();connectStream();load();};
    const chartTimeframeLabel=document.createElement('label');chartTimeframeLabel.className='field';chartTimeframeLabel.textContent='Chart & runner timeframe';
    const chartTimeframe=el('timeframe');chartTimeframeLabel.append(chartTimeframe);el('chart-toolbar').prepend(chartTimeframeLabel);
    // One authoritative timeframe; the launch selector mirrors the chart control.
    const runnerTimeframeRow=document.createElement('label');runnerTimeframeRow.className='field';runnerTimeframeRow.textContent='Runner timeframe';
    const runnerTimeframe=document.createElement('select');runnerTimeframe.id='renko-runner-timeframe';runnerTimeframe.setAttribute('aria-label','Runner timeframe');
    for(const option of chartTimeframe.options)runnerTimeframe.add(new Option(option.text,option.value));runnerTimeframe.value=chartTimeframe.value;
    executionRail.insertBefore(el('strategy-basis').closest('label'),el('lots').closest('label'));
    runnerTimeframeRow.append(runnerTimeframe);executionRail.insertBefore(runnerTimeframeRow,el('lots').closest('label'));
    runnerTimeframe.addEventListener('change',()=>{chartTimeframe.value=runnerTimeframe.value;chartTimeframe.dispatchEvent(new Event('change'));});
    const parameterHelp=root.SectorPulseHelp?.parameters||{};
    const helpTip=document.createElement('div');helpTip.id='renko-parameter-tooltip';helpTip.setAttribute('role','tooltip');helpTip.hidden=true;helpTip.style.cssText='position:fixed;z-index:2147483647;max-width:min(420px,calc(100vw - 32px));padding:12px 14px;border:1px solid #789bc5;border-radius:8px;background:#101c2d;color:#e5edf7;box-shadow:0 8px 30px #0008;font:13px/1.5 Arial;pointer-events:none';document.body.append(helpTip);
    const hideParameterHelp=()=>{helpTip.hidden=true;};
    for(const [id,text]of Object.entries(parameterHelp)){
      const input=el(id),label=input?.closest('label');if(!label)continue;input.title=text;label.title=text;
      const button=document.createElement('button');button.type='button';button.className='renko-parameter-help';button.textContent='ⓘ';button.setAttribute('aria-label','Help: '+(input.getAttribute('aria-label')||label.firstChild?.textContent||id).trim());button.setAttribute('aria-describedby',helpTip.id);button.style.cssText='display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;min-width:24px;padding:0;margin:0 0 0 6px;border:1px solid #6784a7;border-radius:50%;background:transparent;color:#b9d7fa;cursor:help;font:14px Arial';label.append(button);
      const show=()=>{helpTip.textContent=text;helpTip.hidden=false;const rect=button.getBoundingClientRect(),height=helpTip.getBoundingClientRect().height;helpTip.style.left=Math.max(16,Math.min(rect.left,innerWidth-440))+'px';helpTip.style.top=Math.max(12,Math.min(rect.bottom+8,innerHeight-height-16))+'px';};
      label.addEventListener('mouseenter',show);label.addEventListener('mouseleave',hideParameterHelp);input.addEventListener('focus',show);input.addEventListener('blur',hideParameterHelp);button.addEventListener('focus',show);button.addEventListener('blur',hideParameterHelp);button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();show();});
    }
    document.addEventListener('keydown',event=>{if(event.key==='Escape')hideParameterHelp();});document.addEventListener('scroll',hideParameterHelp,true);root.addEventListener('resize',hideParameterHelp);

    const timeframeNote=document.createElement('span');timeframeNote.id='renko-timeframe-state';timeframeNote.setAttribute('role','status');el('chart-toolbar').append(timeframeNote);
    let timeframeBusy=false;
    chartTimeframe.addEventListener('change',async()=>{
      if(timeframeBusy)return;
      const target=chartTimeframe.value;
      if(!lastRunner?.config){timeframeNote.textContent='Timeframe selected for next Start.';return;}
      timeframeBusy=true;chartTimeframe.disabled=true;
      try{
        const current=await request('runner');
        if(current.config?.underlying!==el('symbol').value)throw Error('Displayed instrument differs from the runner; select its instrument first.');
        const result=await request('chart-timeframe',{run_id:current.run_id,underlying:current.config.underlying,mode:current.config.mode,timeframe:target});
        applyStatus(result);connectStream();clearAnalysis();load();
      }catch(error){timeframeNote.textContent='Timeframe change not applied: '+error.message;el('action-error').textContent=error.message;el('action-error').hidden=false;}
      finally{timeframeBusy=false;chartTimeframe.disabled=false;}
    });
    el('reset-chart').onclick=()=>{if(chart)el('readable-chart').onclick();};el('readable-chart').onclick=()=>{if(!chart||!plottedCount)return;const view=readableChartViewport(el('chart').clientWidth,el('chart').clientHeight,plottedCount);chart.applyOptions({width:el('chart').clientWidth,height:el('chart').clientHeight});chart.priceScale('right').applyOptions({autoScale:true,scaleMargins:view.scaleMargins});chart.timeScale().applyOptions({rightOffset:view.rightOffset,barSpacing:view.spacing});const range=isMotilal?{from:Math.min(view.range.from,plottedCount-Math.ceil(el("chart").clientWidth/view.spacing)),to:view.range.to}:view.range;const latestTime=currentPlotted.at(-1)?.time,x=Number.isFinite(latestTime)?chart.timeScale().timeToCoordinate(latestTime):null,latest=Number.isFinite(x)?chart.timeScale().coordinateToLogical(x):null;if(Number.isFinite(latest)){const shift=latest-(plottedCount-1);range.from+=shift;range.to+=shift;}chart.timeScale().setVisibleLogicalRange(range);rsiChart?.timeScale().setVisibleLogicalRange(range);positionAssessment();};el('fit-chart').onclick=()=>chart?.timeScale().fitContent();el('full-chart').onclick=()=>{const target=el('chart-stack');if(document.fullscreenElement)document.exitFullscreen();else target.requestFullscreen();};
    let inspectionCard=null,inspectionCardKey='',inspectionPinnedTime=null;
    function renderCandleInspection(time){
      if(!Number.isFinite(time))return;
      inspectionPinnedTime=time;
      const context=boundChartContext(),matching=lastRunner?.config?.underlying===el('symbol').value&&lastRunner.config.timeframe===chartControl('timeframe').value;
      const plotted=currentPlotted.find(c=>c.time===time),preview=statusFrame?.display_analysis;
      const forming=plotted?.source_timestamp!=null?false:time>(historyRows.filter(r=>!r.is_forming).at(-1)?.timestamp??Infinity);
      const evidenceRows=forming&&plotted?[...historyRows,{...plotted,...(preview?.timestamp===time?preview:{}),timestamp:time,rsi14:rsiPoints.get(time),provisional:true}]:historyRows;
      const model=candleInspection({time,symbol:el('symbol').value,timeframe:chartControl('timeframe').value,settings:context.settings,state:context.basis==='draft'?null:lastRunner,rows:evidenceRows,forming});
      const key=JSON.stringify(model);if(key===inspectionCardKey)return;inspectionCardKey=key;
      if(!inspectionCard){
        inspectionCard=document.createElement('details');inspectionCard.className='renko-candle-inspection';inspectionCard.id='renko-candle-inspection';
        try{inspectionCard.open=localStorage.getItem('sector-pulse:candle-inspection:'+instanceId)!=='collapsed';}catch{inspectionCard.open=true;}
        const summary=document.createElement('summary');summary.textContent='Candle inspection';inspectionCard.append(summary);
        const body=document.createElement('div');body.className='renko-inspection-body';inspectionCard.append(body);
        inspectionCard.addEventListener('toggle',()=>{try{localStorage.setItem('sector-pulse:candle-inspection:'+instanceId,inspectionCard.open?'open':'collapsed');}catch{}});
        el('chart').after(inspectionCard);
        if(!document.getElementById('renko-inspection-style')){
          const style=document.createElement('style');style.id='renko-inspection-style';style.textContent='.renko-candle-inspection{box-sizing:border-box;width:100%;max-width:100%;margin:12px 0;border:1px solid #334154;border-radius:10px;background:#172132;color:#d9e2f0;min-width:0}.renko-candle-inspection>summary{padding:12px 15px;font:600 13px Arial;cursor:pointer;overflow-wrap:anywhere}.renko-inspection-body{padding:0 15px 15px;max-height:340px;overflow:auto;overscroll-behavior:contain}.renko-inspection-context{font:12px/1.6 Arial;color:#a7bad4;margin-bottom:12px;overflow-wrap:anywhere}.renko-inspection-checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.renko-inspection-rule{padding:11px 12px;background:#1a2639;border:1px solid #334154;border-radius:6px;min-width:0;overflow-wrap:anywhere}.renko-inspection-rule header{display:flex;justify-content:space-between;gap:10px;align-items:start;font:600 12px Arial}.renko-inspection-rule small{display:block;font:11px/1.6 Arial;color:#a7bad4;margin-top:5px}.renko-inspection-badge{font:600 10px/1.4 Menlo,monospace;white-space:nowrap;color:#a7bad4}.renko-inspection-badge[data-status=PASS]{color:#79cbbd}.renko-inspection-badge[data-status=FAIL]{color:#e6a5a5}.renko-inspection-badge[data-status=WAIT]{color:#e0bf7c}.renko-inspection-settings{margin-top:12px;font:12px/1.6 Arial}.renko-inspection-settings dl{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:5px 12px}.renko-inspection-settings dt,.renko-inspection-settings dd{margin:0;overflow-wrap:anywhere}.renko-inspection-settings dd{color:#a7bad4}@media(max-width:700px){.renko-candle-inspection{max-width:calc(100vw - 64px)}.renko-inspection-checks{grid-template-columns:minmax(0,1fr)}.renko-inspection-body{padding:0 10px 10px;max-height:280px}.renko-candle-inspection>summary{padding:11px 10px}}';document.head.append(style);
        }
      }
      inspectionCard.hidden=false;
      inspectionCard.querySelector('summary').textContent='Candle inspection · '+stamp(time)+' IST · '+(forming?'forming':'completed')+' · '+(model.source.startsWith('Recorded')?'runner record':'reconstructed');
      const body=inspectionCard.querySelector('.renko-inspection-body');body.replaceChildren();
      const contextLabel=document.createElement('div');contextLabel.className='renko-inspection-context';contextLabel.textContent=model.configSource+(model.mode?' · '+model.mode:'')+' · '+model.source+'\n'+model.reason;body.append(contextLabel);
      const checks=document.createElement('div');checks.className='renko-inspection-checks';body.append(checks);
      for(const check of model.checks){
        const row=document.createElement('article');row.className='renko-inspection-rule';
        const head=document.createElement('header'),label=document.createElement('span'),badge=document.createElement('span');label.textContent=check.name;badge.className='renko-inspection-badge';badge.dataset.status=check.status;badge.textContent=check.status;head.append(label,badge);row.append(head);
        for(const value of [check.rule,check.observed,check.reason]){const small=document.createElement('small');small.textContent=value;row.append(small);}checks.append(row);
      }
      const settings=document.createElement('details');settings.className='renko-inspection-settings';const title=document.createElement('summary');title.textContent='All indicator and entry settings';settings.append(title);const list=document.createElement('dl');for(const setting of model.settings){const name=document.createElement('dt'),value=document.createElement('dd');name.textContent=setting.name;value.textContent=setting.value;list.append(name,value);}settings.append(list);body.append(settings);
    }

    let inspectedCandleTime=null,latestReadoutCandle=null,hoverInside=false,hoverRevision=0,renderedHoverRevision=0;
    function acceptInspectionHover(){if(!hoverInside||hoverRevision===renderedHoverRevision)return false;renderedHoverRevision=hoverRevision;return true;}
    function bindChartInspection(surface){
      surface.addEventListener('pointermove',()=>{hoverInside=true;hoverRevision++;},true);
      surface.addEventListener('pointerleave',()=>{hoverInside=false;renderedHoverRevision=++hoverRevision;inspectedCandleTime=null;chart?.timeScale().applyOptions({shiftVisibleRangeOnNewBar:true});readCandle(latestReadoutCandle);});
    }
    for(const paneId of ['chart','rsi-chart'])bindChartInspection(el(paneId));
    function readCandle(c,hover=false){if(c&&el('chart-view').value==='synthetic'&&!c.source_timestamp){const brick=currentPlotted.find(b=>b.time===c.time);if(brick)c={...c,...brick};}if(hover){inspectedCandleTime=c?.time??null;renderCandleInspection(inspectedCandleTime);chart?.timeScale().applyOptions({shiftVisibleRangeOnNewBar:false});}else{latestReadoutCandle=c;if(inspectedCandleTime!==null)return;}if(!c||!Number.isFinite(c.close)){el('candle-readout').textContent=c?'Invalid broker candle · '+stamp(c.time)+' IST · OHLC unavailable':'';return;}el('candle-readout').textContent=`${el('symbol').value} · ${chartControl('timeframe').value} · ${el('chart-view').value!=='synthetic'?'Broker OHLC':'Renko brick · box '+price(c.box)} · ${stamp(c.source_timestamp??c.time)} IST · O ${price(c.open)} · H ${price(c.high)} · L ${price(c.low)} · C ${price(c.close)}`;}
    const storage=(isEngine?'sector-pulse:renko-engine-settings-v3':'sector-pulse:renko-supertrend-settings-v3')+(isMotilal?':MOTILAL_OSWAL:'+dhanAccount:isDelta?':DELTA_INDIA':'')+(instanceId!=='default'?':'+instanceId:'');
    try{const rawSaved=JSON.parse(localStorage.getItem(storage)||'null'),saved=rawSaved?inheritRsiHtfFields(migrateDestinations(rawSaved)):null;if(saved){if(!saved['strategy-basis'])saved['strategy-basis']='LEGACY';if(saved.symbol)el('symbol').add(new Option(saved.symbol,saved.symbol));for(const id of allIds)if(saved[id]!=null){if((el(id).type==='checkbox'))el(id).checked=saved[id]===true;else el(id).value=saved[id];}}else if(!isEngine&&!isDelta&&!isMotilal&&instanceId==='default'){const previous=JSON.parse(localStorage.getItem('sector-pulse:renko-supertrend-settings-v2')||localStorage.getItem('sector-pulse:renko-supertrend-settings-v1')||'null');if(previous){if(previous.symbol)el('symbol').add(new Option(previous.symbol,previous.symbol));for(const id of allIds)if(!['use-adx','widening-window'].includes(id)&&previous[id]!=null)el(id).value=previous[id];}}}catch{}
    function deltaFutures(){return isDelta&&el('delta-execution-route').value==='DELTA_PERPETUAL';}
    function cashEquity(){return !isDelta&&!isDhan&&['NSE_EQUITY','BSE_EQUITY'].includes(el('market').value);}
    function displayedAlreadyActive(symbol){
      return lastInstanceRows.some(v=>v.broker===selectedBroker&&(v.instrument||v.config?.underlying)===symbol&&(v.running||v.position||v.pending));
    }
    function syncActiveStartButtons(){
      if(isBatchChartView)return;
      const displayed=displayedAlreadyActive(el('symbol').value);
      const start=el('toggle');
      if(start.textContent.startsWith('Start displayed')&&displayed)start.disabled=true;
      const selected=Array.from(el('batch-symbols').selectedOptions).map(o=>o.value);
      const batch=el('start-selected');
      if(selected.length&&selected.every(displayedAlreadyActive))batch.disabled=true;
      for(const b of [start,batch]){
        b.style.opacity=b.disabled?'0.45':'1';b.style.cursor=b.disabled?'not-allowed':'pointer';
      }
    }
    function controls(){if(el('reset-settings'))el('reset-settings').disabled=!lastRunner||!!(lastRunner.running||lastRunner.position||lastRunner.pending);releaseActiveFormLocks();synchronizeActiveRunnerForm(lastRunner);if(el('runner-timeframe'))el('runner-timeframe').value=el('timeframe').value;if(isMotilal){const minutes={'1 minute':1,'2 minutes':2,'3 minutes':3,'5 minutes':5,'10 minutes':10,'15 minutes':15,'30 minutes':30,'1 hour':60};const host=minutes[el('timeframe').value],higher=minutes[el('supertrend-timeframe').value];if(higher<=host){const paired={'1 minute':'5 minutes','5 minutes':'15 minutes'}[el('timeframe').value]||Object.keys(minutes).find(key=>minutes[key]>host);if(paired)el('supertrend-timeframe').value=paired;}}
      for(const input of section.querySelectorAll('[data-exit-locked]')){input.disabled=input.dataset.exitLocked==='true';delete input.dataset.exitLocked;}

      for(const input of section.querySelectorAll('[data-family-disabled]')){input.disabled=input.dataset.familyDisabled==='true';delete input.dataset.familyDisabled;}

      el('delta-execution-field').hidden=!isDelta;
      el('delta-execution-route').disabled=!isDelta||lastRunner?.delta_perpetual_revision!=='delta-perpetual-v1';
      if(isDelta){
        el('delta-execution-route').title=lastRunner?.delta_perpetual_revision==='delta-perpetual-v1'?'Selection applies on the next Start; active exposure keeps its saved product.':'Perpetual support awaits backend restart.';
        el('max-premium').closest('label').firstChild.textContent=deltaFutures()?'Per-entry notional cap · native quote currency (optional)':'Premium cap · native quote currency (optional)';
        el('daily-budget').closest('label').firstChild.textContent=deltaFutures()?'Daily entry risk budget · full notional + realized losses (optional)':'Daily loss budget · native quote currency (optional)';
        el('trailing-basis').options[0].text=deltaFutures()?'Perpetual executable price · percent':'Option executable bid · percent';
        el('sideways-enabled').title=deltaFutures()?'Funding evidence unavailable; clear this optional after-cost filter before starting perpetual futures.':'';
      }
el('ema-momentum-enabled').disabled=lastRunner?.entry_momentum_revision!=='split-proximity-momentum-v1';el('ema-momentum-enabled').title=el('ema-momentum-enabled').disabled?'Backend activation pending; current runner rules retained.':'Requires proximity ON at 0.5 ATR. Retests retain baseline; momentum needs a new completed qualification. Changes apply on next Start.';el('higher-timeframe-enabled').disabled=lastRunner?.mtf_supertrend_revision!=='optional-selected-htf-supertrend-v2';el('higher-timeframe-enabled').title=el('higher-timeframe-enabled').disabled?'Backend update pending safe restart; existing runner settings retained.':'Completed host and selected higher-timeframe Supertrend must agree for normal entries.';if(isDelta)el('session-deadline').disabled=el('carry-policy').value==='CONTINUOUS';const rsiReady=['renko-supertrend-assessment-recovery-v14','renko-supertrend-rsi-slope-v13'].includes(lastRunner?.runtime_revision)||(isDelta&&lastRunner?.runtime_revision==='renko-delta-paper-capital-v4');el('rsi-slope-enabled').disabled=!rsiReady;el('rsi-slope-status').textContent=rsiReady?'Optional entry filter; no RSI zone thresholds. '+(lastRunner?.config?.rsi_slope_enabled?'ON in runner':'OFF in runner')+'. New setups default OFF; changes apply on next Start.':'RSI slope prepared; backend activation pending. Current runner retains its existing entry rules.';if(isDelta)for(const id of ['max-premium','daily-budget','spot-target','spot-stop']){let note=el(id+'-inr');if(!note){note=document.createElement('small');note.id='renko-'+id+'-inr';el(id).after(note);}note.textContent=el(id).value===''?'Blank disables this limit.':'INR equivalent · '+root.DeltaINR.format(el(id).value,'USD');}el('paper-capital').closest('label').hidden=el('mode').value!=='PAPER';const mcx=!isDelta&&(el('market').value==='MCX'||el('symbol').value.startsWith('MCX:'));el('commodity-holding-field').hidden=!mcx;if(!el('market-policy-note')){const n=document.createElement('p');n.id='renko-market-policy-note';n.className='renko-small';el('cash-note').after(n);}el('market-policy-note').textContent=isDelta?(el('carry-policy').value==='CONTINUOUS'?(deltaFutures()?'Crypto perpetual · continuous; no expiry or daily cutoff. Long bullish / short bearish; full notional collateral reserve.':'Crypto · continuous; no daily market close or midnight square-off. Exact held option expiry applies.'):'Crypto trades 24/7 · Daily cutoff selected: '+el('session-deadline').value+' IST (saved strategy risk policy). Choose Continuous trading above for no daily cutoff; changes apply on next Start.'):(cashEquity()&&el('cash-product').value==='CNC'?'Cash delivery · overnight carry; regular market-session signal exits.':el('market').value==='MCX'||el('symbol').value.startsWith('MCX:')?'MCX · cutoff follows the selected contract’s verified regular-session end.':'NSE/BSE · intraday strategy cutoff 15:10 IST; normal market close is later.');if(!isDelta&&el('symbol').value&&el('market-policy-note').dataset.symbol===el('symbol').value&&!(cashEquity()&&el('cash-product').value==='CNC'))el('market-policy-note').textContent=el('market-policy-note').dataset.policy;if(mcx&&el('commodity-holding').value==='CARRY_FORWARD')el('market-policy-note').textContent='MCX · overnight MARGIN options; no session-end or midnight square-off. Stops and signal exits remain active in regular sessions. Pre-expiry exit: prior weekday session end minus 30 minutes; broker RMS may act earlier.';if(isDelta){el('session-deadline').disabled=el('carry-policy').value==='CONTINUOUS';}const cash=cashEquity();const live=el('mode').value==='LIVE';executionRail.classList.toggle('is-live',live);modeNote.classList.toggle('is-live',live);modeNote.textContent=live?'Live selected · real '+brokerName+' orders when you press Start.': 'Paper selected · simulated fills; no broker orders.';if(live&&lastRunner&&!lastRunner.live_available)modeNote.textContent='Live unavailable · the existing runtime gate is off.';if(!owned&&!running&&!toggleBusy){el('toggle').textContent='Start displayed · '+(live?'Live':'Paper');el('toggle').disabled=!el('symbol').value||(live&&lastRunner&&!lastRunner.live_available);}const selectedCount=el('batch-symbols').selectedOptions.length;batchSummary.textContent='Batch selection · '+selectedCount+' selected';const cashReady=['renko-supertrend-assessment-recovery-v14','renko-supertrend-cash-equity-v10','renko-supertrend-mcx-carry-v11','renko-supertrend-ema-timing-v12','renko-supertrend-rsi-slope-v13'].includes(lastRunner?.runtime_revision);if((cash&&!cashReady)||(mcx&&el('commodity-holding').value==='CARRY_FORWARD'&&!['renko-supertrend-assessment-recovery-v14','renko-supertrend-mcx-carry-v11','renko-supertrend-ema-timing-v12','renko-supertrend-rsi-slope-v13'].includes(lastRunner?.runtime_revision))){el('toggle').disabled=true;el('start-selected').disabled=true;}else if(!toggleBusy){el('start-selected').disabled=selectedCount===0||(live&&lastRunner&&!lastRunner.live_available)||lastRunner?.indicator_selection_revision!=='independent-indicators-v1';}el('sideways-enabled').title=cash?'Cash charge model is unavailable; after-cost sideways filtering cannot be enabled for cash equity.':'';el('cash-product-field').hidden=!cash;el('cash-note').hidden=!cash;el('cash-note').textContent=el('cash-product').value==='CNC'?'Quantity is whole shares. Carry forward uses CNC delivery: bought shares can stay overnight; new bearish short entries are blocked. Bearish signals still exit held long shares. Delivery exits require broker sell authorization.':'Quantity is whole shares. Intraday cash buys bullish signals and sells bearish signals short; exits close the held side. Strategy square-off: 15:10 IST.';if(cash&&el('sideways-enabled').checked)el('cash-note').textContent+=' Clear the optional after-cost sideways filter before starting cash equity; its cash fee model is unavailable.';el('lots').closest('label').firstChild.textContent=cash?'Quantity':isDelta?(deltaFutures()?'Whole perpetual contracts':'Whole option contracts'):'Lots';el('lots').setAttribute('aria-label',cash?'Quantity':'Lots');el('lots').max=cash?'1000000':'100';el('lots').title=cash?(el('cash-product').value==='CNC'?'Exact whole-share quantity; delivery buys only, bearish new shorts blocked.':'Exact whole-share quantity; bullish buys / bearish sells intraday.'):(isDelta?(deltaFutures()?'Whole perpetual contracts using verified broker contract units; full notional collateral required.':'Whole option contracts.'):'Whole derivative lots.');el('start-selected').textContent='Start selected · '+el('mode').value;el('retest-status').textContent=!['renko-supertrend-assessment-recovery-v14','renko-supertrend-rsi-slope-v13','renko-supertrend-ema-timing-v12','renko-supertrend-mcx-carry-v11','renko-supertrend-cash-equity-v10','renko-supertrend-confirmed-ema-retest-v9','renko-delta-shared-engine-v1','renko-delta-continuous-v2','renko-delta-inr-display-v3','renko-delta-paper-capital-v4'].includes(lastRunner?.runtime_revision)?'Retest update pending: the active runner keeps its existing entry rules.':'Retest confirmation '+(lastRunner?.config?.retest_enabled?'ON in runner':'OFF in runner')+' · pattern selections apply on the next Start Runner.';for(const id of ['retest-engulfing','retest-harami','retest-star'])el(id).disabled=!(el('retest-enabled').checked||chartChoice('retest-enabled-indicator'))||!['renko-supertrend-assessment-recovery-v14','renko-supertrend-rsi-slope-v13','renko-supertrend-ema-timing-v12','renko-supertrend-mcx-carry-v11','renko-supertrend-cash-equity-v10','renko-supertrend-confirmed-ema-retest-v9','renko-delta-shared-engine-v1','renko-delta-continuous-v2','renko-delta-inr-display-v3','renko-delta-paper-capital-v4'].includes(lastRunner?.runtime_revision);el('retest-enabled').disabled=!['renko-supertrend-assessment-recovery-v14','renko-supertrend-rsi-slope-v13','renko-supertrend-ema-timing-v12','renko-supertrend-mcx-carry-v11','renko-supertrend-cash-equity-v10','renko-supertrend-confirmed-ema-retest-v9','renko-delta-shared-engine-v1','renko-delta-continuous-v2','renko-delta-inr-display-v3','renko-delta-paper-capital-v4'].includes(lastRunner?.runtime_revision);el('retest-enabled').title=el('retest-enabled').disabled?'Retest backend update awaits a stopped runner.':'Touch prior completed EMA10; matching selected pattern confirms within 3 completed candles and closes on trend side. Widening not required; one entry per touch episode.';for(const id of ['ema-proximity-mode','ema-proximity-distance'])el(id).disabled=!(el('ema-proximity-enabled').checked||chartChoice('ema-proximity-enabled-indicator'));for(const id of ['trailing-basis','trailing-distance'])el(id).disabled=!el('trailing-enabled').checked;for(const id of ['history-from','history-to'])el(id).disabled=liveChartEnabled();if(!running&&!owned&&lastRunner?.indicator_selection_revision!=='independent-indicators-v1'){el('toggle').disabled=true;el('start-selected').disabled=true;}const zonesReady=lastRunner?.zone_target_revision==='strong-5m-zone-target-v1',structureReady=lastRunner?.market_structure_revision==='confirmed-host-structure-v1';
      el('zone-target-enabled').disabled=!zonesReady;el('market-structure-enabled').disabled=!structureReady;
      const zone=lastRunner?.position?.zone_target_assessment;
      el('zone-target-state').textContent=!zonesReady?'Optional zone exits OFF · backend update pending; current runner unchanged':(lastRunner?.config?.zone_target_enabled?'ON in active config':'OFF in active config')+' · strong 5m opposing zone; touch assessed at completed 5m close, continue only beyond outer boundary. '+(zone?zone.state+' · '+(zone.reason||'no zone exit request'):'No owned target assessment')+(lastRunner?.position?.zone_target_error?' · Unavailable: '+lastRunner.position.zone_target_error:'');
      const structure=lastRunner?.latest_entry_assessment?.signal?.market_structure;
      el('market-structure-state').textContent=!structureReady?'Optional structure entry filter OFF · backend update pending; current runner unchanged':(lastRunner?.config?.market_structure_enabled?'ON in active config':'OFF in active config')+' · Actual '+(lastRunner?.config?.timeframe||el('timeframe').value)+' completed host OHLC · strict 2-left/2-right swings, confirmed after 2 later closes · '+(structure?structure.state+' · '+structure.reason:'Long: HH + HL; short: LH + LL. Insufficient structure blocks entries when enabled.');
      if((el('zone-target-enabled').checked&&!zonesReady)||(el('market-structure-enabled').checked&&!structureReady)){el('toggle').disabled=true;el('start-selected').disabled=true;}
      syncCalibratedControls();indicatorControls();syncThirdEmaControls();paintChartControls();el('manual-brick').disabled=el('brick-mode').value!=='Manual';for(const id of ['adx-threshold','adx-length','adx-smoothing'])el(id).disabled=!(el('use-adx').checked||chartChoice('use-adx-indicator')||el('adx-exit-enabled').checked||chartChoice('adx-exit-enabled-indicator'));lockActiveRunnerForm();}
    const resetSettingsButton=document.createElement('button');resetSettingsButton.id='renko-reset-settings';resetSettingsButton.type='button';resetSettingsButton.disabled=true;resetSettingsButton.className='button secondary';resetSettingsButton.textContent='Reset to strategy defaults';configurationTools.insertBefore(resetSettingsButton,el('save-settings'));
    resetSettingsButton.onclick=async()=>{
      if(lastRunner?.running||lastRunner?.position||lastRunner?.pending){el('config-state').textContent='Stop the selected runner and resolve its exposure before resetting settings.';return;}
      clearTimeout(prefsTimer);sessionBreaks?.reset();const reset={...factoryFields,symbol:el('symbol').value,timeframe:el('timeframe').value,market:el('market').value};
      for(const [id,value] of Object.entries(reset)){if(!el(id))continue;if(el(id).type==='checkbox')el(id).checked=value===true;else el(id).value=value;}
      try{localStorage.setItem(chartStyleKey(),'synthetic');localStorage.setItem(pointerPreferencesKey,JSON.stringify({one:false,five:false}));}catch{}oneMinuteLabelToggle.checked=false;fiveMinuteLabelToggle.checked=false;syncChartDisplay();
      selectedConfigurationId=null;el('override-direction').value='';el('config-name').value='';deleteConfigButton.disabled=true;controls();indicatorControls();
      try{await persistDraft();el('config-state').textContent='Strategy defaults saved · Renko + Supertrend + EMA 10 · optional filters off · runner stopped';load();}catch(e){el('config-state').textContent='Defaults shown; save failed: '+e.message;}
    };
    el('strategy-basis').addEventListener('change',()=>{if(el('strategy-basis').value==='RENKO')el('intrabar-entries').checked=false;controls();});
    let savedDraft=null,confirmedSavedAt=null;
    const libraryStorage=(isEngine?'sector-pulse:renko-engine-configurations-v1:':'sector-pulse:renko-configurations-v1:')+brokerName+(isMotilal?':'+dhanAccount:''),initialConfigurationSignature=JSON.stringify(values());
    let namedLibrary=configurationLibrary(null),libraryError=null,configOptions=[],configOptionIndex=-1,selectedConfigurationId=null;
    try{const original=localStorage.getItem(libraryStorage);namedLibrary=configurationLibrary(JSON.parse(original||'null'));if(original&&original!==JSON.stringify(namedLibrary)){if(!localStorage.getItem(libraryStorage+':before-instrument-consolidation'))localStorage.setItem(libraryStorage+':before-instrument-consolidation',original);localStorage.setItem(libraryStorage,JSON.stringify(namedLibrary));}}catch(e){libraryError=e.message;namedConfigNote.textContent=libraryError;}
    function writeLibrary(next){if(libraryError)throw Error(libraryError);localStorage.setItem(libraryStorage,JSON.stringify(next));namedLibrary=next;}
    function closeConfigOptions(){el('config-options').hidden=true;el('config-name').setAttribute('aria-expanded','false');el('config-name').removeAttribute('aria-activedescendant');configOptionIndex=-1;}
    function paintConfigOptions(show=true,all=false){
      const filter=all?'':el('config-name').value.trim().toLowerCase();configOptions=namedLibrary.records.filter(r=>(r.name+' '+r.symbol).toLowerCase().includes(filter)).sort((a,b)=>a.name.localeCompare(b.name)||a.symbol.localeCompare(b.symbol));
      el('config-options').replaceChildren();configOptionIndex=-1;
      for(const [index,r]of configOptions.entries()){
        const option=document.createElement('button');option.type='button';option.id='renko-config-option-'+index;option.setAttribute('role','option');option.setAttribute('aria-selected','false');option.textContent=r.name+' · '+r.symbol;option.addEventListener('click',()=>loadNamedConfiguration(r,true));el('config-options').append(option);
      }
      if(!configOptions.length){const empty=document.createElement('span');empty.textContent=filter?'No saved name matches. Save settings to create it.':'No named configurations saved yet.';el('config-options').append(empty);}
      el('config-options').hidden=!show;el('config-name').setAttribute('aria-expanded',String(show));
    }
    function applyNamedFields(record){
      const fields=restoredConfigurationFields(values(),record);if(!record.settings['strategy-basis'])fields['strategy-basis']='LEGACY';
      if(fields.symbol&&!Array.from(el('symbol').options).some(o=>o.value===fields.symbol))el('symbol').add(new Option(fields.symbol,fields.symbol));
      for(const id of allIds)if(Object.hasOwn(fields,id)){if(el(id).type==='checkbox')el(id).checked=fields[id]===true;else el(id).value=fields[id];}
      if(record.settings['rsi-sma-period']!=null)el('rsi-sma-period').value=record.settings['rsi-sma-period'];
      if(record.settings['show-one-minute-label']!=null)oneMinuteLabelToggle.checked=record.settings['show-one-minute-label']===true;
      if(record.settings['show-five-minute-label']!=null)fiveMinuteLabelToggle.checked=record.settings['show-five-minute-label']===true;
      selectedConfigurationId=record.id;deleteConfigButton.disabled=false;el('config-name').value=record.name;namedConfigNote.textContent='Loaded '+record.name+' · '+record.symbol+' · execution mode retained · applies on next Start only.';
    }
    function loadNamedConfiguration(record,manual=false){
      clearTimeout(prefsTimer);applyNamedFields(record);closeConfigOptions();
      if(manual)try{writeLibrary({...namedLibrary,preferred:{...namedLibrary.preferred,[record.symbol]:record.id}});}catch(e){namedConfigNote.textContent+=' · preference could not be saved: '+e.message;}
      invalidate();clearAnalysis();connectStream();rebuildSma();paintSupertrendPointers();load();
    }
    function matchInstrumentConfiguration(){
      const record=chooseConfiguration(namedLibrary,el('symbol').value);
      if(record){applyNamedFields(record);return true;}
      selectedConfigurationId=null;deleteConfigButton.disabled=true;el('config-name').value='';namedConfigNote.textContent='No saved configuration for this exact instrument · current settings retained.';return false;
    }
    function preservePreviousDraft(fields,savedAt,source){
      if(libraryError||!fields?.symbol)return;
      if((namedLibrary.deleted_symbols||[]).includes(fields.symbol))return;
      const existing=chooseConfiguration(namedLibrary,fields.symbol);
      if(existing)return;
      try{writeLibrary(storeConfiguration(namedLibrary,existing?.name||fields.symbol,fields,Number(savedAt)||0));}catch(e){namedConfigNote.textContent='Previous draft remains intact; configuration migration failed: '+e.message;}
    }
    el('config-name').addEventListener('input',()=>{selectedConfigurationId=null;deleteConfigButton.disabled=true;paintConfigOptions();});
    const deleteConfirmation=document.createElement('div');deleteConfirmation.hidden=true;deleteConfirmation.setAttribute('role','alertdialog');deleteConfirmation.setAttribute('aria-label','Confirm saved configuration deletion');deleteConfirmation.style.cssText='flex-basis:100%;padding:10px;border:1px solid #dfa861;border-radius:4px';
    const deleteConfirmationText=document.createElement('p'),confirmDeleteButton=document.createElement('button'),cancelDeleteButton=document.createElement('button');confirmDeleteButton.type=cancelDeleteButton.type='button';confirmDeleteButton.className=cancelDeleteButton.className='button';confirmDeleteButton.textContent='Confirm deletion';cancelDeleteButton.textContent='Cancel deletion';deleteConfirmation.append(deleteConfirmationText,confirmDeleteButton,cancelDeleteButton);configurationTools.append(deleteConfirmation);let pendingConfigurationDelete=null;
    cancelDeleteButton.onclick=()=>{pendingConfigurationDelete=null;deleteConfirmation.hidden=true;};
    deleteConfigButton.onclick=()=>{
      const record=namedLibrary.records.find(r=>r.id===selectedConfigurationId);if(!record)return;
      pendingConfigurationDelete=record.id;deleteConfirmationText.textContent='Delete '+record.name+' for '+record.symbol+'? Displayed settings and the runner will stay unchanged.';deleteConfirmation.hidden=false;
    };
    confirmDeleteButton.onclick=()=>{
      const record=namedLibrary.records.find(r=>r.id===pendingConfigurationDelete);if(!record)return;
      try{writeLibrary(deleteConfiguration(namedLibrary,record.id));selectedConfigurationId=null;deleteConfigButton.disabled=true;el('config-name').value='';closeConfigOptions();namedConfigNote.textContent='Deleted '+record.name+' · displayed settings and active runner unchanged.';pendingConfigurationDelete=null;deleteConfirmation.hidden=true;}catch(e){namedConfigNote.textContent='Configuration deletion failed: '+e.message;}
    };
    el('config-name').addEventListener('focus',()=>paintConfigOptions(true,true));
    el('config-dropdown').onclick=()=>el('config-options').hidden?paintConfigOptions(true,true):closeConfigOptions();
    el('config-name').addEventListener('keydown',e=>{
      if(e.key==='Escape'){closeConfigOptions();return;}
      if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();if(el('config-options').hidden)paintConfigOptions(true,true);if(!configOptions.length)return;configOptionIndex=(configOptionIndex+(e.key==='ArrowDown'?1:-1)+configOptions.length)%configOptions.length;for(const [i,o]of Array.from(el('config-options').children).entries())o.setAttribute('aria-selected',String(i===configOptionIndex));el('config-name').setAttribute('aria-activedescendant','renko-config-option-'+configOptionIndex);}
      if(e.key==='Enter'&&!el('config-options').hidden){const record=configOptions[configOptionIndex]||configOptions.find(r=>r.name===el('config-name').value.trim()&&r.symbol===el('symbol').value);if(record){e.preventDefault();loadNamedConfiguration(record,true);}}
    });
    document.addEventListener('pointerdown',e=>{if(!el('config-name').closest('.renko-config-combo').contains(e.target))closeConfigOptions();});
    const comboStyle=document.createElement('style');comboStyle.textContent='.renko-config-combo{position:relative;display:inline-flex;min-width:260px}.renko-config-name input{max-width:none;width:240px}.renko-config-combo>button{padding:5px 9px}#renko-config-options{position:absolute;top:100%;left:0;z-index:30;min-width:100%;max-width:min(520px,80vw);max-height:240px;overflow:auto;background:#172132;border:1px solid #719fe8;border-radius:5px;box-shadow:0 4px 16px #0008}#renko-config-options[hidden]{display:none}#renko-config-options>button{display:block;width:100%;padding:9px 12px;text-align:left;background:transparent;color:#d9e4ef;border:0;white-space:normal;font:12px Arial}#renko-config-options>button:hover,#renko-config-options>[aria-selected="true"]{background:#334b69}#renko-config-options>span{display:block;padding:12px;color:#9dafc3}#renko-named-config-note{flex-basis:100%;font-size:11px;color:#9dafc3}';document.head.append(comboStyle);
    // Preserve old v1/v2/v3 per-instance drafts without overwriting named saves.
    try{for(let i=0;!isEngine&&i<localStorage.length;i++){const key=localStorage.key(i);if(!key?.startsWith('sector-pulse:renko-supertrend-settings-v'))continue;if(isMotilal?!key.startsWith('sector-pulse:renko-supertrend-settings-v3:MOTILAL_OSWAL:'+dhanAccount):key.includes(':MOTILAL_OSWAL:')||key.includes(':DELTA_INDIA')!==isDelta)continue;const prior=JSON.parse(localStorage.getItem(key));preservePreviousDraft(prior,prior?.__saved_at,key.split(':').at(-1));}}catch(e){namedConfigNote.textContent='Legacy draft scan incomplete: '+e.message;}

    function configurationState(){const saved=savedDraft===JSON.stringify(values());el('config-state').textContent=(saved?'Draft saved '+stamp(confirmedSavedAt)+' IST':'Draft edited · save pending or unconfirmed')+' · Selected instance '+instanceId+' · '+(lastRunner?.running?'Active '+(lastRunner.config?.mode||'')+' '+(lastRunner.config?.underlying||'')+' · Runner active with its Start settings; edits apply on next Start.':lastRunner?'Runner '+lastRunner.status+' · Start applies visible settings.':'Runner state loading.');}
    async function persistDraft(){if(el('anti-chop-enabled')?.checked)requireRsiHtfSupport(payload(),lastRunner);if(values()['zone-entry-enabled']&&values()['calibrated-enabled'])requireRsiHtfSupport(payload(),lastRunner);if(!isEngine&&lastRunner?.entry_atr_policy_revision!=='all-broker-flexible-atr-v1')throw Error('Flexible ATR settings are ready; broker dashboard update is required before saving.');if(!isEngine&&lastRunner?.ema_third_revision!=='third-ema-entry-v1')throw Error('Third EMA settings require dashboard activation before saving.');const draft=values(),signature=JSON.stringify(draft);const result=await request('settings',{settings:draft});savedDraft=signature;confirmedSavedAt=result.saved_at;try{localStorage.setItem(storage,JSON.stringify({...draft,__saved_at:result.saved_at}));}catch{}configurationState();return result;}
    el('save-settings').onclick=async()=>{clearTimeout(prefsTimer);el('save-settings').disabled=true;try{const result=await persistDraft();const name=el('config-name').value.trim()||el('symbol').value;if(name){writeLibrary(storeConfiguration(namedLibrary,name,{...values(),'rsi-sma-period':el('rsi-sma-period').value,'show-one-minute-label':oneMinuteLabelToggle.checked,'show-five-minute-label':fiveMinuteLabelToggle.checked},result.saved_at));selectedConfigurationId=JSON.stringify([el('symbol').value]);deleteConfigButton.disabled=false;namedConfigNote.textContent='Saved '+name+' · '+el('symbol').value+' · available in this browser.';closeConfigOptions();}else namedConfigNote.textContent='Draft saved. Enter a name to add it to saved configurations.';}catch(e){el('config-state').textContent='Settings save failed: '+e.message+' · active runner unchanged';}finally{el('save-settings').disabled=false;}};
    el('export-settings').onclick=()=>{const fields=allIds.map(id=>({id,label:(el(id).closest('label')?.firstChild?.textContent||id).split('\n')[0].replace(/\s+/g,' ').trim().slice(0,180),value:values()[id]}));fields.push({id:'rsi-sma-period',label:'Chart-only SMA of RSI period',value:el('rsi-sma-period').value});const out=configurationText({broker:isDelta?'DELTA_INDIA':'FYERS',instance:instanceId,fields,requested:payload(),active:lastRunner?.config,revision:lastRunner?.runtime_revision,savedAt:savedDraft===JSON.stringify(values())?confirmedSavedAt:null});const name=el('config-name').value.trim().replace(/[^A-Za-z0-9_-]/g,'_');const url=URL.createObjectURL(new Blob([out.text],{type:'text/plain;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=name?name+'-'+out.filename:out.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    function invalidate(){version++;controls();prefsSavedAt=Date.now()/1000;try{localStorage.setItem(storage,JSON.stringify({...values(),__saved_at:prefsSavedAt}));}catch{}configurationState();clearTimeout(prefsTimer);prefsTimer=setTimeout(()=>persistDraft().catch(e=>{el('config-state').textContent='Preferences could not be saved: '+e.message;}),250);}

    function clearAnalysis(){sessionBreaks?.clear();runnerStartPointer?.clear();inspectionPinnedTime=null;inspectionCardKey="";if(inspectionCard)inspectionCard.hidden=true;inspectedCandleTime=null;latestReadoutCandle=null;studyHoverTime=null;chartSettingsError=null;clearTimeout(historyRetry);historyFailures=0;historyFailedAt=0;historyKey="";historyRevision="";historyRows=[];for(const pane of studyPanes.values()){pane.points.clear();pane.latest=null;pane.series.setData([]);pane.view.clearCrosshairPosition();pane.value.textContent='Warming up';pane.value.dataset.hoverTime='';}currentPlotted=[];el('history-health').textContent="";supertrendPointerPoints=[];fiveMinutePointerPoints=[];paintSupertrendPointers();zoneRows=[];zoneError="Five-minute zones loading selected instrument…";paintZones([],null,"Zones loading selected instrument / timeframe…");chartAnalysisReady=false;lastLoadAt=0;allEvents=[];el('candle-readout').textContent='';el('history-range').textContent='Loading selected historical range…';el('signal-range').textContent='';el('latest-signal').disabled=true;el('older-events').disabled=true;el('newer-events').disabled=true;el('events-page').textContent='';el('provisional-status').textContent='Waiting for current analysis…';for(const id of ['direction','event','box','st'])el(id).textContent='—';el('anchor').textContent='';el('events').replaceChildren();if(chart){candles.setData([]);volumeSeries?.setData([]);line.setData([]);liveSupertrendLine?.setData([]);fiveMinuteLine?.setData([]);syntheticLine.setData([]);ema10Line.setData([]);ema30Line.setData([]);ema100Line?.setData([]);rsiLine?.setData([]);rsiSmaLine?.setData([]);confirmedRsiPoints=[];formingRsiPoint=null;rsiPoints.clear();rsiSmaPoints.clear();rsiConfirmed={};el('rsi-sma-readout').textContent=`SMA ${smaPeriod()} · loading…`;el('rsi-readout').textContent='Loading RSI…';}el('status').textContent='Loading the selected Renko calculation…';}
    function signalNavigation(c,plotted){const b=document.createElement('button');b.type='button';b.className='button';b.textContent='Show '+c.lifecycle_event;b.onclick=()=>{const i=plotted.findIndex(r=>r.time===c.timestamp);if(i>=0)chart.timeScale().setVisibleLogicalRange({from:Math.max(0,i-20),to:Math.min(plotted.length+2,i+35)});};return b;}
    function eventTable(){const begin=eventPage*20;table(el('events'),['Candle opens · IST','Event confirms · IST','Signal','Host close','Brick size','Supertrend','Exit/entry reason','Chart'],allEvents.slice(begin,begin+20).map(c=>[stamp(c.timestamp),stamp(c.lifecycle_event_at??c.timestamp),c.lifecycle_event,price(c.close),(chartChoice('supertrend-enabled-indicator')||chartChoice('supertrend-exit-enabled-indicator'))?price(c.box):'—',(chartChoice('supertrend-enabled-indicator')||chartChoice('supertrend-exit-enabled-indicator'))?price(c.supertrend):'—',c.lifecycle_reason,signalNavigation(c,currentPlotted)]));el('older-events').disabled=begin+20>=allEvents.length;el('newer-events').disabled=eventPage===0;el('events-page').textContent=` ${Math.min(begin+1,allEvents.length)}–${Math.min(begin+20,allEvents.length)} of ${allEvents.length} events`; }
    el('older-events').onclick=()=>{eventPage++;eventTable();};el('newer-events').onclick=()=>{eventPage=Math.max(0,eventPage-1);eventTable();};
    async function load(){restoreChartStyle();paintChartBasis();if((!isBatchChartView&&batchChartFrames.size>0)||busy||!el('symbol').value)return;clearTimeout(historyRetry);connectStream();busy=true;const seq=version;
      try{if(!isBatchChartView&&boundSelectionSymbol!==el('symbol').value)await bindDisplayedInstrument();if(seq!==version)return;const query={commodity_holding:!isDelta&&el('symbol').value.startsWith('MCX:')?el('commodity-holding').value:'INTRADAY',...(isDelta?{execution_route:el('delta-execution-route').value,session_deadline:el('session-deadline').value,carry_policy:el('carry-policy').value}:{}),symbol:el('symbol').value,timeframe:chartControl('timeframe').value,...boundChartContext().settings,...(isEngine?root.RenkoEngine.executionSettings(values()):{}),history_preset:el('history-preset').value,history_from:el('history-from').value,history_to:el('history-to').value,...boundChartContext().history};const queryKey=JSON.stringify(query);const incremental=queryKey===historyKey&&historyRevision;const params={...query,...(incremental?{revision:historyRevision,since:historyRows.at(-2)?.timestamp||0}:{})};const context=boundChartContext();const d=mergeChartRows(await request('chart?'+new URLSearchParams(params)),historyRows);if(seq!==version)return;if(!isEngine&&context.settings.ema_third_enabled&&(d.settings?.ema_third_enabled!==true||!Number.isFinite(Number(d.settings?.ema_third_length))))throw Error('Third EMA calculations await dashboard activation.');chartParity=runnerChartAlignment(context,lastRunner,d);confirmedRevision=d.confirmed_source?.revision||confirmedRevision;paintChartBasis();chartSettingsError=null;void connectStream();historyFailures=0;historyFailedAt=0;el('history-health').textContent=d.history?.history_error?'Completed history refresh delayed · cached candles retained':'';lastLoadAt=Date.now();historyRows=d.rows;historyKey=queryKey;historyRevision=d.history.analysis_revision;el('history-range').textContent=`Requested ${d.history.requested_from} → ${d.history.requested_to} · Available ${stamp(d.history.display_oldest)} → ${stamp(d.history.display_latest)} IST · ${d.history.display_count} displayed candles · ${d.history.initialization_bars} preceding warmup bars. ${d.history.source}. ${d.history.history_error?'History refresh delayed · cached completed candles retained. ':''}${d.history.anchor_policy} ${d.history.intrabar_history}`;if(!isDelta&&d.session_policy&&el('commodity-holding').value!=='CARRY_FORWARD'&&!(cashEquity()&&el('cash-product').value==='CNC')){el('market-policy-note').dataset.symbol=el('symbol').value;el('market-policy-note').dataset.policy=d.session_policy.session_exchange+' · strategy cutoff '+d.session_policy.session_deadline+' IST · verified regular session '+d.session_policy.master_regular_session+'.';el('market-policy-note').textContent=el('market-policy-note').dataset.policy;}const available=chartAnalysisAvailable(d);chartAnalysisReady=available;const analysisRows=available?d.rows:[];const last=d.latest;el('rsi-htf-chart').textContent='Chart settings · '+rsiHtfSummary(last?.mtf_rsi);if(available&&!last)throw Error('No completed host candles.');
        if(available){
        el('direction').textContent=last.direction;el('event').textContent=last.lifecycle_event||entryDecisionText(last,lastRunner,d.symbol);el('box').textContent=price(last.box);el('st').textContent=price(last.supertrend);
        el('status').textContent=`${d.symbol} · ${d.timeframe} · Completed ${stamp(last.timestamp)} · ${entryDecisionText(last,lastRunner,d.symbol)}`+(el('ema-fast-enabled').checked?' · EMA '+chartControl('ema-fast-length').value+' '+price(last.ema10):'')+(el('ema-slow-enabled').checked?' · EMA '+chartControl('ema-slow-length').value+' '+price(last.ema30):'')+(el('ema-third-enabled').checked&&Number.isFinite(last.ema100)?' · EMA '+chartControl('ema-third-length').value+' '+price(last.ema100):'')+(el('ema-widening-enabled').checked?' · gap '+price(last.ema_gap)+' · '+d.settings.widening_window+' candles':'')+(el('use-adx').checked?' · ADX '+fmt(last.adx):'');
        const cutoffNote=isEngine?'Pine IST entry '+el('engine-session').value+'; square-off '+el('engine-flat-hour').value+':'+el('engine-flat-minute').value:isDelta&&d.settings.carry_policy==='CONTINUOUS'?'Continuous crypto · no daily square-off or entry cutoff; held contract expiry applies':d.settings.session_segment+' square-off / entry cutoff '+d.squareoff_time;const provisional=d.provisional_candidate;el('provisional-status').textContent=(d.intrabar_entries?(provisional?`Provisional live candidate: ${provisional.entry_direction||provisional.entry_diagnostic} · event ${stamp(provisional.market_event_at)} · EMA10 ${price(provisional.ema10)} / EMA30 ${price(provisional.ema30)} · can disappear; not a fill.`:'Intrabar entry waiting: '+(d.provisional_error||'fresh market update unavailable'))+' · '+cutoffNote+'.':(isEngine?'Completed-candle Pine entries and opposite-signal exits · ':'Completed-candle entries and EMA exits · ')+cutoffNote+'.')+' · '+(d.option_route?.message||'Execution route not verified');
        el('anchor').textContent=`Initialization: ${stamp(d.initialization_anchor)} · ${d.host_bar_count} completed host bars. Historical signal simulation, not broker fills. State: ${last.projected_position?.direction||'FLAT'}${last.projected_position?' since '+stamp(last.projected_position.entry_timestamp):''}. Signals depend on this history anchor; Actual intrabar candidates require fresh ticks; historical OHLC cannot reconstruct them.`;
        }else{
          for(const id of ['direction','event','box','st'])el(id).textContent='Unavailable';
          el('status').textContent=chartParity?.blocked?chartParity.reason:d.data_quality.message+' Invalid bars: '+d.data_quality.invalid_count+'. '+(d.data_quality.invalid_candles||[]).slice(0,5).map(g=>stamp(g.timestamp)+' IST: '+g.reason).join(' · ');
          el('anchor').textContent=chartParity?.blocked?chartParity.reason:'Historical calculations withheld across invalid OHLC; valid broker candles remain visible.';
          el('provisional-status').textContent='Provisional chart indicators unavailable until historical validation succeeds.';
        }
        const provisional=available&&!chartParity?.blocked?d.provisional_candidate:null;
        if(!chart){chart=root.LightweightCharts.createChart(el('chart'),{width:el('chart').clientWidth,height:el('chart').clientHeight,layout:{background:{color:'#131722'},textColor:'#d1d4dc',fontFamily:'Arial',fontSize:12},grid:{vertLines:{color:'#242832'},horzLines:{color:'#242832'}},crosshair:{mode:0,vertLine:{color:'#758696',labelBackgroundColor:'#363a45'},horzLine:{color:'#758696',labelBackgroundColor:'#363a45'}},rightPriceScale:{minimumWidth:110,borderColor:'#2a2e39',scaleMargins:{top:.12,bottom:.20}},localization:{timeFormatter:stamp,priceFormatter:price},timeScale:{timeVisible:true,tickMarkFormatter:t=>new Date(t*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false})}});renkoChartSeries(chart,'line');renkoChartSeries(chart,'volume');candles=chart.addCandlestickSeries({upColor:'#26a69a',downColor:'#ef5350',borderVisible:false,wickUpColor:'#26a69a',wickDownColor:'#ef5350'});volumeSeries=chart.addHistogramSeries({priceScaleId:'volume',priceFormat:{type:'volume'},priceLineVisible:false,lastValueVisible:false});volumeSeries.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0},visible:false});line=chart.addLineSeries({lineWidth:2,priceLineVisible:false,title:'1-minute Supertrend'});liveSupertrendLine=chart.addLineSeries({color:'#f2c14e',lineWidth:2,lineStyle:2,priceLineVisible:false,title:'Provisional Supertrend · no entry authority'});fiveMinuteLine=chart.addLineSeries({lineWidth:3,lineStyle:2,priceLineVisible:false,title:'5-minute Supertrend'});ema10Line=chart.addLineSeries({color:'#4bb9ff',lineWidth:2,priceLineVisible:false,title:'EMA 10'});ema30Line=chart.addLineSeries({color:'#bc8cff',lineWidth:2,priceLineVisible:false,title:'EMA 30'});ema100Line=chart.addLineSeries({color:'#e7b15a',lineWidth:2,priceLineVisible:false,title:'EMA 100'});syntheticLine=chart.addLineSeries({color:'#e0b65f',lineWidth:1,priceLineVisible:false,title:'Synthetic close'});chart.subscribeCrosshairMove(coalescedHover(param=>{if(!acceptInspectionHover())return;syncRsiHover(param,false);const c=param.seriesData?.get(candles);if(c){readCandle(c,true);el('candle-readout').textContent+=(chartChoice('ema-fast-enabled-indicator')?' · EMA '+chartControl('ema-fast-length').value+' '+price(param.seriesData.get(ema10Line)?.value):'')+(chartChoice('ema-slow-enabled-indicator')?' · EMA '+chartControl('ema-slow-length').value+' '+price(param.seriesData.get(ema30Line)?.value):'')+(chartChoice('ema-third-enabled-indicator')?' · EMA '+chartControl('ema-third-length').value+' '+price(param.seriesData.get(ema100Line)?.value):'')+(chartChoice('supertrend-enabled-indicator')?' · '+chartControl('timeframe').value+' Supertrend '+price(param.seriesData.get(line)?.value):'')+(chartChoice('higher-timeframe-enabled-indicator')?' · '+chartControl('supertrend-timeframe').value+' Supertrend '+price(param.seriesData.get(fiveMinuteLine)?.value):'');const t=typeof param.time==='number'?param.time:null;if(t!==null){const rv=rsiPoints.get(t),sv=rsiSmaPoints.get(t);if(chartChoice('rsi-slope-enabled-indicator')||chartChoice('rsi-level-enabled-indicator')||chartChoice('rsi-exit-enabled-indicator')||chartChoice('rsi-sma-enabled'))el('candle-readout').textContent+=' · RSI '+chartControl('rsi-length').value+' '+(Number.isFinite(rv)?fmt(rv):'warming up')+(chartChoice('rsi-sma-enabled')?' · RSI SMA '+smaPeriod()+' '+(Number.isFinite(sv)?fmt(sv):'warming up'):'');}}},requestAnimationFrame));new ResizeObserver(()=>{const width=el('chart').clientWidth,height=el('chart').clientHeight;if(!width||!height)return;const range=chart.timeScale().getVisibleLogicalRange(),latest=!range||range.to>=plottedCount-3;chart.applyOptions({width,height});if(range){chart.timeScale().setVisibleLogicalRange(range);}else if(plottedCount&&inspectedCandleTime===null)el('readable-chart').onclick();}).observe(el('chart'));}
        if(isDelta)for(const series of [candles,line,fiveMinuteLine,ema10Line,ema30Line,ema100Line,syntheticLine])series.applyOptions({priceFormat:{type:'custom',minMove:.01,formatter:price}});
        if(!rsiChart){
          rsiChart=root.LightweightCharts.createChart(el('rsi-chart'),{width:el('rsi-chart').clientWidth,height:el('rsi-chart').clientHeight,layout:{background:{color:'transparent'},textColor:'#d1d4dc',fontFamily:'Arial',fontSize:11},grid:{vertLines:{color:'#ffffff0a'},horzLines:{color:'#ffffff0a'}},rightPriceScale:{minimumWidth:110,borderColor:'#2a2e39',scaleMargins:{top:0,bottom:0}},timeScale:{visible:false},localization:{timeFormatter:stamp}});
          renkoChartSeries(rsiChart,'line');rsiLine=rsiChart.addLineSeries({color:'#bc8cff',lineWidth:2,priceLineVisible:false,title:'RSI14',autoscaleInfoProvider:()=>({priceRange:{minValue:0,maxValue:100}})});
          rsiSmaLine=rsiChart.addLineSeries({color:'#ffd166',lineWidth:2,priceLineVisible:false,title:'RSI SMA 14',autoscaleInfoProvider:()=>({priceRange:{minValue:0,maxValue:100}})});
          for(const level of [0,40,60,80,100])rsiLine.createPriceLine({price:level,color:'#697386',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:''});
          const sync=(source,target)=>range=>{if(range&&!rsiSync){rsiSync=true;target.timeScale().setVisibleLogicalRange(range);rsiSync=false;}};
          chart.timeScale().subscribeVisibleLogicalRangeChange(sync(chart,rsiChart));chart.timeScale().subscribeVisibleLogicalRangeChange(positionAssessment);rsiChart.timeScale().subscribeVisibleLogicalRangeChange(sync(rsiChart,chart));
          rsiChart.subscribeCrosshairMove(p=>syncRsiHover(p,true));
          new ResizeObserver(()=>{if(el('rsi-chart').clientWidth&&el('rsi-chart').clientHeight)rsiChart.applyOptions({width:el('rsi-chart').clientWidth,height:el('rsi-chart').clientHeight});}).observe(el('rsi-chart'));
        }
        const previousRange=chart.timeScale().getVisibleLogicalRange(),previousVisible=chart.timeScale().getVisibleRange();
        const logicalAt=t=>{const x=chart.timeScale().timeToCoordinate(t);return Number.isFinite(x)?chart.timeScale().coordinateToLogical(x):null;};
        const previousLastLogical=currentPlotted.length?logicalAt(currentPlotted.at(-1).time):null,previousLeftLogical=previousVisible?logicalAt(previousVisible.from):null;
        const view=el('chart-view').value,plotted=chartCandles(d,view);chart.uniformRenkoRows=view==='synthetic'?plotted:null;rsiChart.uniformRenkoRows=chart.uniformRenkoRows;paintBrickPreview(d.forming?.at(-1));
        const calculatedRsi=rsiHistory(analysisRows,Number(chartControl('rsi-length').value));confirmedRsiPoints=calculatedRsi.points;formingRsiPoint=null;rsiPoints.clear();for(const p of calculatedRsi.points)rsiPoints.set(p.time,p.value);rsiConfirmed=calculatedRsi.state;rsiLine.setData(calculatedRsi.points);paintRsi(calculatedRsi.points.at(-1));
        const formingRsi=d.forming?.at(-1);if(available&&formingRsi&&liveChartEnabled()&&formingRsi.timestamp>rsiConfirmed.time)paintRsi(rsiStep(rsiConfirmed,formingRsi.close,formingRsi.timestamp,Number(chartControl('rsi-length').value)).point,true);
        if(!available){el('rsi-readout').textContent=chartParity?.blocked?'RSI withheld · runner agreement unconfirmed':'RSI unavailable · invalid historical OHLC';el('rsi-sma-readout').textContent=chartParity?.blocked?'RSI SMA withheld · runner agreement unconfirmed':'RSI SMA unavailable · invalid historical OHLC';rsiSmaLine.setData([]);}
        const key=JSON.stringify({...query,chart_view:el('chart-view').value}),same=key===lastKey;lastKey=key;
        const viewport=refreshChartViewport(currentPlotted,plotted,previousRange,same),followLatest=viewport.follow;
        candles.setData(plotted);volumeSeries.setData(view==='synthetic'&&!available?[]:volumePoints(d,view));readCandle(plotted.at(-1));el('chart-description').textContent=view==='host'?'Actual '+brokerName+' volume in lower chart band (missing bars mean unavailable; forming volume is a broker snapshot) · Real '+brokerName+' open/high/low/close · candle opening time in IST · green/red calculated Supertrend · blue EMA 10 · purple EMA 30. Forming candles and live indicators are provisional display values. Yellow exits: historical EMA10 simulation; actual runner exits use its active setting (see trade journal).':'Renko uses two-box reversals. Active price-confirmed mode updates full bricks and Supertrend from ordered broker prices; only unfinished remainder is provisional. The selected timeframe supplies Auto sizing and optional host filters. Historical OHLC initializes indicators; it does not establish an observed intrabar path.';
        const plottedAnalysis=boundChartContext().basis!=='draft'?analysisRows:provisional&&view==='host'?[...analysisRows,provisional]:analysisRows;
        liveSupertrendLine?.setData([]);ema10Line.setData(plottedAnalysis.map(c=>({time:c.timestamp,value:c.ema10})));ema30Line.setData(plottedAnalysis.map(c=>({time:c.timestamp,value:c.ema30})));ema100Line.setData(plottedAnalysis.filter(c=>Number.isFinite(c.ema100)).map(c=>({time:c.timestamp,value:c.ema100})));syntheticLine.setData(view==='synthetic'?plotted.map(c=>({time:c.time,value:c.close})):[]);syntheticLine.applyOptions({title:'Renko close'});
        line.applyOptions({title:(query.timeframe==='1 minute'?'1-minute':query.timeframe.replace(' minutes','-minute'))+' Supertrend'});
        fiveMinuteLine.setData([]);
        supertrendPointerPoints=plottedAnalysis.map(c=>({time:c.timestamp,value:c.supertrend,color:c.pine_direction<0?'#2ea043':'#e53935'}));line.setData(supertrendPointerPoints);fiveMinutePointerPoints=[];paintSupertrendPointers();
        const events=chartHistoricalEvents(d,chartParity);latestSignalIndex=events.length?plotted.findIndex(c=>c.time===events.at(-1).timestamp):null;plottedCount=plotted.length;el('latest-signal').disabled=latestSignalIndex===null;const latestEvent=events.at(-1);el('signal-range').textContent=chartParity?.blocked?'Historical signals withheld · runner comparison unconfirmed.':!available?'Historical signals unavailable · invalid broker OHLC.':latestEvent?`Latest historical ${latestEvent.lifecycle_event}: ${stamp(latestEvent.timestamp)} IST. Use Show latest historical event if its marker is outside your visible range.`:'No historical entry/exit events in the loaded history with these settings.';const markers=events.map(c=>({time:c.timestamp,position:(c.lifecycle_event==='BUY'||c.lifecycle_event==='SELL EXIT')?'belowBar':'aboveBar',shape:c.lifecycle_event.endsWith('EXIT')?'circle':c.lifecycle_event==='BUY'?'arrowUp':'arrowDown',color:c.lifecycle_event.endsWith('EXIT')?'#f2c14e':c.lifecycle_event==='BUY'?'#2ea043':'#e53935',text:c.lifecycle_event}));if(d.intrabar_entries&&provisional?.entry_direction&&view==='host'&&!last.projected_position)markers.push({time:provisional.timestamp,position:provisional.entry_direction==='BULLISH'?'belowBar':'aboveBar',shape:'square',color:'#f2c14e',text:'PROVISIONAL '+(provisional.entry_direction==='BULLISH'?'BUY':'SELL')});historicalMarkers=markers;paintMarkers();
        if(!available)el('chart-description').textContent=chartParity?.blocked?'Broker OHLC only · '+chartParity.reason:view==='host'?'Valid broker OHLC only · invalid candles are visible time gaps · derived indicators and historical signals withheld.':'Synthetic Renko unavailable · invalid broker history; choose Host candles to view valid OHLC.';
        if(available&&chartParity?.blocked){
          el('direction').textContent=last.direction+' · chart only';
          el('event').textContent='Runner comparison unconfirmed';
          el('chart-description').textContent+=' Chart-only indicator calculations · runner values differ; historical trade signals withheld. Trading settings and execution are unchanged.';
          el('provisional-status').textContent='Chart indicators available · runner comparison unconfirmed; no provisional trade signals shown.';
        }
        if(previousRange&&same&&Number.isFinite(previousLastLogical)){
          viewport.follow=previousRange.to>=previousLastLogical-2;
          const nextLast=plotted.length?logicalAt(plotted.at(-1).time):null,width=previousRange.to-previousRange.from;
          if(viewport.follow&&Number.isFinite(nextLast)){const to=nextLast+Math.max(1,previousRange.to-previousLastLogical);viewport.range={from:to-width,to};}
          else if(previousVisible&&Number.isFinite(previousLeftLogical)){const left=logicalAt(previousVisible.from);if(Number.isFinite(left)){const from=left+(previousRange.from-previousLeftLogical);viewport.range={from,to:from+width};}else viewport.range=previousRange;}
        }
        if(!viewport.follow&&viewport.range){chart.timeScale().setVisibleLogicalRange(viewport.range);rsiChart?.timeScale().setVisibleLogicalRange(viewport.range);}
        // Fetch selected overlays from their actual broker candle timeframe.
        if(chartChoice('zone-target-enabled-indicator')||chartChoice('higher-timeframe-enabled-indicator'))try{
          if(!zoneRows.length)paintZones([],null,'Five-minute zones loading broker OHLC…');
          const source=query.timeframe==='5 minutes'&&!query.intrabar_entries?d:await request('chart?'+new URLSearchParams({...query,timeframe:'5 minutes',higher_timeframe_enabled:false,intrabar_entries:false,chart_entry_guards:false,confirmed_run_id:'',chart_zone_target_enabled:false}));
          if(seq!==version)return;
          const displaySeconds=Number(query.timeframe.split(' ')[0])*(query.timeframe.includes('hour')?3600:60);
          const cutoff=Math.min(Date.now()/1000,(d.rows.at(-1)?.timestamp||0)+displaySeconds);
          zoneRows=chartChoice('zone-target-enabled-indicator')?fiveMinuteZoneRows(source,query.symbol,cutoff):[];zoneError='';
          if(chartChoice('higher-timeframe-enabled-indicator')){
          const higherFrame=chartControl('supertrend-timeframe').value;
          const higherSource=higherFrame==='5 minutes'?source:higherFrame===query.timeframe&&!query.intrabar_entries?d:await request('chart?'+new URLSearchParams({...query,timeframe:higherFrame,higher_timeframe_enabled:false,intrabar_entries:false,chart_entry_guards:false,confirmed_run_id:'',chart_zone_target_enabled:false}));
          if(seq!==version)return;
          const higherSeconds=Number(higherFrame.split(' ')[0])*(higherFrame.includes('hour')?3600:60);
          const higherRows=assessedHigherRows(chartAnalysisAvailable(higherSource)?higherSource.rows:[],lastRunner,context,higherFrame);
          const overlay=fiveMinuteSupertrendPoints(higherRows,plotted,cutoff,higherSeconds);
          fiveMinuteLine.applyOptions({title:higherFrame+' Supertrend'});
          fiveMinutePointerPoints=view==='host'?overlay:[];fiveMinuteLine.setData(fiveMinutePointerPoints);paintSupertrendPointers();
          el('chart-description').textContent+=' Solid '+query.timeframe+' Supertrend · dashed '+higherFrame+' Supertrend (completed candles only).';
          el('provisional-status').textContent+=' · Higher timeframe check '+(lastRunner?.config?.higher_timeframe_enabled?'ON · '+lastRunner.config.supertrend_timeframe:'OFF in runner');}
        }catch(error){if(seq!==version)return;zoneError=zoneRows.length?'':'Five-minute overlay unavailable: '+error.message;el('history-health').textContent+=' · Five-minute overlay refresh delayed'+(zoneRows.length?' · previous completed snapshot retained':'');}
        paintZones(zoneRows,plotted.at(-1)?.time);currentPlotted=plotted;if(!drawingPriceSurface)drawingPriceSurface=chart.addLineSeries({color:"transparent",lineVisible:false,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,autoscaleInfoProvider:()=>null});drawingPriceSurface.setData(plotted.filter(c=>Number.isFinite(c.close)).slice(-1).map(c=>({time:c.time,value:c.close})));if(!drawingTools)drawingTools=mountChartDrawings({chart,candles:drawingPriceSurface,host:el("chart"),scope:()=>[pageParams.get("renkoBroker")||selectedBroker,pageParams.get("renkoAccount")||pageParams.get("brokerAccount")||dhanAccount,el("symbol").value,el("chart-view").value].join(":"),formatPrice:price,storage:root.localStorage});drawingTools.sync();if(!sessionBreaks)sessionBreaks=mountSessionBreaks({chart,host:el('chart'),toolbar:el('chart').previousElementSibling,storage:root.localStorage,scope:()=>[selectedBroker,dhanAccount,el('symbol').value].join(':')});sessionBreaks.set(plotted,d.session_policy||{});if(!runnerStartPointer)runnerStartPointer=mountRunnerStartPointer({chart,host:el('chart'),before:el('candle-readout')});if(!el('chart-view').closest('.renko-drawing-tools')){const styleLabel=el('chart-view').closest('label');styleLabel.firstChild.textContent='Chart ';styleLabel.style.maxWidth='';el('chart-view').setAttribute('aria-label','Chart type');el('chart-view').closest('label').title='Display only. Renko uses equal-sized completed-close bricks and two-box reversals.';el('chart').previousElementSibling.prepend(styleLabel);}paintPriceStyle();paintSelectedIndicators();paintEntryPrice();paintAssessment();if(viewport.follow){if(viewport.range){chart.timeScale().setVisibleLogicalRange(viewport.range);rsiChart?.timeScale().setVisibleLogicalRange(viewport.range);}else el('readable-chart').onclick();}if(inspectedCandleTime!==null){const inspected=plotted.find(c=>c.time===inspectedCandleTime);if(inspected)chart.setCrosshairPosition(inspected.close,inspected.time,candles);}if(inspectionPinnedTime!==null)renderCandleInspection(inspectionPinnedTime);allEvents=events.slice().reverse();if(!same)eventPage=0;eventPage=Math.min(eventPage,Math.max(0,Math.ceil(allEvents.length/20)-1));eventTable();
      }catch(e){if(seq===version){historyDelay(e);if(historyKey&&chartAnalysisReady)paintRsi(null,false,false);if(!historyKey){chartAnalysisReady=false;el('status').textContent=(isMotilal&&/No completed Renko host candles|history is warming up/i.test(e.message)?'Motilal history warming up: ':'Chart history unavailable: ')+e.message;} }}finally{busy=false;if(seq!==version)load();}}
    el('timeframe').addEventListener('change',()=>{
      const paired={'1 minute':'5 minutes','5 minutes':'15 minutes'}[el('timeframe').value];
      if(paired)el('supertrend-timeframe').value=paired;
      if(isBatchChartView&&root.parent!==root)root.parent.postMessage({type:'sector-pulse:renko-timeframe-selection',symbol:el('symbol').value,timeframe:el('timeframe').value},location.origin);
    },true);
    allIds.forEach(id=>el(id).addEventListener('change',()=>{if(id==='symbol')matchInstrumentConfiguration();if(id==='delta-execution-route'){el('action-error').hidden=true;el('action-error').textContent='';}invalidate();if(id==='fyers-history-enabled'||id==='fyers-history-account-id'||signalIds.includes(id)||historyIds.includes(id)||id==='commodity-holding'||id==='delta-execution-route'||id==='supertrend-timeframe'){clearAnalysis();load();}}));
    el('latest-signal').onclick=()=>{if(chart&&latestSignalIndex!==null)chart.timeScale().setVisibleLogicalRange({from:Math.max(0,latestSignalIndex-20),to:Math.min(plottedCount+2,latestSignalIndex+40)});};
    el('chart-view').addEventListener('change',()=>{try{localStorage.setItem(chartStyleKey(),el('chart-view').value);}catch{}paintPriceStyle();load();});
    async function searchInstruments(){
      clearTimeout(searchTimer);version++;clearAnalysis();const seq=++searchVersion,q=el('search').value.trim(),market=el('market').value;
      searchTimer=setTimeout(async()=>{try{
        const r=await fetch(((isDelta||isNative)?apiBase+'search?q=':'/api/ema-band/underlying-search?q=')+encodeURIComponent(q) +(isDelta?'':'&market='+encodeURIComponent(market)));
        const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'Search failed');if(seq!==searchVersion)return;
        const prior=el('symbol').value,priorLabel=el('symbol').selectedOptions[0]?.textContent;el('symbol').replaceChildren(new Option('Select an underlying',''));
        for(const item of d.matches||[])el('symbol').add(new Option((isMotilal?(item.description||item.underlying):item.underlying)+' · '+item.symbol,item.symbol));
        if(prior&&!Array.from(el('symbol').options).some(o=>o.value===prior)&&!isDelta&&!isNative){const exactResponse=await fetch('/api/ema-band/underlying-search?'+new URLSearchParams({q:prior,market}));const exact=await exactResponse.json();if(seq!==searchVersion)return;if(exactResponse.ok){const item=(exact.matches||[]).find(v=>v.symbol===prior);if(item)el('symbol').add(new Option(item.underlying+' · '+item.symbol,item.symbol));}}
        if(isMotilal&&prior&&!Array.from(el('symbol').options).some(o=>o.value===prior))el('symbol').add(new Option(priorLabel||prior,prior));
        if(isDhan&&prior&&!Array.from(el('symbol').options).some(o=>o.value.toUpperCase()===prior.toUpperCase())){
          const exactResponse=await fetch(apiBase+'search?'+new URLSearchParams({q:prior,market:prior.startsWith('MCX:')?'MCX':market}));
          const exact=await exactResponse.json();if(seq!==searchVersion)return;
          if(exactResponse.ok){const item=(exact.matches||[]).find(v=>v.symbol.toUpperCase()===prior.toUpperCase());if(item)el('symbol').add(new Option(item.underlying+' · '+item.symbol,item.symbol));}
        }
        const dhanAliases={'NSE:NIFTY50-INDEX':'NSE:NIFTY','NSE:NIFTYBANK-INDEX':'NSE:BANKNIFTY','NSE:FINNIFTY-INDEX':'NSE:FINNIFTY','NSE:MIDCPNIFTY-INDEX':'NSE:MIDCPNIFTY','BSE:SENSEX-INDEX':'BSE:SENSEX','BSE:BANKEX-INDEX':'BSE:BANKEX'};
        const mapped=isDhan?(dhanAliases[prior]||prior.replace(/-EQ$/,'')):prior;
        const candidate=isDhan?(Array.from(el('symbol').options).find(o=>o.value.toUpperCase()===mapped.toUpperCase())?.value||mapped):mapped;
        if(Array.from(el('symbol').options).some(o=>o.value===candidate)){
          el('symbol').value=candidate;
          if(candidate!==prior){streamKey='';connectStream();if(active)load();}
        }
        controls();
        el('status').textContent=(d.matches||[]).length+' instruments · '+(d.message||'Select an instrument, then add it to the selection.');
      }catch(e){el('status').textContent=e.message;}},300);
    }
    el('search').addEventListener('input',searchInstruments);el('market').addEventListener('change',()=>{el('symbol').value='';el('search').value='';controls();searchInstruments();});
    // Initial search runs after draft restoration.
    el('cash-product').addEventListener('change',controls);
    function syncChartControl(){for(const id of ['reconcile-close','chart-reconcile-close']){el(id).hidden=!(lastRunner?.external_close_recovery_revision==='dhan-external-close-v1'&&!lastRunner.running&&lastRunner.position);el(id).disabled=toggleBusy||overrideBusy||!runnerStatusFresh;}const toggle=lastRunner?toggleState(lastRunner,toggleBusy||overrideBusy||(!runnerStatusFresh&&!lastRunner.running)):{label:'Loading runner…',disabled:true};for(const id of ['toggle','chart-toggle']){el(id).textContent=toggle.label;el(id).disabled=toggle.disabled||(!lastRunner?.running&&!lastRunner?.position&&!lastRunner?.pending&&lastRunner?.indicator_selection_revision!=='independent-indicators-v1');}const context={symbol:el('symbol').value,timeframe:el('timeframe').value,mode:el('mode').value,broker:selectedBroker},o=overrideState(lastRunner||{},context,el('override-direction').value,toggleBusy||overrideBusy||!runnerStatusFresh);el('override-entry').textContent=overrideAttempt?'Check override result':o.label;el('override-entry').disabled=(isDelta&&(lastRunner?.config?.execution_route||'OPTIONS')!==el('delta-execution-route').value)|| (overrideAttempt?toggleBusy||overrideBusy||!lastRunner:o.disabled);el('override-direction').disabled=toggleBusy||overrideBusy||!!overrideAttempt;el('override-note').textContent=overrideAttempt?'Response uncertain. Check the same request before another entry.':o.reason+(lastRunner?.config?' Active size: '+(lastRunner.config.quantity||lastRunner.config.lots)+' '+(lastRunner.config.execution_route==='CASH_EQUITY'?'shares':isDelta?'contracts':'lots')+'.':'');el('chart-action-error').hidden=el('action-error').hidden;el('chart-action-error').textContent=el('action-error').textContent;syncActiveStartButtons();syncThirdEmaControls();}
    if(isMotilal){
      el('mode').options[1].textContent='Live — real Motilal Oswal orders';
      killResult.hidden=true;adoptionPanel.hidden=true;
      if(executionPanel.querySelector('.label'))executionPanel.querySelector('.label').textContent='MOTILAL OSWAL EXECUTION';
      const source=document.createElement('p');source.className='ticket-warning';source.textContent='Motilal live data and execution. Historical candles use Motilal captures unless the explicit FYERS history switch is ON; the selected source is shown in chart details. Native LIMIT IOC orders; Motilal fees are not estimated by another broker model.';executionPanel.prepend(source);
    }
    if(isDhan){
      el('mode').options[1].textContent='Live — real Dhan orders';killResult.hidden=true;el('retest-enabled').disabled=false;
      if(executionPanel.querySelector('.label'))executionPanel.querySelector('.label').textContent='DHAN EXECUTION';
      el('sideways-enabled').disabled=true;
      el('sideways-enabled').closest('label').title='Dhan retail option charges are estimates; quick-loss filtering uses confirmed-fill net estimates.';
      for(const note of section.querySelectorAll('p'))if(note.textContent.includes('Net P&L deducts'))note.textContent='Dhan net P&L deducts estimated retail option charges from confirmed fills; projected exits use executable bid. Estimates can differ from contract notes.';
    }
    if(isNative){for(const id of ['start-selected','stop-all']){el(id).disabled=true;el(id).hidden=true;el(id).title='Use this account’s individual strategy controls.'}adoptionPanel.hidden=true;}
    const overrideStorage='sector-pulse:override-attempt:'+apiBase+instanceId;
    try{overrideAttempt=JSON.parse(sessionStorage.getItem(overrideStorage)||'null');}catch{}
    el('symbol').addEventListener('change',()=>{syncDisplayedChartSelection();runnerStatusFresh=false;syncChartControl();bindDisplayedInstrument().catch(e=>{el('action-error').textContent=e.message;el('action-error').hidden=false;});});
    el('override-direction').onchange=syncChartControl;
    for(const id of ['symbol','timeframe','mode','delta-execution-route'])el(id).addEventListener('change',syncChartControl);
    el('override-entry').onclick=async()=>{
      if(overrideBusy||toggleBusy||!lastRunner||el('override-entry').disabled)return;
      const c=lastRunner.config;
      if(!overrideAttempt){overrideAttempt={override_revision:'explicit-entry-v1',run_id:lastRunner.run_id,underlying:c.underlying,timeframe:c.timeframe,mode:c.mode,broker:c.broker||'FYERS',...(isDelta?{execution_route:el('delta-execution-route').value}:{}),direction:el('override-direction').value,request_id:crypto.randomUUID()};try{sessionStorage.setItem(overrideStorage,JSON.stringify(overrideAttempt));}catch{}}
      overrideBusy=true;el('action-error').hidden=true;el('action-error').textContent='';syncChartControl();
      try{
        const response=await fetch(apiBase+'override-entry?instance='+encodeURIComponent(instanceId),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(overrideAttempt)});
        const d=await response.json();
        // A definitive server response ends this attempt. Network uncertainty reuses its ID.
        const record=(d.override_requests||[]).find(x=>x.request_id===overrideAttempt.request_id);
        overrideAttempt=null;try{sessionStorage.removeItem(overrideStorage);}catch{}
        if(!response.ok||d.error)throw Error(d.error||'Override request failed');
        applyStatus(d);
        if(record?.status==='BLOCKED_OR_UNKNOWN')throw Error(record.error||'Override blocked or awaiting order reconciliation.');
      }catch(e){el('action-error').textContent=e.message+(overrideAttempt?' Response uncertain; Check override result reuses the same request and cannot place it twice.':'');el('action-error').hidden=false;}
      finally{overrideBusy=false;if(await status()!==false)syncChartControl();}
    };

    async function reconcileBrokerClosure(){
      if(toggleBusy||overrideBusy||!lastRunner||el('reconcile-close').disabled)return;
      toggleBusy=true;el('action-error').hidden=true;syncChartControl();
      try{await request('reconcile-external-close',{run_id:lastRunner.run_id});}
      catch(error){el('action-error').textContent=error.message;el('action-error').hidden=false;}
      finally{toggleBusy=false;if(await status()!==false)syncChartControl();}
    }
    el('reconcile-close').onclick=reconcileBrokerClosure;el('chart-reconcile-close').onclick=reconcileBrokerClosure;
    async function toggleRunner(){if(toggleBusy||overrideBusy||!lastRunner)return;if(!running&&!owned&&lastRunner.indicator_selection_revision!=='independent-indicators-v1'){el('runner-message').textContent='Indicator selection backend update pending; refresh before starting.';return;}toggleBusy=true;el('action-error').hidden=true;el('action-error').textContent='';syncChartControl();try{const action=!lastRunner.running&&(lastRunner.position||lastRunner.pending)?'resume-position':lastRunner.running?'stop':'start';await request(action,action==='resume-position'?{run_id:lastRunner.run_id,mode:lastRunner.config.mode}:action==='stop'?{run_id:lastRunner.run_id,started_at:lastRunner.started_at}:await selectedStartPayload());}catch(e){el('action-error').textContent=e.message;el('action-error').hidden=false;}finally{toggleBusy=false;if(await status()!==false)syncChartControl();}}
    el('toggle').onclick=toggleRunner;el('chart-toggle').onclick=toggleRunner;

    const aggregateJournal=!isNative&&!isEngine;
    const journalApiBase=(location.pathname.match(/^\/broker-workspace\/[^/]+/)?.[0]||'')+apiBase;
    const journalScope=document.createElement('select');journalScope.id='renko-journal-scope';journalScope.setAttribute('aria-label','Trade journal scope');
    journalScope.add(new Option('All saved instances · this account','all'));journalScope.add(new Option('Selected instance','selected'));
    const journalNote=document.createElement('p');journalNote.className='muted';journalNote.setAttribute('role','status');
    if(aggregateJournal){exportLink.parentElement.append(journalScope);exportLink.parentElement.after(journalNote);}
    let journalRefreshAt=0,journalRequestVersion=0,journalBusy=false;
    function journalQuery(){return new URLSearchParams({instance:journalScope.value==='all'?'all':instanceId,mode:el('journal-mode').value});}
    async function refreshJournal(force=false){
      if(!aggregateJournal||isBatchChartView)return;
      if(!force&&(journalBusy||Date.now()-journalRefreshAt<10000))return;journalBusy=true;journalRefreshAt=Date.now();
      const version=++journalRequestVersion;journalNote.textContent=force?'Loading selected scope; previous results remain visible until ready…':'Refreshing journal; displayed records remain available…';exportLink.href=journalApiBase+'journal.xlsx?'+journalQuery();
      try{const response=await fetch(journalApiBase+'journal?'+journalQuery(),{cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'Journal unavailable');if(version!==journalRequestVersion)return;renderTrades(data.trades||[]);journalNote.textContent=(data.trades||[]).length+' recorded trades · '+brokerName+' · '+(journalScope.value==='all'?'all saved instances in this account':'selected instance')+' · '+el('journal-mode').value;}
      catch(error){if(version===journalRequestVersion){journalNote.textContent='Journal refresh unavailable: '+error.message+' · Previous results retained; requested scope has not loaded.';}}finally{if(version===journalRequestVersion)journalBusy=false;}
    }
    journalScope.onchange=()=>refreshJournal(true);
    let renderedTradesKey='';
    function renderTrades(rows){journalRows=rows;const renderKey=JSON.stringify([rows,el('journal-mode').value]);if(renderKey===renderedTradesKey)return;renderedTradesKey=renderKey;const mode=el('journal-mode').value;renderTradeTable(el('trades'),rows.filter(t=>mode==='ALL'||t.mode===mode),brokerName);}
    el('journal-mode').onchange=()=>{if(aggregateJournal)void refreshJournal(true);else renderTrades(journalRows);};
    let lastRunner=null,activeFormKey='';
    function releaseActiveFormLocks(){
      for(const input of section.querySelectorAll('[data-runner-form-lock]')){input.disabled=false;delete input.dataset.runnerFormLock;}
    }
    function synchronizeActiveRunnerForm(state){
      const projection=activeRunnerFields(values(),state);
      let note=el('active-settings-note');
      if(!note){note=document.createElement('p');note.id='renko-active-settings-note';note.setAttribute('role','status');note.style.cssText='grid-column:1/-1;flex-basis:100%;padding:10px 12px;border-left:3px solid #7bbfb9;color:#c6dfdc;font-size:13px;line-height:1.5';el('mode').closest('label').after(note);}
      note.hidden=!projection;
      if(!projection){activeFormKey='';return null;}
      const key=JSON.stringify([state.run_id,state.config]);
      for(const [id,value]of Object.entries(projection)){
        const input=el(id);if(!input)continue;
        const visual=id.endsWith('-indicator')||['volume-enabled','rsi-sma-enabled'].includes(id);
        if(visual&&key===activeFormKey)continue;
        if(input.type==='checkbox')input.checked=value===true;else input.value=String(value);
      }
      if(key!==activeFormKey)clearTimeout(prefsTimer);
      activeFormKey=key;note.textContent='Showing active '+state.config.mode+' · '+state.config.timeframe+(state.config.renko_confirmation==='PRICE'?' reference timeframe · full bricks confirm from live price.':' settings.')+' Stop this runner before editing its execution or strategy settings.';
      if(el('runner-timeframe'))el('runner-timeframe').value=state.config.timeframe;
      return projection;
    }
    function lockActiveRunnerForm(){
      const projection=activeRunnerFields(values(),lastRunner);if(!projection)return;
      for(const id of [...Object.keys(projection),'runner-timeframe']){
        if(id==='symbol'||id.endsWith('-indicator')||['volume-enabled','rsi-sma-enabled','chart-view'].includes(id))continue;
        const input=el(id);if(input){input.disabled=true;input.dataset.runnerFormLock='true';}
      }
    }

    let renderedOrderKey='',renderedAuditKey='';
    function applyStatus(s){if(!el('recovery-status')){const note=document.createElement('span');note.id='renko-recovery-status';note.setAttribute('role','status');note.style.cssText='font-size:13px;padding:6px 10px;color:#b9c9e2';el('chart-toolbar').append(note);}const recovery=s.auto_recovery;el('recovery-status').textContent=recovery?(s.running?'Auto recovery · '+recovery.status.replaceAll('_',' ').toLowerCase()+' · '+recovery.attempts+' recoveries'+(recovery.error?' · '+recovery.error:''):'Auto recovery · stopped by user / awaiting Start'):'Auto recovery · backend update pending';runnerStatusFresh=true;lastRunnerReceived=performance.now();lastRunner=s;synchronizeActiveRunnerForm(s);const nextBasis=JSON.stringify(boundChartContext());if(nextBasis!==chartBasisKey){chartBasisKey=nextBasis;chartParity=null;version++;historyKey='';historyRevision=null;streamKey='';setTimeout(()=>{paintChartBasis();connectStream();load();},0);}syncChartControl();configurationState();paintAssessment();if(el('paper-funds')){const f=s.paper_capital;el('paper-funds').textContent=s.config?.mode==='PAPER'?(f?(f.error||`Virtual INR capital · available ₹${Number(f.available_inr).toLocaleString('en-IN')} · reserved ₹${Number(f.reserved_inr).toLocaleString('en-IN')} · fee provision ₹${Number(f.fee_provision_inr).toLocaleString('en-IN')}`):'Virtual Paper capital update awaits backend deployment; this running session still uses its current balance checks.'):'';}inrPolicy(s);paintPnl(s,streamConnected);paintMarkers();running=!!s.running;owned=!!s.pending||!!s.position;el('state').textContent=s.status;const toggle=toggleState(s,toggleBusy||overrideBusy);el('toggle').textContent=toggle.label;el('toggle').disabled=toggle.disabled;el('runner-message').textContent=s.message||'Runner stopped. Choose the visible mode and settings, then Start Runner.';el('mode').querySelector('option[value="LIVE"]').disabled=!s.live_available;el('pnl').textContent=`Position P&L: ${price(s.pnl?.unrealized)} · Realized ${price(s.pnl?.realized)} · Before fees`;
      el('rsi-htf-active').textContent='Saved runner settings · '+(RSI_HTF_SLOTS.some(i=>s.config?.['rsi_htf_'+i+'_enabled'])?rsiHtfSummary(s.last_signal?.mtf_rsi):'Higher-timeframe RSI OFF. Draft edits apply on next Start.');
      controls();const trail=s.position?.renko_trailing;el('trailing-status').textContent=!s.config?.trailing_enabled?'Trailing stop OFF':trail?'Trailing '+trail.basis+' · best '+price(trail.best)+' · stop '+price(trail.stop):'Trailing enabled · waiting for a fresh post-fill price';
      if(aggregateJournal)void refreshJournal();else renderTrades(s.trade_history||[]);
      const orderKey=JSON.stringify(s.order_history||[]);if(orderKey!==renderedOrderKey){renderedOrderKey=orderKey;table(el('orders'),['Broker ID','Contract','Side','Requested','Filled','Remaining','Status','Reason','Submitted · IST'],(s.order_history||[]).slice(-15).reverse().map(r=>[r.order_id,r.symbol,r.side,r.requested,r.filled,r.remaining,r.status,r.reason,stamp(r.submitted_at)]));}
      const auditKey=JSON.stringify([s.run_id,s.execution_signals||[]]);if(auditKey!==renderedAuditKey){renderedAuditKey=auditKey;table(el('entry-audit'),['Host candle · IST','Direction','Mode','Final status','First assessment','First event · IST','Actual fill · IST','First assessment reason'],(s.execution_signals||[]).filter(e=>e.run_id===s.run_id).slice(-20).reverse().map(e=>[stamp(e.timestamp),e.direction,e.mode,e.status,e.first_assessment?.status||e.status,stamp(e.first_assessment?.event_at||e.event_at),e.first_fill_confirmed_at?stamp(e.first_fill_confirmed_at):'No confirmed fill',e.first_assessment?.reason||e.reason]));}
    }
    async function status(){try{applyStatus(await request('runner'));}catch(e){runnerStatusFresh=false;el('runner-message').textContent=e.message;el('chart-action-error').textContent='Runner status unavailable: '+e.message;el('chart-action-error').hidden=false;syncChartControl();el('override-entry').disabled=true;return false;}}
    el('chart-stack').style.setProperty('display','flex','important');
    const chartScrollBody=document.createElement('div');chartScrollBody.id='renko-chart-scroll-body';chartScrollBody.setAttribute('role','region');chartScrollBody.setAttribute('aria-label','Scrollable chart and study panels');chartScrollBody.tabIndex=0;for(const child of Array.from(el('chart-stack').children))if(child!==el('chart-toolbar'))chartScrollBody.append(child);el('chart-stack').append(chartScrollBody);chartScrollBody.insertBefore(el('candle-readout'),el('chart'));el('candle-readout').setAttribute('aria-live','off');el('candle-readout').setAttribute('aria-label','Hovered candle and indicator values');el('candle-readout').style.cssText='position:relative;z-index:1;display:block;width:100%;min-height:40px;height:auto;max-height:none;overflow:visible;margin:8px 0 0;padding:10px 12px;box-sizing:border-box;font-size:12px;line-height:1.6;background:#0e1625;color:#d1d4dc;border:1px solid #34465b;border-radius:6px;overflow-wrap:anywhere;white-space:normal;pointer-events:none';
    function syncChartDisplay(target){
      if(isBatchChartView)return;
      const card=batchChartFrames.get(instanceId),frame=card?.querySelector('iframe');
      if(!frame||target&&target!==frame.contentWindow)return;
      const symbol=new URL(frame.src).searchParams.get('renkoChartSymbol');
      if(symbol!==el('symbol').value)return;
      frame.contentWindow.postMessage({type:'sector-pulse:renko-chart-display',symbol,selection:chartDisplaySelection(values())},location.origin);
    }
    root.addEventListener('message',event=>{
      if(event.origin!==location.origin)return;
      if(!isBatchChartView&&event.data?.type==='sector-pulse:renko-chart-display-ready'){syncChartDisplay(event.source);return;}
      if(!isBatchChartView||event.source!==root.parent||event.data?.type!=='sector-pulse:renko-chart-display'||event.data.symbol!==el('symbol').value)return;
      const selection=chartDisplaySelection(event.data.selection);
      let changed=false;
      for(const [id,checked]of Object.entries(selection))if(el(id)&&el(id).checked!==checked){el(id).checked=checked;changed=true;}
      if(changed){indicatorControls();paintSelectedIndicators();version++;historyKey='';historyRevision=null;connectStream();load();}
    });
    allIds.forEach(id=>el(id).addEventListener('change',()=>syncChartDisplay()));
    async function restore(){try{const remote=await request('settings');preservePreviousDraft(remote.settings,remote.saved_at,'server draft');const local=JSON.parse(localStorage.getItem(storage)||'null');const restoredMode=remote.saved_at&&(!local||remote.saved_at>Number(local.__saved_at||0))?remote.settings?.mode:local?.mode;if(!modeEdited&&['LIVE','PAPER'].includes(restoredMode))el('mode').value=restoredMode;if(version===0&&remote.saved_at&&(!local||remote.saved_at>Number(local.__saved_at||0))){const saved=inheritRsiHtfFields(migrateDestinations(remote.settings));if(!saved['strategy-basis'])saved['strategy-basis']='LEGACY';if(saved.symbol&&!Array.from(el('symbol').options).some(o=>o.value===saved.symbol))el('symbol').add(new Option(saved.symbol,saved.symbol));for(const id of allIds)if(Object.hasOwn(saved,id)){if((el(id).type==='checkbox'))el(id).checked=saved[id];else el(id).value=saved[id];}localStorage.setItem(storage,JSON.stringify({...saved,__saved_at:remote.saved_at}));}else if(version===0&&local&&!remote.saved_at){const adopted=await request('settings',{settings:values()});localStorage.setItem(storage,JSON.stringify({...values(),__saved_at:adopted.saved_at}));}if(remote.saved_at){if(allIds.every(id=>Object.hasOwn(remote.settings,id)&&remote.settings[id]===values()[id]))savedDraft=JSON.stringify(values());confirmedSavedAt=remote.saved_at;}if(!remote.saved_at&&!local&&JSON.stringify(values())===initialConfigurationSignature)matchInstrumentConfiguration();configurationState();}catch(e){el('runner-message').textContent='Preference restore: '+e.message;}const chartSymbol=pageParams.get('renkoSymbol');if(!isDelta&&chartSymbol&&/^(?:NSE:)?[A-Z0-9&_-]+(?:-EQ)?$/.test(chartSymbol)){const exact=chartSymbol.startsWith('NSE:')?chartSymbol:'NSE:'+chartSymbol+'-EQ';el('market').value='NSE_EQUITY';el('search').value=chartSymbol.replace(/^NSE:/,'').replace(/-EQ$/,'');if(!Array.from(el('symbol').options).some(o=>o.value===exact))el('symbol').add(new Option(exact,exact));el('symbol').value=exact;}const batchSymbol=pageParams.get('renkoChartSymbol');if(isBatchChartView&&batchSymbol){if(!Array.from(el('symbol').options).some(o=>o.value===batchSymbol))el('symbol').add(new Option(batchSymbol,batchSymbol));el('symbol').value=batchSymbol;el('search').value=batchSymbol;}controls();if(!isDelta)searchInstruments();connectStream();await status();if(instanceId!=='default'&&!el('symbol').value&&(lastRunner?.config?.underlying||lastRunner?.instrument)){const c=lastRunner.config||{underlying:lastRunner.instrument,timeframe:el('timeframe').value,mode:el('mode').value};if(!Array.from(el('symbol').options).some(o=>o.value===c.underlying))el('symbol').add(new Option(c.underlying,c.underlying));el('symbol').value=c.underlying;if(isDhan&&c.underlying.startsWith('MCX:'))el('market').value='MCX';el('timeframe').value=c.timeframe;el('mode').value=(lastRunner.running||lastRunner.position||lastRunner.pending)?c.mode:(['LIVE','PAPER'].includes(pageParams.get('renkoNextMode'))?pageParams.get('renkoNextMode'):el('mode').value);controls();connectStream();}syncDisplayedChartSelection();void refreshBroker();el('start-selected').textContent='Start selected · '+el('mode').value;if(isDelta&&!el('symbol').value){el('symbol').add(new Option('ETHUSD · Delta perpetual','ETHUSD'));el('symbol').value='ETHUSD';}indicatorControls();controls();configurationState();if(el('brick-mode').value==='Manual')await deriveManualBrick();if(active&&el('symbol').value)load();if(isBatchChartView&&root.parent!==root)root.parent.postMessage({type:'sector-pulse:renko-chart-display-ready',symbol:el('symbol').value},location.origin);else syncChartDisplay();}if(isBatchChartView){const compact=document.createElement('style');compact.textContent='body .side{display:none!important}body .desk{display:block!important}body .work{padding:8px!important}#renko-supertrend>*,#renko-supertrend>.panel:has(#renko-chart-stack)>*{display:none!important}#renko-supertrend>.panel:has(#renko-chart-stack),#renko-supertrend>.panel:has(#renko-chart-stack)>#renko-chart-stack{display:block!important}#renko-supertrend>.panel:has(#renko-chart-stack){margin:0!important;padding:0!important}#renko-chart-stack{margin:0!important}';document.head.append(compact);}if(isEngine)root.RenkoEngine.finish({el,isBatchChartView});restore();if(isDelta)root.DeltaINR.load().then(()=>{if(lastRunner)applyStatus(lastRunner);if(el('symbol').value)load();});
    for(const id of [...RSI_HTF_IDS,'supertrend-exit-enabled','ema-slow-exit-enabled','rsi-exit-enabled','ema-widening-exit-enabled','adx-exit-enabled','market-structure-exit-enabled','volume-enabled','rsi-sma-enabled','rsi-length','ema-exit-length','supertrend-enabled','ema-fast-enabled','ema-slow-enabled','ema-third-enabled','ema-widening-enabled','ema-fast-length','ema-slow-length','ema-third-length','rsi-slope-enabled','use-adx','market-structure-enabled','ema-proximity-enabled','ema-proximity-mode','ema-proximity-distance','ema-momentum-enabled','higher-timeframe-enabled','zone-target-enabled','ema-exit-enabled','sideways-enabled','trailing-enabled'])el(id).addEventListener('change',()=>{indicatorControls(id);paintSelectedIndicators();});
    DESTINATION_RULES.forEach(id=>el(id+'-indicator').addEventListener('change',()=>{indicatorControls(id+'-indicator');paintSelectedIndicators();connectStream();load();}));
    signalIds.forEach(id=>el(id).addEventListener('change',connectStream));
    async function recoverSilentStream(){
      if(!section.classList.contains('active')||document.hidden||!el('symbol').value||streamRecoveryBusy)return;
      const now=performance.now(),last= Math.max(statusReceived,streamAttemptAt);
      if(now-last<15000||now-streamRecoveryAt<10000)return;
      streamRecoveryBusy=true;streamRecoveryAt=now;runnerStatusFresh=false;streamConnected=false;
      stream?.close();stream=null;streamKey='';++streamEpoch;
      try{await Promise.allSettled([status(),connectStream()]);}finally{streamRecoveryBusy=false;}
    }
    setInterval(recoverSilentStream,5000);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden){void recoverSilentStream();connectStream();if(el('symbol').value)load();}});
    window.addEventListener('pagehide',()=>{stream?.close();stream=null;streamKey='';++streamEpoch;});
    const streamObserver=new MutationObserver(()=>{if(section.classList.contains('active')){connectStream();if(!chart)load();}});streamObserver.observe(section,{attributes:true,attributeFilter:['class']});
  }
  root.RenkoSupertrend={mount,signalSettings,renderTradeTable};
  function readableChartViewport(width,height,total){
    const spacing=Math.max(10,Math.min(22,Number(height)/32));
    const gutter=Math.min(230,Math.max(120,Number(width)*.22)),rightOffset=Math.ceil(gutter/spacing);
    const count=Math.max(12,Math.min(160,Math.floor(Math.max(120,Number(width)-80-gutter)/spacing)));
    return {range:{from:Math.max(0,total-count),to:total+rightOffset},rightOffset,spacing,scaleMargins:{top:.12,bottom:.20}};
  }
  if(typeof module!=='undefined')module.exports={refreshChartViewport,runnerStartContext,chartSessionBreaks,provisionalRenkoBricks,universalStrategyDefaults,activeRunnerFields,uniformRenkoBricks,renkoStudyPoints,ANTI_CHOP_DEFAULTS,antiChopSettings,mountChartDrawings,FAMILY_RULES,familySettings,effectiveFamilySettings,effectiveChartChoice,candleInspection,testedNiftyDefaults,chartDisplaySelection,migrateAtrProfile,entryDecisionText,assessedHigherRows,configurationComparisonRows,mergeChartRows,chartHistoricalEvents,runnerChartContext,runnerChartAlignment,studyHoverValue,coalescedHover,chartSettingsFailure,inheritRsiHtfFields,rsiHtfSettings,rsiHtfSummary,requireRsiHtfSupport,chartSelectionForInstrument,stopAllRenko,DESTINATION_RULES,migrateDestinations,chartSettings,ownedEntryPrice,feedPresentation,feedHealthSummary,lastKnownIndicator,readableChartViewport,deleteConfiguration,configurationLibrary,chooseConfiguration,storeConfiguration,restoredConfigurationFields,fiveMinuteSupertrendPoints,chartControlState,overrideState,costPnlValues,configurationText,hostZones,zoneBandRect,fiveMinuteZoneRows,signalSettings,volumePoints,chartCandles,chartAnalysisAvailable,chartStreamStatus,chartStreamHealth,toggleState,renderTradeTable,pnlValues,executionMarkers,rsiStep,rsiHistory,rsiSma,rsiZone,STRATEGY};
})(typeof window==='undefined'?globalThis:window);
