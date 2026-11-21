/* Analytical Renko study alignment. Not connected to chart controls yet. */
(function(root) {
  'use strict';
  function renkoStudyClock(bars) {
    let previousSource=-Infinity, previousClock=-Infinity, duplicate=0, provisional=false;
    return bars.map(bar=>{
      const source=bar.sourceTime;
      if(!Number.isFinite(source)||source<previousSource) throw new RangeError('Renko source times must be ordered and finite');
      if(provisional&&!bar.provisional) throw new RangeError('Confirmed Renko bars must precede projections');
      provisional=provisional||!!bar.provisional;
      duplicate=source===previousSource?duplicate+1:0;
      previousSource=source;
      const clock=source+duplicate/1000;
      if(clock<=previousClock)throw new RangeError('Renko synthetic times collide');
      previousClock=clock;
      return clock;
    });
  }
  function alignRenkoStudyPlots(plots,reference,host,options={}) {
    if(plots.some(plot=>plot.length!==reference.length)) throw new RangeError('Renko study plot length differs from reference');
    const sourceClock=renkoStudyClock(reference),hostClock=renkoStudyClock(host);
    const output=plots.map(plot=>{const values=[];if(Array.isArray(plot.colors))values.colors=[];return values;});
    let latest=-1;
    for(let i=0;i<host.length;i++) {
      const closed=i+1<host.length&&!host[i].provisional&&!host[i+1].provisional?hostClock[i+1]:null;
      let selected=-1;
      if(closed!==null) {
        while(latest+1<reference.length-1&&!reference[latest+1].provisional&&!reference[latest+2].provisional&&sourceClock[latest+2]<=closed) {
          latest++;
          if(sourceClock[latest+1]>hostClock[i])selected=latest;
        }
      }
      if(options.gaps===false)selected=latest;
      plots.forEach((plot,p)=>{
        output[p].push(selected<0?null:plot[selected]??null);
        if(output[p].colors)output[p].colors.push(selected<0?undefined:plot.colors[selected]);
      });
    }
    return output;
  }
  function applyConfirmedRenkoStudyTail(aligned,plots,reference,host,options={}) {
    const {live,confirmedThrough,now,updatedAt}=options;
    if(live!==true||!host.length||host.at(-1).historyOnly
        ||![confirmedThrough,now,updatedAt].every(Number.isFinite)
        ||confirmedThrough>now||updatedAt>now+2||now-updatedAt>=60) return aligned;
    if(plots.length!==aligned.length||plots.some(p=>p.length!==reference.length)
        ||aligned.some(p=>p.length!==host.length))throw new RangeError('Renko tail plot shape differs from history');
    let latest=-1;
    reference.forEach((bar,index)=>{
      if(!bar.provisional&&!bar.historyOnly&&Number.isFinite(bar.sourceTime)&&bar.sourceTime<confirmedThrough)latest=index;
    });
    if(latest<0)return aligned;
    return aligned.map((plot,index)=>{
      const copy=plot.slice();
      copy[copy.length-1]=plots[index][latest]??null;
      if(Array.isArray(plot.colors)||Array.isArray(plots[index].colors)){
        copy.colors=plot.colors?plot.colors.slice():Array(plot.length).fill(undefined);
        copy.colors[copy.length-1]=plots[index].colors?.[latest];
      }
      return copy;
    });
  }
  const publicationStates=new WeakMap();
  function renkoStudyPublication(study,scope,key) {
    if(!study||typeof study!=='object'||!scope||scope.aborted)return undefined;
    let state=publicationStates.get(study);
    if(!state||state.scope!==scope||state.key!==key){
      state={scope,key};publicationStates.set(study,state);
    }
    return state;
  }

  function applyRenkoStudyPublication(aligned,plots,reference,host,options={},state) {
    if(!state||options.live!==true||!host.length)return applyConfirmedRenkoStudyTail(aligned,plots,reference,host,options);
    const clock=renkoStudyClock(host),known=new Set(clock);
    if(!(state.rows instanceof Map)||!known.has(state.lastClock))state.rows=new Map();
    const out=aligned.map(plot=>{
      const copy=plot.slice();if(Array.isArray(plot.colors))copy.colors=plot.colors.slice();return copy;
    });
    for(let i=0;i<clock.length;i++){
      const saved=state.rows.get(clock[i]);
      if(!saved)continue;
      out.forEach((plot,p)=>{
        plot[i]=saved.values[p]??null;
        if(saved.colors){plot.colors??=Array(host.length).fill(undefined);plot.colors[i]=saved.colors[p];}
      });
    }
    const tail=applyConfirmedRenkoStudyTail(aligned,plots,reference,host,options);
    if(tail!==aligned){
      const start=clock.indexOf(state.lastClock);
      for(let i=start<0?host.length-1:start;i<host.length;i++){
        const values=tail.map(plot=>plot.at(-1));
        const colors=tail.some(plot=>Array.isArray(plot.colors))?tail.map(plot=>plot.colors?.at(-1)):undefined;
        state.rows.set(clock[i],{values,colors});
        out.forEach((plot,p)=>{
          plot[i]=values[p]??null;
          if(colors){plot.colors??=Array(host.length).fill(undefined);plot.colors[i]=colors[p];}
        });
      }
      state.lastClock=clock.at(-1);
    }
    for(const key of state.rows.keys())if(!known.has(key))state.rows.delete(key);
    return out;
  }

  // Display-only Close-source projections. Never feed these into confirmed studies.
  function closeRenkoProjection(previous,price,size,sourceTime) {
    if(!previous||![previous.open,previous.close,price,size,sourceTime].every(Number.isFinite)||size<=0)
      throw new TypeError('Invalid Renko projection input');
    const direction=Math.sign(previous.close-previous.open);
    if(!direction||Math.abs(Math.abs(previous.close-previous.open)-size)>size*1e-8)
      throw new RangeError('Projection requires a confirmed full brick');
    const delta=price-previous.close,step=Math.sign(delta),reversal=step!==direction;
    if(!step)return [];
    let open=previous.close+(reversal?step*size:0);
    if(step*(price-open)<=size*1e-10)return [];
    const count=Math.ceil(Math.abs(price-open)/size-1e-10);
    if(count>1000)throw new RangeError('Increase the projection brick size');
    const result=[];
    for(let i=0;i<count;i++) {
      const close=i===count-1?price:open+step*size;
      result.push({sourceTime,provisional:true,open,high:Math.max(open,close),low:Math.min(open,close),close});
      open=close;
    }
    return result;
  }
  function calculateRenkoTimeframeStudy(options) {
    const {sourceBars,hostBars,renko,run,size,previousBrick,liveState}=options;
    if(!Array.isArray(sourceBars)||!Array.isArray(hostBars)||typeof renko!=='function'||typeof run!=='function'
        ||!Number.isFinite(size)||size<=0)throw new TypeError('Invalid Renko timeframe calculation');
    const confirmed=sourceBars.filter(bar=>!bar.provisional&&!bar.historyOnly);
    const reference=renko(confirmed,size,previousBrick,options.source??'close',options.showWicks===true);
    const sourcePlots=run(reference);
    const aligned=alignRenkoStudyPlots(sourcePlots,reference,hostBars,{gaps:options.waitForClose!==false});
    const plots=applyRenkoStudyPublication(aligned,sourcePlots,reference,hostBars,liveState,options.publication);
    return {reference,plots,size,projectionAvailable:false};
  }
  root.SectorPulseRenkoStudyAlignment={renkoStudyClock,alignRenkoStudyPlots,applyConfirmedRenkoStudyTail,calculateRenkoTimeframeStudy,closeRenkoProjection,applyRenkoStudyPublication,renkoStudyPublication};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.SectorPulseRenkoStudyAlignment;
})(typeof window==='undefined'?globalThis:window);
