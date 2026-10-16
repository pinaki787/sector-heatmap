/* Read-only explanation of the current runner snapshot; never an entry signal. */
(function(root){
  const intervals={'1 minute':60,'2 minutes':120,'3 minutes':180,'5 minutes':300,'10 minutes':600,'15 minutes':900,'30 minutes':1800,'1 hour':3600};
  const finite=Number.isFinite;
  function assessment(s,view,now=Date.now()/1000,connected=true){
    const c=s?.config,latest=s?.last_signal,record=s?.latest_entry_assessment;
    const decision=record&&record.run_id===s.run_id&&record.underlying===c?.underlying&&record.timeframe===c?.timeframe&&record.timestamp===latest?.timestamp?record:null;
    const q=decision?.signal||latest,seconds=intervals[c?.timeframe];
    const result={title:'Latest runner assessment',reason:'No armed runner assessment available.',checks:[],timestamp:null,close:null,provisional:false,fresh:false,tone:'waiting',context:'Runner evidence only · no historical annotations'};
    if(!c)return result;
    result.rules='Rules: '+[c.supertrend_enabled!==false?'Renko Supertrend':null,c.ema_fast_enabled!==false?'EMA '+(c.ema_fast_length||10):null,c.ema_slow_enabled!==false?'EMA '+(c.ema_slow_length||30):null,c.ema_widening_enabled!==false?c.widening_window+'-candle widening':null,c.rsi_slope_enabled?'RSI '+(c.rsi_slope_length||14)+' slope':null,c.use_adx?'ADX > '+c.adx_threshold:null,c.market_structure_enabled?'Swing structure':null,c.ema_proximity_enabled?'EMA proximity':null].filter(Boolean).join(' + ')+' · exit '+(c.ema_exit_enabled?'EMA'+c.ema_exit_length:'EMA off');
    result.context=`Active ${c.mode} · ${c.underlying} · ${c.timeframe}`;
    if(c.underlying!==view.symbol||c.timeframe!==view.timeframe){result.reason=`Chart differs from active runner (${c.underlying} · ${c.timeframe}).`;return result;}
    const provisional=!!q?.provisional;
    result.provisional=provisional;
    result.timestamp=finite(q?.timestamp)?q.timestamp:null;
    result.close=finite(q?.close)?q.close:null;
    const expected=seconds?Math.floor(now/seconds)*seconds-(provisional?0:seconds):null;
    const tickFresh=!provisional||finite(q?.market_event_at)&&now-q.market_event_at>=0&&now-q.market_event_at<=15;
    result.age=finite(s.updated_at)?Math.max(0,Math.floor(now-s.updated_at)):null;
    result.fresh=connected&&s.stream?.connected!==false&&result.age!==null&&now-s.updated_at>=0&&result.age<=15&&result.timestamp===expected&&tickFresh;
    if(!s.running){result.title=s.position?'Monitoring stopped · position remains':'Runner stopped';result.reason=s.position?'Owned position remains; entry assessment is inactive.':'No entries assessed while stopped.';return result;}
    if(s.pending){result.title='Order reconciliation';result.reason='Owned order is pending; no new entry assessment.';return result;}
    if(s.position){result.title='Position management';result.reason=`Holding ${s.position.symbol}; managing configured exits, not a new entry.`;return result;}
    if(s.status==='WAITING_FOR_STREAM'||s.stream?.connected===false){result.reason='Waiting for the runner market stream; entry data unavailable.';return result;}
    if(!q||!finite(q.timestamp)){result.reason='Latest assessment unavailable; waiting for runner evidence.';return result;}
    if(!result.fresh){result.reason=s.status==='BLOCKED'&&s.message?'Entry data unavailable: '+s.message+' Last saved assessment is not current.':'Latest assessment stale / unavailable; saved conditions are not a current entry decision.';return result;}
    const lock=s.sideways_status?.lock;
    if(lock?.active){result.title='Quick-loss range lock';result.reason='Recorded after-cost loss lock: strict breakout required. This does not classify the market as sideways.';result.tone='blocked';return result;}
    const observed=provisional?q.market_event_at:q.timestamp+seconds;
    const beforeEligibility=finite(s.eligible_since)&&observed<=s.eligible_since;
    const recovery=(s.history_recoveries||[]).at(-1);
    const legacyRecovery=!decision&&beforeEligibility&&recovery?.at===s.eligible_since;
    result.assessed_at=decision?.observed_at??null;
    result.history_revised_at=decision?.history_revised_at??s.history_revised_at??recovery?.at??null;
    const bullish=q.direction==='BULLISH',bearish=q.direction==='BEARISH';
    if(c.rsi_level_enabled){
      const mode=q.rsi_level_mode??c.rsi_level_mode;
      const bound=k=>q[k]??c[k];
      const range=mode==='BETWEEN'?`${bound(bullish?'rsi_bullish_min':'rsi_bearish_min')}–${bound(bullish?'rsi_bullish_max':'rsi_bearish_max')} inclusive`:`${bullish?'>':'<'} ${bound(bullish?'rsi_bullish_above':'rsi_bearish_below')}`;
      result.checks.push(`${q.rsi_level_pass===true?'PASS':q.rsi_level_pass===false?'WAIT':'UNAVAILABLE'} · RSI entry level ${finite(q.rsi14)?q.rsi14.toFixed(2):'warming up'} · ${range}`);
    }
    if((c.ema_fast_enabled!==false||c.ema_slow_enabled!==false)&&(bullish||bearish)&&finite(q.ema10)&&finite(q.ema30)&&finite(q.close)){
      const fast=c.ema_fast_enabled!==false,slow=c.ema_slow_enabled!==false;const aligned=(!fast||(bullish?q.close>q.ema10:q.close<q.ema10))&&(!slow||(bullish?q.close>q.ema30:q.close<q.ema30))&&(!(fast&&slow)||(bullish?q.ema10>q.ema30:q.ema10<q.ema30));
      result.checks.push(`${aligned?'PASS':'WAIT'} · ${bullish?'Bullish':'Bearish'} close / EMA10 / EMA30`);
    }
    if(c.use_adx)result.checks.push(`${q.signal_allowed===true?'PASS':q.signal_allowed===false?'WAIT':'UNKNOWN'} · ADX ${finite(q.adx)?q.adx.toFixed(1):'unavailable'} > ${c.adx_threshold}`);
    else result.checks.push('OFF · ADX gate');
    if(c.ema_widening_enabled!==false&&typeof q.ema_widening==='boolean')result.checks.push(`${q.ema_widening?'PASS':'WAIT'} · EMA gap widening (${c.widening_window})`);
    if(c.retest_enabled)result.checks.push(q.retest_signal?'PASS · Confirmed retest pattern':q.retest_rsi_blocked?'WAIT · Confirmed retest blocked by RSI slope':provisional?'WAIT · Retest needs completed pattern':q.retest_touch_evidence?'WAIT · EMA10 touch recorded; matching pattern and directional close required':'WAIT · No confirmed retest entry; no active EMA10 touch evidence');
    if(c.rsi_slope_enabled)result.checks.push(`${q.rsi_slope_pass?'PASS':'WAIT'} · RSI14 slope ${finite(q.rsi14_slope)?q.rsi14_slope.toFixed(3):'warming up'} · ${bullish?'rising':'falling'} required`);
    else result.checks.push('OFF · RSI slope filter');
    if(c.ema_proximity_enabled)result.checks.push(`PENDING · Proximity entry only: ${c.ema_proximity_mode==='ATR'?'|price − EMA10| / completed ATR':'|price − EMA10|'} ≤ ${c.ema_proximity_distance}${c.ema_proximity_mode==='ATR'?'':' points'} at live preflight`);
    const diagnostics={WAITING_SUPERTREND_REVERSAL:'No entry: waiting for a selected Supertrend reversal.',NO_DIRECTIONAL_INDICATOR:'No entry: select a directional indicator.',WAITING_SELECTED_ALIGNMENT:'No entry: selected indicators do not agree.',WAITING_RSI_WARMUP:'No entry: RSI14 slope needs two seeded host-candle values.',WAITING_RSI_FLAT:'No entry: RSI14 slope is flat.',WAITING_RSI_DIRECTION:'No entry: RSI14 slope opposes entry direction.',WAITING_ADX:'No entry: ADX gate has not qualified.',WAITING_EMA_ALIGNMENT:'No entry: EMA10 / EMA30 direction alignment has not qualified.',WAITING_CLOSE:'No entry: close is on the wrong side of EMA10.',WAITING_WIDENING:'No entry: EMA gap is not strictly widening.',ENTRY_CUTOFF:'No entry: configured entry cutoff reached.'};
    const events=(s.execution_signals||[]).filter(e=>e.run_id===s.run_id&&e.timestamp===q.timestamp&&e.underlying===c.underlying).sort((a,b)=>(b.observed_at||0)-(a.observed_at||0));
    const event=events[0];
    if(event&&event.status==='BLOCKED'){result.reason='Blocked at runner preflight: '+(event.reason||'Execution preflight rejected this candle.');result.tone='blocked';if(c.ema_proximity_enabled&&/too far from EMA10/i.test(event.reason||''))result.checks=result.checks.map(x=>x.startsWith('PENDING · Proximity')?'BLOCKED · '+event.reason:x);}
    else if(s.status==='BLOCKED'&&s.message){result.reason='Blocked at runner preflight: '+s.message;result.tone='blocked';}
    else if(event&&event.status==='FILLED'){result.reason='Latest entry assessment filled; see owned trade journal.';result.tone='pass';}
    else if(legacyRecovery){result.reason='Historical OHLC revised at '+new Date(recovery.at*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'})+'; this candle was excluded from entry eligibility. Its rule checks remain available below.';result.tone='blocked';}
    else if(decision&&decision.code!=='ELIGIBLE'){result.reason=diagnostics[decision.code]||decision.reason;}
    else if(!decision&&beforeEligibility){result.reason='Entry ineligible: this candle predates entry eligibility (arming, reconnect or lock-release boundary).';}
    else if(event&&event.eligible===false){result.reason='No entry: '+(event.first_assessment?.reason||event.reason||'signal not eligible.');}
    else if(diagnostics[q.entry_diagnostic])result.reason=diagnostics[q.entry_diagnostic];
    else if(q.entry_qualified===true&&!q.cross_direction&&!q.entry_direction)result.reason='Setup passes; waiting for a fresh entry event. Qualification alone does not authorize another entry.';
    else if(decision?.eligible||event?.eligible)result.reason='Entry signal eligible; execution preflight / fill not yet confirmed.';
    else result.reason='Latest snapshot available; exact execution decision not recorded yet.';
    if(decision?.code==='WAITING_RSI_LEVEL'||!decision&&q.entry_diagnostic==='WAITING_RSI_LEVEL')result.reason='No entry: RSI is outside the active entry threshold or range.';
    result.title=provisional?'Latest assessment · provisional':'Latest assessment · completed candle';
    if(q.entry_data_mode==='COMPLETED_CANDLE_FALLBACK')result.checks.push('WAIT · Intrabar OHLC unavailable; assessing verified completed candle. Fresh execution preflight still required.');
    result.link=result.fresh&&result.timestamp!==null&&result.close!==null;
    return result;
  }
  function exitAssessment(s,view,now=Date.now()/1000,connected=true){
    const c=s?.config,p=s?.position,q=s?.last_signal;
    const r={title:'Exit assessment',reason:'No active runner configuration.',checks:[],fresh:false,context:''};
    if(!c)return r;
    r.context=`Active ${c.mode} · ${c.underlying} · ${c.timeframe}`;
    if(c.underlying!==view.symbol||c.timeframe!==view.timeframe){r.reason='Chart differs from active runner; exit evidence unavailable for this view.';return r;}
    const age=finite(s.updated_at)?now-s.updated_at:null;
    r.fresh=connected&&s.stream?.connected!==false&&age!==null&&age>=0&&age<=15;
    const record=s.latest_exit_assessment;
    const ownedRecord=p&&record&&finite(record.timestamp)&&finite(p.entry_signal_timestamp)&&record.timestamp>=p.entry_signal_timestamp?record:null;
    const seconds=intervals[c.timeframe],closed=q&&!q.provisional&&!q.is_forming&&finite(q.timestamp)&&seconds&&now-q.timestamp-seconds>=0&&now-q.timestamp-seconds<=seconds;
    const usable=r.fresh&&s.running&&p&&closed;
    const bull=p?.direction==='BULLISH',opposite=bull?'BEARISH':'BULLISH';
    const check=(enabled,label,hit)=>r.checks.push({label,state:!enabled?'OFF':!p?'NO POSITION':!usable||hit===null?'UNAVAILABLE':hit?'CONDITION MET':'NOT MET'});
    check(c.ema_exit_enabled===true,'EMA '+(c.ema_exit_length||10)+' adverse close',finite(q?.close)&&finite(q?.ema_exit??q?.ema10)?(bull?q.close<(q.ema_exit??q.ema10):q.close>(q.ema_exit??q.ema10)):null);
    check(c.supertrend_exit_enabled!==false,'Opposite Supertrend reversal',q&&Object.hasOwn(q,'supertrend_cross_direction')?q.supertrend_cross_direction===opposite:null);
    check(c.ema_slow_exit_enabled,'EMA '+(c.ema_slow_length||30)+' adverse close',finite(q?.close)&&finite(q?.ema30)?(bull?q.close<q.ema30:q.close>q.ema30):null);
    check(c.rsi_exit_enabled,'Opposing RSI slope',finite(q?.rsi14_slope)?(bull?q.rsi14_slope<0:q.rsi14_slope>0):null);
    check(c.ema_widening_exit_enabled,'EMA gap contraction',finite(q?.ema_gap)&&finite(q?.exit_previous_ema_gap)?Math.abs(q.ema_gap)<Math.abs(q.exit_previous_ema_gap):null);
    check(c.adx_exit_enabled,'ADX below '+(c.adx_threshold??25),finite(q?.adx)?q.adx<(c.adx_threshold??25):null);
    check(c.market_structure_exit_enabled,'Opposing confirmed swings',q?.exit_market_structure?.state?q.exit_market_structure.state===(bull?'BEARISH_LH_LL':'BULLISH_HH_HL'):null);
    for(const [key,label] of [['spot_stop','Underlying stop'],['spot_target','Underlying target']])r.checks.push({label:label+(finite(c[key])?' '+c[key]:''),state:finite(c[key])?(p?'LIVE TICK RULE':'NO POSITION'):'OFF'});
    const trail=p?.renko_trailing;
    r.checks.push({label:'Trailing stop'+(finite(trail?.stop)?' '+trail.stop:'')+(c.trailing_enabled?' · '+c.trailing_basis+' · '+c.trailing_distance:''),state:!c.trailing_enabled?'OFF':!p?'NO POSITION':!r.fresh?'UNAVAILABLE':trail?'TRACKING':'AWAITING FRESH QUOTE'});
    const zone=p?.zone_target_assessment;
    r.checks.push({label:'Opposing 5m zone',state:!c.zone_target_enabled?'OFF':!p?'NO POSITION':!r.fresh||p.zone_target_error?'UNAVAILABLE':zone?.state||'AWAITING ASSESSMENT'});
    r.reason=!s.running?(p?'Monitoring stopped · position remains.':'Runner stopped · exit rules inactive.') :s.pending?'Order reconciliation pending; no exit fill is confirmed.':!p?'No owned position · exit criteria shown for the active configuration.':p.exit_requested?'Exit requested: '+(p.exit_reason||'runner exit intent')+' · awaiting reconciliation.':!r.fresh?'Runner snapshot stale or disconnected; current exit decision unavailable.':'Holding '+p.symbol+' · no exit request recorded.';
    r.checks=r.checks.filter(item=>item.state!=='OFF'&&item.state!=='NO SESSION DEADLINE');
    r.record=ownedRecord?{timestamp:ownedRecord.timestamp,observed_at:ownedRecord.observed_at,reason:ownedRecord.reason,eligible:ownedRecord.eligible}:null;
    r.checks.push({label:'Session square-off'+(c.session_deadline?' '+c.session_deadline+' IST':''),state:c.session_deadline?'SCHEDULED':'NO SESSION DEADLINE'});
    r.context+=' · '+(c.intrabar_entries?'EMA exits may use fresh intrabar breaches; other indicator exits use completed candles.':'Indicator exits use completed candles.')+' Fixed levels and trailing use fresh ticks. Conditions shown are observations, not confirmed exit fills.';
    return r;
  }
  root.RenkoAssessment={assessment,exitAssessment};
  if(typeof module!=='undefined')module.exports={assessment,exitAssessment};
})(typeof window==='undefined'?globalThis:window);
