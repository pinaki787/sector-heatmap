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
    result.rules=`Rules: EMA10/30 alignment + ${c.widening_window}-candle widening${c.use_adx?' + ADX > '+c.adx_threshold:''}${c.retest_enabled?' or confirmed retest':''}${c.ema_proximity_enabled?' · proximity '+c.ema_proximity_distance+' '+c.ema_proximity_mode+' at preflight':''} · exit ${c.ema_exit_enabled?'EMA'+c.ema_exit_length:'EMA off'}`;
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
    if((bullish||bearish)&&finite(q.ema10)&&finite(q.ema30)&&finite(q.close)){
      const aligned=bullish?q.close>q.ema10&&q.ema10>q.ema30:q.close<q.ema10&&q.ema10<q.ema30;
      result.checks.push(`${aligned?'PASS':'WAIT'} · ${bullish?'Bullish':'Bearish'} close / EMA10 / EMA30`);
    }
    if(c.use_adx)result.checks.push(`${q.signal_allowed===true?'PASS':q.signal_allowed===false?'WAIT':'UNKNOWN'} · ADX ${finite(q.adx)?q.adx.toFixed(1):'unavailable'} > ${c.adx_threshold}`);
    else result.checks.push('OFF · ADX gate');
    if(typeof q.ema_widening==='boolean')result.checks.push(`${q.ema_widening?'PASS':'WAIT'} · EMA gap widening (${c.widening_window})`);
    if(c.retest_enabled)result.checks.push(q.retest_signal?'PASS · Confirmed retest pattern':q.retest_rsi_blocked?'WAIT · Confirmed retest blocked by RSI slope':provisional?'WAIT · Retest needs completed pattern':q.retest_touch_evidence?'WAIT · EMA10 touch recorded; matching pattern and directional close required':'WAIT · No confirmed retest entry; no active EMA10 touch evidence');
    if(c.rsi_slope_enabled)result.checks.push(`${q.rsi_slope_pass?'PASS':'WAIT'} · RSI14 slope ${finite(q.rsi14_slope)?q.rsi14_slope.toFixed(3):'warming up'} · ${bullish?'rising':'falling'} required`);
    else result.checks.push('OFF · RSI slope filter');
    if(c.ema_proximity_enabled)result.checks.push(`PENDING · Proximity ≤ ${c.ema_proximity_distance} ${c.ema_proximity_mode==='ATR'?'completed ATR':'points'} at live preflight`);
    const diagnostics={WAITING_RSI_WARMUP:'No entry: RSI14 slope needs two seeded host-candle values.',WAITING_RSI_FLAT:'No entry: RSI14 slope is flat.',WAITING_RSI_DIRECTION:'No entry: RSI14 slope opposes entry direction.',WAITING_ADX:'No entry: ADX gate has not qualified.',WAITING_EMA_ALIGNMENT:'No entry: EMA10 / EMA30 direction alignment has not qualified.',WAITING_CLOSE:'No entry: close is on the wrong side of EMA10.',WAITING_WIDENING:'No entry: EMA gap is not strictly widening.',ENTRY_CUTOFF:'No entry: configured entry cutoff reached.'};
    const events=(s.execution_signals||[]).filter(e=>e.run_id===s.run_id&&e.timestamp===q.timestamp&&e.underlying===c.underlying).sort((a,b)=>(b.observed_at||0)-(a.observed_at||0));
    const event=events[0];
    if(s.status==='BLOCKED'&&s.message){result.reason='Blocked at runner preflight: '+s.message;result.tone='blocked';}
    else if(event&&event.status==='FILLED'){result.reason='Latest entry assessment filled; see owned trade journal.';result.tone='pass';}
    else if(legacyRecovery){result.reason='Historical OHLC revised at '+new Date(recovery.at*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'})+'; this candle was excluded from entry eligibility. Its rule checks remain available below.';result.tone='blocked';}
    else if(decision&&decision.code!=='ELIGIBLE'){result.reason=diagnostics[decision.code]||decision.reason;}
    else if(!decision&&beforeEligibility){result.reason='Entry ineligible: this candle predates entry eligibility (arming, reconnect or lock-release boundary).';}
    else if(event&&event.eligible===false){result.reason='No entry: '+(event.first_assessment?.reason||event.reason||'signal not eligible.');}
    else if(diagnostics[q.entry_diagnostic])result.reason=diagnostics[q.entry_diagnostic];
    else if(q.entry_qualified===true&&!q.cross_direction&&!q.entry_direction)result.reason='Setup passes; waiting for a fresh entry event. Qualification alone does not authorize another entry.';
    else if(decision?.eligible||event?.eligible)result.reason='Entry signal eligible; execution preflight / fill not yet confirmed.';
    else result.reason='Latest snapshot available; exact execution decision not recorded yet.';
    result.title=provisional?'Latest assessment · provisional':'Latest assessment · completed candle';
    result.link=result.fresh&&result.timestamp!==null&&result.close!==null;
    return result;
  }
  root.RenkoAssessment={assessment};
  if(typeof module!=='undefined')module.exports={assessment};
})(typeof window==='undefined'?globalThis:window);
