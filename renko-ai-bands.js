/* Selected underlying High/Low bands. No feed, order, or chart-history requests. */
(function(root){'use strict';
const colors={SMA:'#38bdf8',EMA:'#a78bfa'};
function cloudColor(kind,point){return kind==='SMA'?(Number.isFinite(point?.close)&&point.close>point.upper?'#22c55e':Number.isFinite(point?.close)&&point.close<point.lower?'#ef4444':'#94a3b8'):colors[kind];}
class BandState{
 constructor(kind,period){if(!colors[kind]||!Number.isInteger(period)||period<1||period>500)throw Error('Invalid band settings');this.kind=kind;this.period=period;this.rows=[];this.points=[];this.last=null;this.lastStamp=-Infinity;}
 push(row){
  const {time,high,low,close}=row;
  if(![time,high,low,close].every(Number.isFinite)||time<=this.lastStamp||low>Math.min(row.open??close,close)||high<Math.max(row.open??close,close)||low<=0)throw Error('Invalid completed broker candle');
  this.lastStamp=time;this.rows.push({high,low});if(this.rows.length>this.period)this.rows.shift();
  if(this.rows.length<this.period)return null;
  const a=2/(this.period+1),upper=this.kind==='EMA'&&this.last?a*high+(1-a)*this.last.upper:this.rows.reduce((s,r)=>s+r.high,0)/this.period,lower=this.kind==='EMA'&&this.last?a*low+(1-a)*this.last.lower:this.rows.reduce((s,r)=>s+r.low,0)/this.period;
  this.last={timestamp:time,upper,lower,close,period:this.period,kind:this.kind};this.points.push(this.last);if(this.points.length>5000)this.points.shift();return this.last;
 }
}
const runtime=new Map(),mounts=new Set();
function runtimeKey(p){return [p.account,p.run_id,p.symbol,p.frame].join('|');}
function mergeBandPoint(points,p){
 let lo=0,hi=points.length;
 while(lo<hi){const mid=(lo+hi)>>1;if(points[mid].timestamp<p.timestamp)lo=mid+1;else hi=mid;}
 if(points[lo]?.timestamp===p.timestamp)points[lo]=p;else points.splice(lo,0,p);
}
function receive(payload){
 if(!payload.moving_bands?.length)return;
 const key=runtimeKey(payload),current=runtime.get(key)||new Map();
 for(const batch of payload.moving_bands){
  if(batch.underlying!==payload.symbol||batch.timeframe!==payload.frame)continue;
  for(const band of batch.bands||[]){
   if(!colors[band.kind]||!Number.isInteger(band.period)||band.period<1||band.period>500)continue;
   const id=band.kind+'|'+band.period,points=current.get(id)||[];
   for(const p of band.points||(band.value?[band.value]:[])){
    if(![p.timestamp,p.upper,p.lower].every(Number.isFinite)||p.upper<p.lower||p.lower<=0)continue;
    mergeBandPoint(points,p);
   }
   current.set(id,points.slice(-5000));
  }
 }
 runtime.set(key,current);
 for(const mount of mounts){if(mount.ownedKey===key)mount.set(null);else mount.refresh();}
}
function mount({pane,chart,series,getData,ownedKey}){
 const canvas=document.createElement('canvas'),legend=document.createElement('div');canvas.className='sp-ai-band-cloud';canvas.setAttribute('aria-hidden','true');
 Object.assign(canvas.style,{position:'absolute',inset:'0',width:'100%',height:'100%',pointerEvents:'none',zIndex:'2'});
 Object.assign(legend.style,{position:'absolute',bottom:'64px',left:'10px',maxWidth:'calc(100% - 100px)',display:'flex',gap:'10px',flexWrap:'wrap',font:'11px system-ui',pointerEvents:'none',zIndex:'3'});
 legend.setAttribute('aria-label','Moving average bands');pane.append(canvas,legend);
 let specs=[],signature='',states=new Map(),sourceFirst=null,sourceLastKey='',scheduled=0,disposed=false;
 const ctx=canvas.getContext('2d');
 function schedule(){if(!specs.length)return;if(!scheduled&&!disposed)scheduled=requestAnimationFrame(paint);}
 function refresh(){
  const data=getData();if(!data)return;
  const rows=data.rows||[];
  if(!ownedKey&&specs.length&&rows.length){
   const completed=data.completed||((r)=>!r.provisional);
   let end=rows.length-1;while(end>=0&&!completed(rows[end]))end--;
   const last=rows[end],first=rows[0]?.time,key=last?[last.time,last.open,last.high,last.low,last.close].join('|'):'';
   if(sourceFirst!==first||last&&[...states.values()].some(s=>s.lastStamp>last.time||s.lastStamp===last.time&&sourceLastKey&&key!==sourceLastKey)){states=new Map(specs.map(s=>[s.kind,new BandState(s.kind,s.period)]));sourceFirst=first;sourceLastKey='';}
   if(key!==sourceLastKey){
    for(const spec of specs){
     const state=states.get(spec.kind);let low=0,high=end+1;
     while(low<high){const mid=(low+high)>>1;if(rows[mid].time<=state.lastStamp)low=mid+1;else high=mid;}
     for(let i=low;i<=end;i++){try{state.push(rows[i]);}catch{states.set(spec.kind,new BandState(spec.kind,spec.period));break;}}
    }
    sourceLastKey=key;
   }
  }
  schedule();
 }
 function pointsFor(spec){return ownedKey?(runtime.get(ownedKey)?.get(spec.kind+'|'+spec.period)||[]):(states.get(spec.kind)?.points||[]);}
 function paint(){
  scheduled=0;if(disposed||!ctx||!canvas.isConnected)return;
  const data=getData(),size=chart.paneSize(),ratio=devicePixelRatio||1;
  const width=size.width,height=size.height;
  if(canvas.width!==Math.round(width*ratio))canvas.width=Math.round(width*ratio);
  if(canvas.height!==Math.round(height*ratio))canvas.height=Math.round(height*ratio);
  canvas.style.width=width+'px';canvas.style.height=height+'px';ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,width,height);
  legend.replaceChildren();
  const bars=data?.bars||[],range=chart.timeScale().getVisibleLogicalRange(),start=Math.max(0,Math.floor(range?.from??0)-2),end=Math.min(bars.length,Math.ceil(range?.to??bars.length)+3);
  for(const spec of specs){
   const points=pointsFor(spec),path=[];let index=0;
   for(let i=start;i<end;i++){
    const bar=bars[i],sourceTime=bar.sourceTime??bar.time;
    while(index+1<points.length&&points[index+1].timestamp<=sourceTime)index++;
    const p=points[index];if(!p||p.timestamp>sourceTime)continue;
    const x=chart.timeScale().timeToCoordinate(bar.time),upper=series.priceToCoordinate(p.upper),lower=series.priceToCoordinate(p.lower);
    if([x,upper,lower].every(v=>v!==null&&Number.isFinite(v)))path.push({x,upper,lower,color:cloudColor(spec.kind,p)});
   }
   const color=cloudColor(spec.kind,points.at(-1));
   for(let i=1;i<path.length;i++){
    const pair=[path[i-1],path[i]],shade=path[i].color;
    const top=Math.min(...pair.map(p=>p.upper)),bottom=Math.max(...pair.map(p=>p.lower)),gradient=ctx.createLinearGradient(0,top,0,Math.max(top+1,bottom));
    gradient.addColorStop(0,shade+'50');gradient.addColorStop(1,shade+'16');
    ctx.beginPath();ctx.moveTo(pair[0].x,pair[0].upper);ctx.lineTo(pair[1].x,pair[1].upper);ctx.lineTo(pair[1].x,pair[1].lower);ctx.lineTo(pair[0].x,pair[0].lower);ctx.closePath();ctx.fillStyle=gradient;ctx.fill();
    ctx.strokeStyle=shade+'c0';ctx.lineWidth=1;
    for(const edge of ['upper','lower']){ctx.beginPath();ctx.moveTo(pair[0].x,pair[0][edge]);ctx.lineTo(pair[1].x,pair[1][edge]);ctx.stroke();}
   }
   const label=document.createElement('span'),latest=points.at(-1);
   label.textContent=spec.kind+' '+spec.period+(latest?' · H '+latest.upper.toFixed(2)+' / L '+latest.lower.toFixed(2):' · waiting for completed candles');label.style.color=color;Object.assign(label.style,{background:'rgba(127,127,127,.10)',border:'1px solid '+color+'40',borderRadius:'4px',padding:'3px 6px'});legend.append(label);
  }
 }
 const observer=new ResizeObserver(schedule);observer.observe(pane);
 chart.timeScale().subscribeVisibleLogicalRangeChange(schedule);chart.timeScale().subscribeSizeChange(schedule);chart.subscribeCrosshairMove(schedule);
 const api={ownedKey,refresh,setOwnedKey(next){if(next===ownedKey)return;ownedKey=next;api.ownedKey=next;signature='';},set(next){if(ownedKey)next=[...(runtime.get(ownedKey)?.keys()||[])].map(k=>({kind:k.split('|')[0],period:Number(k.split('|')[1])}));const valid=(next||[]).filter(s=>colors[s.kind]&&Number.isInteger(s.period)&&s.period>=1&&s.period<=500);const key=JSON.stringify(valid);if(key!==signature){signature=key;specs=valid;states=new Map(specs.map(s=>[s.kind,new BandState(s.kind,s.period)]));sourceFirst=null;sourceLastKey='';}canvas.style.display=specs.length?'block':'none';legend.style.display=specs.length?'flex':'none';refresh();},dispose(){disposed=true;observer.disconnect();chart.timeScale().unsubscribeVisibleLogicalRangeChange(schedule);chart.timeScale().unsubscribeSizeChange(schedule);chart.unsubscribeCrosshairMove(schedule);if(scheduled)cancelAnimationFrame(scheduled);mounts.delete(api);canvas.remove();legend.remove();}};
 mounts.add(api);return api;
}
root.RenkoAiBands={BandState,receive,mount,runtimeKey};if(typeof module!=='undefined')module.exports={BandState,runtimeKey,cloudColor,mergeBandPoint};
})(typeof window==='undefined'?globalThis:window);
