/* Position text outside the candle plot; consumes existing validated line data only. */
(function(root){'use strict';
function view(current){
 if(!current)return null;
 const money=/ gross$/.test(current.title||'');
 return {label:money?'Gross P&L':'Position move',value:money?current.title.replace(/ gross$/,''):current.title,color:current.color};
}
function lineOptions(current){return current?{...current,title:''}:null;}
function mount(stage,{key,store=root.localStorage}={}){
 const doc=stage.ownerDocument,strip=doc.createElement('div');strip.className='sp-ai-position-strip';strip.hidden=true;
 strip.setAttribute('aria-label','Position P&L');
 const label=doc.createElement('span'),value=doc.createElement('output'),toggle=doc.createElement('button');
 label.className='sp-ai-position-label';value.className='sp-ai-position-value';value.setAttribute('aria-label','Current position result');
 toggle.type='button';toggle.className='sp-ai-position-toggle';
 strip.append(label,value,toggle);(stage.parentElement?.querySelector('.sp-chart-legend-anchor')||stage).before(strip);
 let hidden=false,last=null,paintedLast=null,paintedHidden;
 try{hidden=store?.getItem(key)==='hidden';}catch{}
 const paint=()=>{
  if(paintedHidden===hidden&&!!paintedLast===!!last&&paintedLast?.label===last?.label&&paintedLast?.value===last?.value&&paintedLast?.color===last?.color)return;
  paintedLast=last;paintedHidden=hidden;
  strip.hidden=!last;label.hidden=value.hidden=hidden;
  toggle.textContent=hidden?'Show P&L':'Hide P&L';toggle.setAttribute('aria-expanded',String(!hidden));
  toggle.setAttribute('aria-label',hidden?'Show position P&L':'Hide position P&L');
  if(last){label.textContent=last.label;value.textContent=last.value;value.style.color=last.color;}
 };
 toggle.addEventListener('click',()=>{hidden=!hidden;try{store?.setItem(key,hidden?'hidden':'shown');}catch{}paint();});
 return {update(current){last=view(current);paint();},element:strip,destroy(){strip.remove();}};
}
root.RenkoAiPositionStrip={view,lineOptions,mount};
if(typeof module!=='undefined')module.exports={view,lineOptions,mount};
})(typeof window==='undefined'?globalThis:window);
