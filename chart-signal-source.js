/* Observe the chart's actual indicator output. No network or order operations. */
(function(root){
  'use strict';
  function create({environment=root,ownerScope=null}={}){
    const env=environment;
    const studies=new WeakMap(),latest=new Map(),peers=new Map();
    let sequence=0,instanceCounter=0;
    const generation=env.crypto?.randomUUID?.()||String(Date.now())+'-'+Math.random();
    const now=()=>Date.now()/1000;
    let channel=null,heartbeat=null,closed=false,scopeRetry=null,scopePending=false;
    let discoveryState='CHECKING_OWNER';
    function emit(snapshot){
      if(env.dispatchEvent&&env.CustomEvent)
        env.dispatchEvent(new env.CustomEvent('sector-pulse-chart-signal-observation',{detail:snapshot}));
    }
    function discoveryChanged(){
      if(env.dispatchEvent&&env.CustomEvent)
        env.dispatchEvent(new env.CustomEvent('sector-pulse-chart-discovery-changed'));
    }
    function post(kind,extra={}){
      if(closed||!channel)return;
      try{channel.postMessage({version:1,kind,sender:generation,...extra});}catch(_){}
    }
    function valid(snapshot,sender){
      if(!snapshot||snapshot.version!==1||snapshot.generation!==sender||
          typeof snapshot.instance!=='string'||!snapshot.instance.startsWith(sender+':')||
          !Number.isInteger(snapshot.sequence)||snapshot.sequence<1||
          snapshot.observationOnly!==true||snapshot.executionEnabled!==false)return false;
      for(const name of ['symbol','interval','chartType','chartPrefix','studyName','dataBroker','dataAccount'])
        if(typeof snapshot[name]!=='string'||!snapshot[name]||snapshot[name].length>300)return false;
      if(typeof snapshot.source!=='string'||!snapshot.source.length||snapshot.source.length>200000||
          !snapshot.inputs||typeof snapshot.inputs!=='object'||Array.isArray(snapshot.inputs)||
          !Array.isArray(snapshot.flags)||snapshot.flags.length>20000||
          !Number.isFinite(snapshot.receivedAt)||snapshot.receivedAt>now()+5||
          !snapshot.confirmedThrough||!Number.isFinite(snapshot.confirmedThrough.time))return false;
      try{return JSON.stringify(snapshot).length<=1000000&&JSON.stringify(snapshot.inputs).length<=20000;}
      catch(_){return false;}
    }
    function forget(study){
      const instance=study&&studies.get(study);
      if(instance&&latest.delete(instance)){post('withdraw',{instance});discoveryChanged();}
    }
    function dispose(){
      if(closed)return;
      post('disconnect');closed=true;
      if(heartbeat!==null)env.clearInterval?.(heartbeat);
      if(scopeRetry!==null)env.clearInterval?.(scopeRetry);
      channel?.close();peers.clear();discoveryState='STOPPED';discoveryChanged();
    }
    function connectPeers(scope){
      if(closed||channel||!env.document||typeof env.BroadcastChannel!=='function'||
          typeof scope!=='string'||!/^[a-f0-9]{64}$/.test(scope))return;
      try{
        // BroadcastChannel is restricted by the browser to this same origin
        // and browser profile. It never connects the Mac to Ubuntu.
        channel=new env.BroadcastChannel('sector-pulse-chart-observations-v1-'+scope);
        discoveryState='CONNECTED';
        if(scopeRetry!==null){env.clearInterval?.(scopeRetry);scopeRetry=null;}
        discoveryChanged();
        channel.onmessage=event=>{
          const message=event.data;
          if(!message||message.version!==1||typeof message.sender!=='string'||
              message.sender===generation||message.sender.length>100)return;
          if(message.kind==='request'){
            for(const snapshot of latest.values())post('observation',{snapshot});
          }else if(message.kind==='observation'&&valid(message.snapshot,message.sender)){
            const snapshot=JSON.parse(JSON.stringify(message.snapshot)),key=snapshot.instance;
            const previous=peers.get(key);
            if(previous&&snapshot.sequence<previous.snapshot.sequence)return;
            if(previous&&snapshot.sequence===previous.snapshot.sequence&&
                JSON.stringify(snapshot)!==JSON.stringify(previous.snapshot))return;
            const changed=!previous||snapshot.sequence!==previous.snapshot.sequence;
            peers.set(key,{sender:message.sender,snapshot,seen:now()});
            if(peers.size>40)peers.delete(peers.keys().next().value);
            // Preserve original publication/provider time and sequence.
            // A heartbeat renews discovery only, never signal freshness.
            if(changed)emit(snapshot);
          }else if(message.kind==='withdraw'){
            const previous=peers.get(message.instance);
            if(previous?.sender===message.sender){peers.delete(message.instance);discoveryChanged();}
          }else if(message.kind==='disconnect'){
            for(const [key,value] of peers)if(value.sender===message.sender)peers.delete(key);
            discoveryChanged();
          }
        };
        let checkedAt=now();
        heartbeat=env.setInterval?.(()=>{
          let expired=false;
          for(const [key,value] of peers)if(now()-value.seen>90){peers.delete(key);expired=true;}
          if(expired)discoveryChanged();
          for(const snapshot of latest.values())post('observation',{snapshot});
          post('request');
          if(!ownerScope&&now()-checkedAt>=30){
            checkedAt=now();
            authenticatedScope().then(current=>{if(current!==scope)dispose();}).catch(dispose);
          }
        },5000)??null;
        env.addEventListener?.('pagehide',dispose,{once:true});
        post('request');
        for(const snapshot of latest.values())post('observation',{snapshot});
      }catch(_){channel?.close();channel=null;discoveryState='UNAVAILABLE';discoveryChanged();}
    }
    async function authenticatedScope(){
      if(typeof env.fetch!=='function')return null;
      const response=await env.fetch('/api/stoxkart-browser/context',{cache:'no-store',credentials:'same-origin'});
      if(!response.ok)return null;
      const data=await response.json();
      // Discovery carries observations only. Normal feature admission stays
      // in the setup/API. Retain the same owner's existing exit observations
      // if normal section access changes; backend frozen-run checks govern it.
      return data.chart_owner_scope;
    }
    async function initializeScope(){
      if(closed||channel||scopePending)return;
      scopePending=true;
      try{
        const scope=await authenticatedScope();
        if(closed)return;
        if(typeof scope==='string'&&/^[a-f0-9]{64}$/.test(scope))connectPeers(scope);
        else {discoveryState='OWNER_UNAVAILABLE';discoveryChanged();}
      }catch(_){if(!closed){discoveryState='OWNER_UNAVAILABLE';discoveryChanged();}}
      finally{scopePending=false;}
    }
    if(ownerScope)connectPeers(ownerScope);
    else if(env.document){
      // A transient context failure during page startup must not permanently
      // disable peer discovery. Never reconnect after an owner change: dispose
      // remains terminal and the user must reload the owning chart.
      scopeRetry=env.setInterval?.(()=>{void initializeScope();},10000)??null;
      void initializeScope();
    }
    function publish(study,result,context){
      if(!study||!result||context.replay||context.hidden||result.replayThrough!=null){forget(study);return null;}
      let instance=studies.get(study);
      if(!instance){instance=generation+':'+(++instanceCounter);studies.set(study,instance);}
      const plots=Object.values(result.plots||{});
      function one(title){
        const matches=plots.filter(p=>p&&p.title===title);
        return matches.length===1&&Array.isArray(matches[0].data)?matches[0].data:null;
      }
      const buys=one('Confirmed BUY flag'),sells=one('Confirmed SELL flag');
      if(!buys||!sells){forget(study);return null;}
      const synthetic=Array.isArray(result.bricks);
      const bars=synthetic?result.bricks:(context.bars||[]);
      // Pine worker plot.time is milliseconds. Chart geometry uses seconds.
      // Synthetic hosts additionally require the exact worker bar index:
      // several distinct Renko bricks may share a source candle timestamp.
      const indexed=bars.map((bar,index)=>({...bar,...(synthetic?{barIndex:index}:{})}));
      const confirmedBars=indexed.filter(b=>!b.provisional&&!b.historyOnly);
      const through=confirmedBars.at(-1);
      if(!through){forget(study);return null;}
      const byTime=new Map();
      if(!synthetic)for(const bar of confirmedBars){
        if(byTime.has(bar.time))byTime.set(bar.time,null);
        else byTime.set(bar.time,bar);
      }
      function chartBar(point){
        if(!point||!Number.isFinite(point.time))return null;
        if(!synthetic)return byTime.get(point.time/1000)||null;
        if(!Number.isInteger(point.barIndex))return null;
        const bar=indexed[point.barIndex];
        if(!bar||bar.provisional||bar.historyOnly||
            (bar.sourceTime??bar.time)*1000!==point.time)return null;
        return bar;
      }
      const key=bar=>String(bar.time)+':'+String(bar.barIndex??'');
      function mapped(points){
        const values=new Map();
        for(const point of points){
          const bar=chartBar(point);if(!bar)continue;
          const id=key(bar);
          // Duplicate evidence is ambiguous, even when its value agrees.
          if(values.has(id))values.set(id,null);
          else values.set(id,{bar,value:point.value});
        }
        return values;
      }
      const buyMap=mapped(buys),sellMap=mapped(sells),flags=[];
      for(const [id,buy] of buyMap){
        const sell=sellMap.get(id);
        if(!buy||!sell||![0,1].includes(buy.value)||![0,1].includes(sell.value))continue;
        if(buy.value+sell.value!==1)continue;
        const bar=buy.bar;
        flags.push({time:bar.time,barIndex:bar.barIndex??null,
                    sourceTime:bar.sourceTime??bar.time,side:buy.value===1?'BUY':'SELL'});
      }
      const snapshot={version:1,generation,instance,sequence:++sequence,
        symbol:result.symbol,interval:result.interval,chartType:result.chartType,
        chartPrefix:result.chartPrefix,studyName:study.name,dataBroker:context.dataBroker,dataAccount:context.dataAccount,
        source:result.source,inputs:JSON.parse(JSON.stringify(study.inputs||{})),
        receivedAt:Date.now()/1000,
        confirmedThrough:{time:through.time,barIndex:through.barIndex??null,sourceTime:through.sourceTime??through.time},
        flags,
        observationOnly:true,executionEnabled:false};
      latest.set(instance,snapshot);
      // Keep the most recent applied studies only, not unbounded chart history.
      if(latest.size>40)latest.delete(latest.keys().next().value);
      emit(snapshot);
      post('observation',{snapshot});
      return snapshot;
    }
    return {publish,
      discoveryStatus:()=>({state:discoveryState,localCount:latest.size,peerCount:peers.size}),
      snapshots:()=>[...latest.values(),...[...peers.values()].filter(p=>now()-p.seen<=90).map(p=>p.snapshot)],
      tabLocation:instance=>latest.has(instance)?'This tab':peers.has(instance)?'Another tab':null,
      remove:forget,
      clear:()=>{for(const instance of latest.keys())post('withdraw',{instance});latest.clear();discoveryChanged();},
      dispose};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={create};
  else root.SectorPulseChartSignalSource=create();
})(typeof window!=='undefined'?window:globalThis);
