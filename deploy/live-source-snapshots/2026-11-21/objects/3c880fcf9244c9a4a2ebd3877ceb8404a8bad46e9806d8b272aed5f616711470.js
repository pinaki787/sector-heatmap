/* Account-bound chart order integration. No automatic order submission. */
(function(root){
  'use strict';
  function mount(host, hooks) {
    let source, draft, series, viewport, paneHeight, lines=[], axisPrimitive, picking, ticket, brokerState;
    const prices=root.SectorPulseChartTradePrices;
    const buttons=document.createElement('div');
    buttons.className='sp-chart-trade-actions';
    buttons.setAttribute('role','group');buttons.setAttribute('aria-label','Chart trading');
    buttons.innerHTML='<button type="button" data-trade-side="SELL">SELL</button><button type="button" data-trade-side="BUY">BUY</button>';
    host.querySelector('.sp-chart-quote-line').append(buttons);
    function clearLines(){
      if(series) for(const line of lines) {try{series.removePriceLine(line);}catch{}}
      if(series && axisPrimitive){try{series.detachPrimitive(axisPrimitive);}catch{}}
      lines=[];axisPrimitive=undefined;
    }
    function markerState(key){
      if(!brokerState)return 'DRAFT';
      const status=String(brokerState.status||'');
      if(['CLOSED','CANCELLED','REJECTED','EXPIRED'].includes(status))return status;
      if(status==='REVIEW_REQUIRED')return 'REVIEW REQUIRED';
      if(['WAITING_FOR_TRIGGER','TRIGGERED'].includes(status))
        return key==='entry'?'ARMED':'PLANNED';
      if(brokerState.protection_confirmed===true)return 'BROKER · PROTECTED';
      if(status==='ENTRY_PENDING')return 'BROKER · PENDING';
      return 'BROKER · VERIFY STATUS';
    }
    function paint(){
      clearLines();
      if(!series || !draft || ticket.element.hidden)return;
      const tickMode=Boolean(draft.price_tick && prices.precision(draft.price_tick)>2),axisViews=[];
      for(const [key,title,color] of [['entry','Entry','#2962ff'],['stop_loss','Stop loss','#f23645'],['target','Target','#089981']]) {
        const price=Number(draft[key]),caption=markerState(key)+' · '+title+(draft.exit_trigger_method==='mark_price'?' (Mark)':'');
        if(!Number.isFinite(price)||price<=0)continue;
        lines.push(series.createPriceLine({price,color,lineWidth:2,lineStyle:2,axisLabelVisible:!tickMode,title:caption}));
        const tickText=tickMode?prices.ticks(draft[key],draft.price_tick):'';
        if(tickMode)axisViews.push({
          text:markerState(key)+' '+({entry:'E',stop_loss:'SL',target:'TP'}[key])+' '+tickText+'t'+(draft.exit_trigger_method==='mark_price'?' M':''),
          price,color
        });
      }
      if(axisViews.length && series.attachPrimitive){
        const owner=series;
        axisPrimitive={paneViews:()=>[{zOrder:()=> 'top',renderer:()=>({draw(target){
          target.useMediaCoordinateSpace(({context,mediaSize})=>{
            context.save();context.font='600 11px Inter,system-ui,sans-serif';context.textBaseline='middle';
            const labels=axisViews.map(row=>({...row,y:owner.priceToCoordinate(row.price)}))
              .filter(row=>Number.isFinite(row.y)&&row.y>=0&&row.y<=mediaSize.height).sort((a,b)=>a.y-b.y);
            let previous=-20;
            for(const row of labels){row.displayY=Math.max(10,row.y,previous+22);previous=row.displayY;}
            let next=mediaSize.height+12;
            for(const row of labels.toReversed()){row.displayY=Math.min(row.displayY,next-22);next=row.displayY;}
            for(const row of labels){
              const width=Math.min(mediaSize.width-8,context.measureText(row.text).width+12),x=mediaSize.width-width-4;
              context.fillStyle=row.color;context.fillRect(x,row.displayY-10,width,20);
              if(Math.abs(row.displayY-row.y)>1){context.strokeStyle=row.color;context.lineWidth=1;context.beginPath();
                context.moveTo(mediaSize.width-3,row.y);context.lineTo(mediaSize.width-3,row.displayY);context.stroke();}
              context.fillStyle='#ffffff';context.fillText(row.text,x+6,row.displayY,width-12);
            }
            context.restore();
          });
        }})}]};series.attachPrimitive(axisPrimitive);
      }
    }
    function cancelPick(){ticket?.element.classList.remove('sp-trade-picking');picking=undefined;hooks.instruction?.('');if(ticket?.element.hidden){draft=undefined;clearLines();}}
    async function request(action,payload){
      if(hooks.replaying?.())throw Error('Exit bar replay before reviewing or placing a live chart order.');
      if(!source?.prefix || payload.account_id!==source.account_id || payload.broker!==source.broker)throw Error('The chart broker account changed. Review a new order.');
      const response=await fetch(source.prefix+'/api/chart-workspace/trading/'+action,{
        method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':root.SectorPulseWorkspace?.csrf||''},
        body:JSON.stringify(payload),credentials:'same-origin',signal:AbortSignal.timeout(20000)
      });
      const result=await response.json();
      if(!response.ok)throw Error(result.error||'The broker order request failed.');
      return result;
    }
    ticket=root.SectorPulseChartTradeTicket.mount(host.querySelector('.sp-chart-content'),{
      prepare:payload=>request('prepare',payload),arm:payload=>request('arm',payload),status:payload=>request('status',payload),
      cancelCondition:payload=>request('cancel-condition',payload),
      onChange:value=>{draft=value;paint();},
      onStatus:result=>{brokerState=result;paint();hooks.instruction?.(result.message||'');},
      pickLevel:key=>{ticket.element.classList.add('sp-trade-picking');picking=key;hooks.cancelDrawing?.();hooks.instruction?.('Click the chart to mark '+key.replace('_',' ')+'. Escape cancels.');},
      cancelPick,
      onSubmitted:result=>{brokerState=result;paint();picking=undefined;hooks.instruction?.(result.message||'Check broker order status before placing another order.');}
    });
    function refreshButtons(){
      const enabled=source?.available===true && source?.permitted===true && !hooks.replaying?.();
      for(const button of buttons.querySelectorAll('button')) {
        button.disabled=!enabled;
        button.title=enabled?'Create a broker order preview with marked chart levels':source?.reason||'Chart order execution is not active for this source.';
      }
    }
    buttons.addEventListener('click',event=>{
      const side=event.target.closest('[data-trade-side]')?.dataset.tradeSide;
      if(!side || !source || event.target.disabled)return;
      brokerState=undefined;ticket.open({...source,side,symbol:hooks.symbol(),price_tick:String(hooks.tick()),products:source.products||['INTRADAY','CNC','MARGIN','MTF']});
    });
    host.addEventListener('keydown',event=>{
      if(event.key==='Escape'&&picking){event.preventDefault();event.stopPropagation();cancelPick();}
    },true);
    const stage=host.querySelector('.sp-chart-stage');
    let drag;
    function release(){
      if(!drag)return;
      const id=drag.id;drag=undefined;
      if(stage?.hasPointerCapture?.(id))stage.releasePointerCapture(id);
      hooks.instruction?.('');
    }
    stage?.addEventListener('pointerdown',event=>{
      if(event.button!==0||picking||!draft||!ticket.editable()||!series)return;
      const rect=(viewport||stage).getBoundingClientRect(),y=event.clientY-rect.top;
      const hit=['entry','stop_loss','target'].map(key=>({key,y:series.priceToCoordinate(Number(draft[key]))}))
        .filter(item=>Number.isFinite(item.y)&&Math.abs(item.y-y)<=7)
        .sort((a,b)=>Math.abs(a.y-y)-Math.abs(b.y-y))[0];
      if(!hit)return;
      event.preventDefault();event.stopImmediatePropagation();
      drag={id:event.pointerId,key:hit.key};
      stage.setPointerCapture?.(event.pointerId);
      hooks.instruction?.('Drag '+hit.key.replace('_',' ')+'. Review the broker order again after changing a level.');
    },true);
    stage?.addEventListener('pointermove',event=>{
      if(!drag||event.pointerId!==drag.id||!ticket.editable())return;
      event.preventDefault();event.stopImmediatePropagation();
      const raw=series.coordinateToPrice(event.clientY-(viewport||stage).getBoundingClientRect().top),tick=Number(hooks.tick());
      if(Number.isFinite(raw)&&raw>0&&Number.isFinite(tick)&&tick>0)
        ticket.setLevel(drag.key,prices.snap(String(raw),String(tick)));
    },true);
    for(const name of ['pointerup','pointercancel','lostpointercapture'])stage?.addEventListener(name,event=>{
      if(!drag||event.pointerId!==drag.id)return;
      event.preventDefault();event.stopImmediatePropagation();release();
    },true);
    return {
      source(value){release();ticket.invalidateSource();draft=undefined;brokerState=undefined;clearLines();source=value;refreshButtons();},
      invalidate(){release();ticket.invalidateSource();draft=undefined;brokerState=undefined;clearLines();refreshButtons();},
      attach(next,element,height){clearLines();series=next;viewport=element;paneHeight=height;paint();refreshButtons();},
      pick(point){
        if(!picking)return false;
        if(!point || !series)return true;
        const price=series.coordinateToPrice(point.y),tick=Number(hooks.tick());
        if(!Number.isFinite(price)||price<=0||!Number.isFinite(tick)||tick<=0)return true;
        const exact=prices.snap(String(price),String(tick));
        ticket.setLevel(picking,exact);cancelPick();return true;
      },
      destroy(){clearLines();ticket.destroy();buttons.remove();}
    };
  }
  root.SectorPulseChartTrading={mount};
})(typeof window==='undefined'?globalThis:window);
