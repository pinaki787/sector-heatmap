/* Display-only V1 references embedded in AI Renko Supertrend. */
(function(root){'use strict';
const MARKER='AI_V1_REFERENCE_DISPLAY_20261127';
const RANGE_COLORS={X:'#7c3aed',R:'#b45309',M:'#0e7490',E:'#2563eb'};
const clone=value=>JSON.parse(JSON.stringify(value));
function referenceSource(source){
 const meta=String.raw`
ai_ref_bounds(string ai_kind) =>
    float ai_hi = na
    float ai_lo = na
    int ai_started = na
    int ai_published = na
    if ai_kind == "SC"
        ai_hi := not sc_missingFinal ? sc_lockedHigh : na
        ai_lo := not sc_missingFinal ? sc_lockedLow : na
        ai_started := sc_lastSource
        ai_published := sc_lockedClose
    else if ai_kind == "T1" or ai_kind == "T2"
        array<sc_SCReference> ai_targets = array.new<sc_SCReference>()
        array<int> ai_times = array.new<int>()
        for ai_item in sc_scArchive
            if not na(sc_scChainKey) and not na(ai_item.sc_visitedChain) and ai_item.sc_visitedChain == sc_scChainKey and ai_item.sc_opened != sc_lastSource and ai_item.sc_approach != 0 and not na(ai_item.sc_anchorAt)
                array.push(ai_targets, ai_item)
                array.push(ai_times, ai_item.sc_anchorAt)
        array<int> ai_order = array.sort_indices(ai_times, order.ascending)
        int ai_slot = (sc_scTargetPage-1)*2 + (ai_kind == "T1" ? 0 : 1)
        if ai_slot < array.size(ai_order)
            sc_SCReference ai_target = array.get(ai_targets, array.get(ai_order,ai_slot))
            ai_hi := ai_target.sc_hi
            ai_lo := ai_target.sc_lo
            ai_started := ai_target.sc_opened
            ai_published := ai_target.sc_closed
    else
        for ai_item in sc_rbSets
            bool ai_match = ai_kind == "LATEST" ? ai_item.sc_kind != "X" and ai_item.sc_published <= sc_chartEnd : ai_item.sc_kind == ai_kind and ai_item.sc_dayKey == sc_rbState.sc_key
            if ai_match and (na(ai_published) or ai_item.sc_published > ai_published)
                ai_hi := ai_item.sc_hi
                ai_lo := ai_item.sc_lo
                ai_started := ai_item.sc_started
                ai_published := ai_item.sc_published
    [ai_hi, ai_lo, ai_started, ai_published]
`;
 let result=source.replace('\n','\n// '+MARKER+'\n');
 result=result.replace('bool sc_gold = str.contains(sc_symbolText, "GOLD")','bool sc_gold = str.contains(sc_symbolText, "PAXG") or str.contains(sc_symbolText, "GOLD")');
 // RZ drawings are not displayed by this adapter; omit their optional history cap.
 result=result.replace(/,\s*calc_bars_count\s*=\s*10000/g,'');
 result+=meta;
 result=result.replace('bool rzLabels = input.bool(false,','bool rzLabels = input.bool(true,');
 for(const kind of ['SC','T1','T2','X','R','M','E','LATEST']){
  result+='\n[ai_'+kind+'_h,ai_'+kind+'_l,ai_'+kind+'_t,ai_'+kind+'_p]=ai_ref_bounds("'+kind+'")\n';
  for(const [field,varName] of [['H','h'],['L','l'],['T','t'],['P','p']])
   result+='plot(ai_'+kind+'_'+varName+', "AIREF_'+kind+'_'+field+'", display=display.none)\n';
 }
 result+='\nplot(sc_selected == "NSE/BSE" ? 1 : 0, "AIREF_INDIAN", display=display.none)\n';
 result+='\nplot(str.tonumber(rzSourceTf), "AIREF_RZ_TF", display=display.none)\n';
 result+=String.raw`
var label ai_archive_meta = na
if barstate.islast
    if not na(ai_archive_meta)
        label.delete(ai_archive_meta)
    string ai_archive_text = ""
    for ai_item in sc_scArchive
        if ai_item.sc_closed <= timenow
            ai_archive_text += str.tostring(ai_item.sc_opened) + "," + str.tostring(ai_item.sc_closed) + "," + str.tostring(ai_item.sc_hi, "#.################") + "," + str.tostring(ai_item.sc_lo, "#.################") + ";"
    ai_archive_meta := label.new(time, close, "AI_SC_ARCHIVE", xloc=xloc.bar_time, tooltip=ai_archive_text, color=color.new(color.white,100), textcolor=color.new(color.white,100))
`;
 result+=String.raw`
var label ai_target_meta = na
if barstate.islast
    if not na(ai_target_meta)
        label.delete(ai_target_meta)
    string ai_target_text = ""
    if array.size(targetSessions) > 0 and showTargets and targetMode != "OFF"
        TargetSession ai_rec = array.last(targetSessions)
        ai_target_text := str.tostring(ai_rec.hi, "#.################") + "," + str.tostring(ai_rec.lo, "#.################") + "," + str.tostring(ai_rec.key) + "," + str.tostring(targetCount) + "," + str.tostring(targetWidth) + "#"
        for ai_line in targetLines
            if line.get_x2(ai_line) >= ai_rec.key
                ai_target_text += str.tostring(line.get_x1(ai_line)) + "," + str.tostring(line.get_x2(ai_line)) + "," + str.tostring(line.get_y1(ai_line), "#.################") + ";"
        ai_target_text += "#"
        for ai_box in targetBoxes
            if box.get_right(ai_box) >= ai_rec.key
                ai_target_text += str.tostring(box.get_left(ai_box)) + "," + str.tostring(box.get_right(ai_box)) + "," + str.tostring(box.get_top(ai_box), "#.################") + "," + str.tostring(box.get_bottom(ai_box), "#.################") + ";"
    ai_target_meta := label.new(time, close, "AI_V1_TARGETS", xloc=xloc.bar_time, tooltip=ai_target_text, color=pendingColor, textcolor=upperColor)
`;
 result+=String.raw`
var label ai_liquidity_meta = na
if barstate.islast
    if not na(ai_liquidity_meta)
        label.delete(ai_liquidity_meta)
    string ai_liquidity_text = ""
    for ai_box in rzBoxes
        ai_liquidity_text += str.tostring(box.get_left(ai_box)) + "," + str.tostring(box.get_right(ai_box)) + "," + str.tostring(box.get_top(ai_box), "#.################") + "," + str.tostring(box.get_bottom(ai_box), "#.################") + ";"
    ai_liquidity_meta := label.new(time, close, "AI_V1_LIQUIDITY", xloc=xloc.bar_time, tooltip=ai_liquidity_text, color=color.new(color.white,100), textcolor=color.new(color.white,100))
`;
 return result;
}
function objects(plots,kind){return plots?.['__'+kind+'__']?.data?.at(-1)?.value?.filter(v=>!v._deleted)||[];}
function title(table){return table.cells?.[0]?.find(cell=>cell?.text)?.text||'';}
function plotValue(plots,name){
 const entry=Object.entries(plots||{}).find(([key,p])=>key===name||p.title===name||p.options?.title===name);
 const value=entry?.[1]?.data?.at(-1)?.value;
 return typeof value==='number'&&Number.isFinite(value)?value:null;
}
function keyForRow(caption){if(/^SC(?:\s|$)/.test(caption))return 'SC';if(/^[XRME](?:\s|$)/.test(caption))return caption[0];if(caption==='Latest red')return 'LATEST';return null;}
class Model{
 constructor(){this.tables=[];this.labels=[];this.ranges={lines:[],boxes:[]};this.sessions=[];this.shadowLabels=[];this.archive=[];this.previousDay={};this.neighbors={above:null,below:null};this.previousShadow=null;this.targets=[];this.liquidity=[];this.pins=new Map();this.labelPins=new Map();this.version=0;this.price=null;this.computations=0;}
 accept(plots,{asOf=Date.now()/1000}={}){
  const tables=objects(plots,'tables').filter(t=>['Levels · IST','SECTOR PULSE V1'].includes(title(t))).map(clone);
  const bounds={};
  for(const kind of ['SC','T1','T2','X','R','M','E','LATEST']){
   const high=plotValue(plots,'AIREF_'+kind+'_H'),low=plotValue(plots,'AIREF_'+kind+'_L'),start=plotValue(plots,'AIREF_'+kind+'_T');
   if(high!==null&&low!==null&&start!==null)bounds[kind]={high,low,start,published:plotValue(plots,'AIREF_'+kind+'_P')};
  }
  const indian=plotValue(plots,'AIREF_INDIAN')===1;
  for(const t of tables){
   if(indian&&title(t)==='Levels · IST'){
    const removed=t.cells.findIndex(row=>/^E(?:\s|$)/.test(row[0]?.text||''));
    if(removed>=0){
     t.cells.splice(removed,1);
     if(t.merges)t.merges=t.merges.filter(m=>!(m.startRow<=removed&&m.endRow>=removed)).map(m=>({...m,startRow:m.startRow>removed?m.startRow-1:m.startRow,endRow:m.endRow>removed?m.endRow-1:m.endRow}));
    }
   }

   t.aiTitle=title(t)==='SECTOR PULSE V1'?'Market View':'Levels · IST';
   if(t.aiTitle==='Market View'){
    t.cells[0][0].text='Market View';t.cells[0][1].text='';t.cells[0][1]._merged=true;
    t.bgcolor='#102235';t.frame_color='#2d4a63';t.frame_width=1;t.border_color='#243b50';t.border_width=1;
    for(let row=0;row<t.cells.length;row++)for(let col=0;col<t.cells[row].length;col++){
     const cell=t.cells[row][col];if(!cell)continue;
     cell.bgcolor=row===0?'#183b58':row%2?'#102235':'#142a3f';
     cell.text_size=row===0?12:col===0?10:11;
     cell.text_formatting=row===0||col===1?'bold':'';
     if(row===0)cell.text_color='#edf6ff';
     else if(col===0){cell.text_color='#a9bed1';cell.text=cell.text.charAt(0)+cell.text.slice(1).toLowerCase();}
    }
    t.merges=(t.merges||[]).filter(m=>m.startRow!==0);
    t.merges.push({startRow:0,endRow:0,startCol:0,endCol:1});
   }
   t.aiBounds={};
   let targetSlot=0;
   t.cells=t.cells.map((row,index)=>{
    const caption=row[0]?.text||'',code=caption.startsWith('→SC')?'T'+(++targetSlot):keyForRow(caption),b=bounds[code];
    if(!b)return row;
    const id=code+'|'+b.start;
    if(!this.pins.has(id))this.pins.set(id,{row:clone(row),bounds:b});
    const pin=this.pins.get(id);t.aiBounds[index]=pin.bounds;
    return clone(pin.row);
   });
  }
  const labels=objects(plots,'labels').filter(l=>/^[XRME]$/.test(l.text||'')&&['bt','bar_time'].includes(l.xloc)&&Number.isFinite(l.x)&&Number.isFinite(l.y)).map(l=>{
   const value={text:l.text,time:l.xloc==='bt'?l.x/1000:l.x,price:l.y,color:RANGE_COLORS[l.text]||l.color||'#b91c1c',tooltip:l.tooltip||'',knownAt:bounds[l.text]?.published/1000};
   const key=value.text+'|'+value.time;
   if(!this.labelPins.has(key))this.labelPins.set(key,value);
   return this.labelPins.get(key);
  });
  const ranges={};
  for(const [kind,coordinate] of [['lines','x1'],['boxes','left']]){
   ranges[kind]=objects(plots,kind).filter(o=>{
    if(!['bt','bar_time'].includes(o.xloc))return false;
    const time=o[coordinate]/(o.xloc==='bt'?1000:1);
    return labels.some(label=>{
     if(label.time!==time)return false;
     const b=bounds[label.text];if(!b)return false;
     const near=(a,c)=>Math.abs(a-c)<=Math.max(1,Math.abs(c))*1e-12;
     const middle=b.low+(b.high-b.low)*.5;
     return kind==='lines'
      ?near(o.y1,o.y2)&&[.44,.5,.56].some(r=>near(o.y1,b.low+(b.high-b.low)*r))
      :((near(o.top,b.high)&&near(o.bottom,middle))||(near(o.top,middle)&&near(o.bottom,b.low)));
    });
   }).map(o=>{const kind=labels.find(l=>l.time===o[coordinate]/(o.xloc==='bt'?1000:1))?.text;return {...clone(o),aiKind:kind,aiKnownAt:bounds[kind]?.published/1000};});
  }
  // SC drawings may share publication time and prices; retain only the XRME session extent.
  ranges.lines=ranges.lines.filter(line=>ranges.boxes.some(box=>box.xloc===line.xloc&&box.left===line.x1&&box.right===line.x2));
  const archiveText=objects(plots,'labels').find(l=>l.text==='AI_SC_ARCHIVE')?.tooltip||'';
  const archive=archiveText.split(';').filter(Boolean).map(row=>{
   const [start,closed,high,low]=row.split(',').map(Number);
   return {start:start/1000,closed:closed/1000,high,low};
  }).filter(r=>Object.values(r).every(Number.isFinite)&&r.start<r.closed&&r.low<=r.high);
  const previousDay={};
  for(const name of ['PDH','PDL']){
   const raw=objects(plots,'labels').find(l=>l.text===name&&Number.isFinite(l.y));
   if(raw)previousDay[name]={price:raw.y,tooltip:raw.tooltip||''};
  }
  const shadowLabels=objects(plots,'labels').filter(l=>/^SC(?: ·|$)/.test(l.text||'')&&String(l.tooltip||'').startsWith('Shadow Candle')&&['bt','bar_time'].includes(l.xloc)&&Number.isFinite(l.x)&&Number.isFinite(l.y)).map(clone);
  const targets=readTargetObjects(plots),liquidity=readLiquidityObjects(plots);
  const previousShadow=previousSessionRange(archive,asOf);
  const sessions=['R','M','E'].filter(kind=>bounds[kind]&&labels.some(l=>l.text===kind)).map(kind=>({kind,time:bounds[kind].start/1000}));
  const changed=JSON.stringify([tables,labels,ranges,sessions,shadowLabels,archive,previousDay,previousShadow,targets,liquidity])!==JSON.stringify([this.tables,this.labels,this.ranges,this.sessions,this.shadowLabels,this.archive,this.previousDay,this.previousShadow,this.targets,this.liquidity]);
  this.tables=tables;this.labels=labels;this.ranges=ranges;this.sessions=sessions;this.shadowLabels=shadowLabels;this.archive=archive;this.previousDay=previousDay;this.previousShadow=previousShadow;this.targets=targets;this.liquidity=liquidity;this.computations++;
  if(changed)this.version++;
  this.setPrice(this.price);
  return changed;
 }
 setPrice(price){
  if(typeof price!=='number'||!Number.isFinite(price)||price<=0)return false;
  this.price=price;let changed=false;
  const neighbors=nearestRanges(this.archive,price);
  if(JSON.stringify(neighbors)!==JSON.stringify(this.neighbors)){this.neighbors=neighbors;changed=true;}
  const states=[this.previousShadow,neighbors.above,neighbors.below].map(r=>r?(price>r.high?'Bullish':price<r.low?'Bearish':'In range'):'Unavailable').join('|');
  if(states!==this.shadowStateKey){this.shadowStateKey=states;changed=true;}


  for(const t of this.tables)for(const [index,b] of Object.entries(t.aiBounds||{})){
   const cell=t.cells[index]?.[4];if(!cell)continue;
   const state=price>b.high?'Bullish':price<b.low?'Bearish':'In range';
   const color=price>b.high?'#16a34a':price<b.low?'#dc2626':'#b4780a';
   if(cell.text!==state||cell.text_color!==color){cell.text=state;cell.text_color=color;changed=true;}
  }
  if(changed)this.version++;
  return changed;
 }
}
function referenceClock(bars,now,seconds=300){
 const last=bars.findLast(b=>!b.provisional&&!b.historyOnly&&b.time+seconds<=now);
 return [last?.time,Math.floor(now/300)].join('|');
}
function markerPoints(labels,bars,isRenko){
 const points=new Map();
 for(const l of labels){
  const bar=bars.find(b=>(isRenko?b.sourceTime:b.time)>=l.time);
  if(!bar)continue;
  const key=bar.time,previous=points.get(key);
  points.set(key,{time:key,value:Math.max(previous?.value||-Infinity,l.price),text:previous?previous.text+' / '+l.text:l.text,color:l.color,position:'aboveBar',shape:'arrowDown'});
 }
 return [...points.values()].sort((a,b)=>a.time-b.time);
}
function labelObjects(labels,bars,isRenko,fullText=true){
 const output=[],names={X:'First completed 5m candle',R:'First red 5m candle after X',M:'Six-candle midday blend (all colors)',E:'Six-candle evening blend'};
 const stamp=b=>isRenko?(b.sourceTime??b.source_time):b.time;
 const wrap=text=>{const lines=[];for(const word of text.split(/\s+/)){if(!lines.length||lines.at(-1).length+word.length>30)lines.push(word);else lines[lines.length-1]+=' '+word;}return lines.join('\n');};
 for(const label of labels){
  if(!bars.length||!Number.isFinite(stamp(bars[0]))||label.time<stamp(bars[0]))continue;
  let lo=0,hi=bars.length;while(lo<hi){const mid=(lo+hi)>>>1;if(stamp(bars[mid])<label.time)lo=mid+1;else hi=mid;}
  const bar=bars[lo];if(!bar)continue;
  const source=String(label.tooltip||'').split('\n').find(line=>line.startsWith('Source '));
  const title=String(label.tooltip||'').split('\n')[0]||names[label.text]||label.text;
  output.push({x:bar.time,xloc:'bar_time',y:label.price,text:fullText?label.text+' · '+wrap(title)+(source?'\n'+source:''):label.text,
   style:'style_label_down',nativeReferenceLabel:true,color:label.color,textcolor:'#ffffff',size:9,tooltip:label.tooltip,
   nativeKnownAt:label.knownAt,nativeOffsetY:label.text==='R'?(fullText?-62:-26):0});
 }
 return output;
}
function rangeObjects(ranges,bars,isRenko){
 const result={lines:[],boxes:[]};if(!bars.length)return result;
 const stamp=b=>b.sourceTime??b.source_time??b.time;
 const map=time=>{
  if(!isRenko)return time;
  let lo=0,hi=bars.length;while(lo<hi){const m=(lo+hi)>>>1;if(stamp(bars[m])<time)lo=m+1;else hi=m;}
  return bars[Math.min(lo,bars.length-1)].time;
 };
 for(const kind of ['lines','boxes'])for(const raw of ranges[kind]||[]){
  const item={...raw,xloc:'bar_time',nativeKnownAt:raw.aiKnownAt},divisor=raw.xloc==='bt'?1000:1;
  const coordinates=kind==='lines'?['x1','x2']:['left','right'];
  if(!coordinates.every(k=>Number.isFinite(raw[k])))continue;
  const begin=raw[coordinates[0]]/divisor,end=raw[coordinates[1]]/divisor;
  if(end<(isRenko?stamp(bars[0]):bars[0].time))continue;
  for(const k of coordinates)item[k]=map(raw[k]/divisor);
  const tint=RANGE_COLORS[raw.aiKind];
  if(tint){
   if(kind==='lines'){item.color=tint;item.style='style_dashed';item.width=1;}
   else{item.border_color=tint;item.border_width=1;item.border_style='style_dotted';item.bgcolor=tint+'12';}
  }
  result[kind].push(item);
 }
 return result;
}
function nearestRanges(archive,price){
 let above=null,below=null;
 if(!Number.isFinite(price))return {above,below};
 for(const row of archive){
  if(row.low>price&&(!above||row.low<above.low||(row.low===above.low&&row.closed>above.closed)))above=row;
  if(row.high<price&&(!below||row.high>below.high||(row.high===below.high&&row.closed>below.closed)))below=row;
 }
 return {above,below};
}
const shadowDateFormats=new Map();
function shadowSourceDate(time,zone='Asia/Kolkata'){
 if(!Number.isFinite(time))return '';
 if(!shadowDateFormats.has(zone))shadowDateFormats.set(zone,new Intl.DateTimeFormat('en-GB',{timeZone:zone,day:'numeric',month:'short'}));
 return shadowDateFormats.get(zone).format(time*1000);
}
function neighborObjects(neighbors,bars,zone='Asia/Kolkata'){
 const result={labels:[],lines:[],boxes:[]};
 if(!bars.length)return result;
 const first=bars[0].time,last=bars.at(-1).time;
 const format=n=>n.toLocaleString('en-IN',{maximumFractionDigits:2});
 const date=new Intl.DateTimeFormat('en-GB',{timeZone:zone,day:'2-digit',month:'short'});
 for(const side of ['above','below']){
  const row=neighbors[side];
  if(!row)continue;
  const color=side==='above'?'#6d28d9':'#0369a1';
  const tooltip='Confirmed Shadow Candle '+side+' price\nSource '+date.format(row.start*1000)+(zone==='Asia/Kolkata'?' IST':' '+zone)+'\nHigh '+format(row.high)+' · Low '+format(row.low);
  result.boxes.push({left:first,right:last,top:row.high,bottom:row.low,xloc:'bar_time',border_color:color,border_width:1,border_style:'style_dashed',bgcolor:color+'12'});
  for(const ratio of [0,.44,.5,.56,1]){
   const price=row.low+(row.high-row.low)*ratio;
   result.lines.push({xloc:'bar_time',x1:first,x2:last,y1:price,y2:price,color,width:ratio===.5?2:1,style:'style_dashed'});
  }
  result.labels.push({x:last,xloc:'bar_time',y:row.low+(row.high-row.low)*.5,nativeShadowLabel:true,nativeShadowOnLine:true,nativeNeighborSide:side,nativeShadowId:side==='above'?'SC2':'SC3',nativeBandSource:true,
   text:(side==='above'?'SC2':'SC3')+' · '+shadowSourceDate(row.start,zone),
   style:'style_label_left',color,textcolor:'#ffffff',size:11,text_formatting:'bold',tooltip});
 }
 return result;
}
function previousSessionRange(archive,now){
 const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'});
 const key=stamp=>{const p=Object.fromEntries(date.formatToParts(stamp*1000).map(p=>[p.type,p.value]));return p.year+p.month+p.day;},today=key(now);
 let result=null;
 for(const row of archive)if(row.closed<=now&&key(row.start)<today&&(!result||row.closed>result.closed))result=row;
 return result;
}
function previousShadowObjects(row,bars,isRenko=false,zone='Asia/Kolkata'){
 if(!row||!bars.length)return {labels:[],lines:[],boxes:[]};
 const result=neighborObjects({above:row,below:null},bars,zone);
 result.labels=result.labels.filter(l=>!l.nativeShadowUnavailable).map(l=>({...l,nativeNeighborSide:'previous',nativeShadowId:'SC1',nativeShadowOnLine:true,y:row.low+(row.high-row.low)*.5,text:'SC1 · '+shadowSourceDate(row.start,zone),color:'#1d4ed8',tooltip:'Previous completed trading-day Shadow Candle\n'+l.tooltip}));
 result.lines=result.lines.map(line=>({...line,color:'#1d4ed8',style:'style_solid'}));
 result.boxes=result.boxes.map(box=>({...box,border_color:'#1d4ed8',border_style:'style_solid',border_width:2,bgcolor:'#1d4ed814'}));
 const stamp=bar=>isRenko?(bar.sourceTime??bar.source_time):bar.time;
 const map=time=>{
  if(!isRenko)return time;
  let lo=0,hi=bars.length;while(lo<hi){const m=(lo+hi)>>>1;if(stamp(bars[m])<time)lo=m+1;else hi=m;}
  return bars[Math.min(lo,bars.length-1)].time;
 };
 if(row.closed>=stamp(bars[0])&&row.start<=stamp(bars.at(-1))){
  result.boxes.push({left:map(row.start),right:map(row.closed),top:row.high,bottom:row.low,xloc:'bar_time',border_color:'#1e40af',border_width:3,border_style:'style_solid',bgcolor:'#2563eb55'});
  const clock=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  result.labels[0]={...result.labels[0],tooltip:result.labels[0].tooltip+'\nSource '+clock.format(row.start*1000)+'–'+clock.format(row.closed*1000)+' IST'};
 }
 return result;
}
function readTargetObjects(plots){
 const meta=objects(plots,'labels').find(l=>l.text==='AI_V1_TARGETS');
 const text=meta?.tooltip||'';
 if(!text)return [];
 const [header,lineText,boxText]=text.split('#');
 const [high,low,key,count,width]=header.split(',').map(Number),span=high-low;
 if(![high,low,key,count,width].every(Number.isFinite)||!(span>0))return [];
 const rows=text=>String(text||'').split(';').filter(Boolean).map(row=>row.split(',').map(Number)).filter(row=>row.every(Number.isFinite));
 const lineKeys=rows(lineText),boxKeys=rows(boxText),targets=new Map();
 const near=(a,b)=>Math.abs(a-b)<=Math.max(1,Math.abs(b))*1e-12;
 for(const raw of objects(plots,'lines')){
  if(raw.xloc!=='bt'||raw.width!==width||!lineKeys.some(k=>k[0]===raw.x1&&k[1]===raw.x2&&near(k[2],raw.y1)&&near(raw.y1,raw.y2)))continue;
  const direction=raw.y1>high?'BULL':raw.y1<low?'BEAR':null;
  if(!direction)continue;
  const multiple=direction==='BULL'?(raw.y1-high)/span:(low-raw.y1)/span,n=Math.round(multiple);
  if(n<1||!Number.isSafeInteger(n)||!near(multiple,n))continue;
  const id=direction+n;
  if(!targets.has(id))targets.set(id,{direction,n,price:raw.y1,span,source:key/1000,lines:[],boxes:[]});
  targets.get(id).lines.push(clone(raw));
 }
 for(const raw of objects(plots,'boxes')){
  if(raw.xloc!=='bt'||!boxKeys.some(k=>k[0]===raw.left&&k[1]===raw.right&&near(k[2],raw.top)&&near(k[3],raw.bottom)))continue;
  const middle=(raw.top+raw.bottom)/2;
  for(const target of targets.values())if(near(middle,target.price))target.boxes.push(clone(raw));
 }
 for(const target of targets.values())target.reached=String(target.lines.at(-1)?.color||'').toLowerCase()!==String(meta.color||'#f59722').toLowerCase();
 return [...targets.values()].sort((a,b)=>(a.direction==='BULL'?0:1)-(b.direction==='BULL'?0:1)||a.n-b.n);
}
const targetGeometryCache=new WeakMap();
function targetVisibilityKey(chartType){
 return chartType==='Candles'?'nativeV1TargetsCandlesVisible':chartType==='Renko'?'nativeV1TargetsRenkoVisible':'nativeV1TargetsOtherVisible';
}
function v1TargetsVisible(inputs,chartType){
 const value=inputs?.[targetVisibilityKey(chartType)];
 return typeof value==='boolean'?value:true;
}
function targetObjects(targets,bars,isRenko,bands=true){
 const key=[isRenko,bands,bars.length,bars[0]?.time,bars[0]?.sourceTime,bars.at(-1)?.time,bars.at(-1)?.sourceTime].join('|');
 const cached=targetGeometryCache.get(targets);if(cached?.key===key)return cached.result;
 const result={lines:[],boxes:[],labels:[]};
 if(!bars.length)return result;
 const date=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short'});
 for(const target of targets){
  const mapped=rangeObjects({lines:target.lines,boxes:bands?target.boxes:[]},bars,isRenko);
  result.lines.push(...mapped.lines);result.boxes.push(...mapped.boxes);
  const line=mapped.lines.at(-1);if(!line)continue;
  const stamp=date.format(target.source*1000);
  result.labels.push({x:line.x1,xloc:'bar_time',y:target.price,nativeShadowSourceAnchor:true,nativeShadowOnLine:true,text:target.direction+' T'+target.n,
   style:'style_label_left',color:line.color,textcolor:target.reached?'#ffffff':'#1e293b',size:9,tooltip:target.direction+' target '+target.n+' · V1 reference '+stamp+'\n'+target.price.toLocaleString('en-IN',{maximumFractionDigits:2})});
 }
 targetGeometryCache.set(targets,{key,result});
 return result;
}

function readLiquidityObjects(plots){
 const text=objects(plots,'labels').find(l=>l.text==='AI_V1_LIQUIDITY')?.tooltip||'';
 const keys=text.split(';').filter(Boolean).map(s=>s.split(',').map(Number)).filter(k=>k.length===4&&k.every(Number.isFinite));
 const near=(a,b)=>Math.abs(a-b)<=Math.max(1,Math.abs(b))*1e-12;
 return objects(plots,'boxes').filter(b=>b.xloc==='bt'&&keys.some(k=>k[0]===b.left&&k[1]===b.right&&near(k[2],b.top)&&near(k[3],b.bottom))).map(b=>({...clone(b),...(plotValue(plots,'AIREF_RZ_TF')!==null?{sourceTimeframe:plotValue(plots,'AIREF_RZ_TF')}:{})}));
}
const liquidityGeometryCache=new WeakMap();
function liquidityObjects(boxes,bars,isRenko){
 const key=[isRenko,bars.length,bars[0]?.time,bars[0]?.sourceTime,bars.at(-1)?.time,bars.at(-1)?.sourceTime].join('|');
 const cached=liquidityGeometryCache.get(boxes);if(cached?.key===key)return cached.result;
 const result=rangeObjects({boxes},bars,isRenko);result.labels=[];
 for(const box of result.boxes){
  const text=box.text||'',demand=/^DEMAND/.test(text),supply=/^SUPPLY/.test(text);
  if(!demand&&!supply)continue;
  const fresh=/FRESH/i.test(text),invalid=/INVALIDATED/i.test(text),color=demand?'#047857':'#be123c';
  const phase=invalid?'Invalidated':/RETESTING/i.test(text)?'Retesting':/RETESTED/i.test(text)?'Retested':'Fresh';
  const format=n=>n.toLocaleString('en-IN',{maximumFractionDigits:2}),tf=box.sourceTimeframe||Number(/·\s*(\d+)m/.exec(text)?.[1]);
  box.border_width=fresh?2:1;box.border_color=color+(fresh?'e6':'66');
  box.bgcolor=color+(fresh?'30':invalid?'0a':'14');
  box.border_style=fresh?'style_solid':'style_dashed';
  box.text='';
  box.tooltip=(demand?'Demand':'Supply')+' order-block-style zone · '+(tf?tf+'m source':'selected source timeframe')+'\nState '+phase+'\nLow '+format(box.bottom)+' · High '+format(box.top);
  if(fresh){
   result.labels.push({x:box.right,xloc:'bar_time',y:box.top,nativeShadowSourceAnchor:true,nativeShadowOnLine:true,
    style:'style_label_left',text:(demand?'DEMAND':'SUPPLY')+' OB · Fresh',color,textcolor:'#ffffff',size:10,tooltip:box.tooltip});
  }
 }
 liquidityGeometryCache.set(boxes,{key,result});return result;
}

const shadowTableCache=new WeakMap();
function shadowReferenceTables(model,includeTargets=false){
 const cached=shadowTableCache.get(model);if(cached?.version===model.version&&cached.includeTargets===includeTargets)return cached.tables;
 const format=n=>n.toLocaleString('en-IN',{maximumFractionDigits:2});
 const date=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short'});
 const specs=[['SC1',model.previousShadow,'Previous day Shadow','#1d4ed8'],['SC2',model.neighbors.above,'Nearest Shadow above price','#6d28d9'],['SC3',model.neighbors.below,'Nearest Shadow below price','#0369a1']];
 const tables=model.tables.map(raw=>{
  if(raw.aiTitle!=='Levels · IST')return raw;
  const table=clone(raw),found=table.cells.findIndex(r=>/^SC(?:\s|$)/.test(r[0]?.text||''));
  const index=found>=0?found:1,removed=found>=0?1:0;
  const rows=specs.map(([id,range,meaning,color])=>{
   const tooltip=meaning+(range?'\nSource '+date.format(range.start*1000)+'\nLow '+format(range.low)+' · High '+format(range.high):'\nNo confirmed range in retained selected-broker history.');
   const cell=text=>({text,text_color:'#1e293b',bgcolor:'#ffffff',text_size:9,tooltip});
   const header={...cell(id+(range?' · '+date.format(range.start*1000):' · —')),bgcolor:color,text_color:'#ffffff'};
   const levels=[.44,.5,.56].map(r=>cell(range?format(range.low+(range.high-range.low)*r):'—'));
   const state=!range?'Unavailable':model.price>range.high?'Bullish':model.price<range.low?'Bearish':'In range';
   return [header,...levels,{...cell(state),text_color:state==='Bullish'?'#16a34a':state==='Bearish'?'#dc2626':'#b4780a'}];
  });
  if(includeTargets)for(const target of model.targets){
   const low=target.price-target.span*.06,high=target.price+target.span*.06;
   const tooltip=target.direction+' target '+target.n+' · V1 reference '+date.format(target.source*1000)+'\n44% '+format(low)+' · 50% '+format(target.price)+' · 56% '+format(high);
   const cell=text=>({text,text_color:'#1e293b',bgcolor:'#ffffff',text_size:9,tooltip});
   rows.push([{...cell(target.direction+' T'+target.n),bgcolor:target.lines.at(-1)?.color||'#f59722',text_color:target.reached?'#ffffff':'#1e293b'},
    cell(format(low)),cell(format(target.price)),cell(format(high)),{...cell(target.reached?'Reached':'Pending'),text_color:target.reached?'#15803d':'#b45309'}]);
  }
  table.cells.splice(index,removed,...rows);
  const delta=rows.length-removed;
  if(table.merges)table.merges=table.merges.filter(m=>!(removed&&m.startRow<=index&&m.endRow>=index)).map(m=>({...m,startRow:m.startRow>=index?m.startRow+delta:m.startRow,endRow:m.endRow>=index?m.endRow+delta:m.endRow}));
  table.rows=table.cells.length;
  return table;
 });
 shadowTableCache.set(model,{version:model.version,includeTargets,tables});return tables;
}
function placeReferenceLabel(box,occupied,pane){
 const gap=6,margin=3;
 const clamp=(value,low,high)=>Math.max(low,Math.min(value,Math.max(low,high)));
 const width=Math.min(box.width,pane.width-margin*2),height=box.height;
 const base={left:clamp(box.left,margin,pane.width-width-margin),top:clamp(box.top,24,pane.height-height-margin),width,height};
 const overlap=(a,b)=>a.left<b.left+b.width+gap&&a.left+a.width+gap>b.left&&a.top<b.top+b.height+gap&&a.top+a.height+gap>b.top;
 const candidates=[base];
 for(const obstacle of occupied){
  for(const top of [obstacle.top-height-gap,obstacle.top+obstacle.height+gap])candidates.push({...base,top:clamp(top,24,pane.height-height-margin)});
  for(const left of [obstacle.left-width-gap,obstacle.left+obstacle.width+gap])candidates.push({...base,left:clamp(left,margin,pane.width-width-margin)});
 }

 for(let level=1;level<=occupied.length+1;level++){
  for(const direction of [-1,1])candidates.push({...base,top:clamp(base.top+direction*level*(height+gap),24,pane.height-height-margin)});
  for(const direction of [-1,1])candidates.push({...base,left:clamp(base.left+direction*level*(width+gap),margin,pane.width-width-margin)});
 }
 const distance=b=>(b.left-base.left)**2+(b.top-base.top)**2;
 const result=candidates.filter(candidate=>occupied.every(other=>!overlap(candidate,other))).sort((a,b)=>distance(a)-distance(b))[0]||base;
 occupied.push(result);return result;
}
function shadowObjects(labels,bars,isRenko){
 if(!bars.length)return [];
 return labels.map(raw=>{
  const time=raw.x/(raw.xloc==='bt'?1000:1);
  let x=time;
  if(isRenko){
   let lo=0,hi=bars.length;while(lo<hi){const m=(lo+hi)>>>1;if((bars[m].sourceTime??bars[m].source_time)<time)lo=m+1;else hi=m;}
   x=bars[Math.min(lo,bars.length-1)].time;
  }
  return {...raw,x,xloc:'bar_time',nativeShadowLabel:true,text:'SHADOW CANDLE\n'+String(raw.text).replace(/^SC\s*·?\s*/,'')+' · '+Number(raw.y).toLocaleString('en-IN',{maximumFractionDigits:2}),style:'style_label_left',color:'#1e40af',textcolor:'#ffffff',text_formatting:'bold',size:12};
 });
}
function sessionObjects(sessions,bars,isRenko){
 if(!bars.length)return [];
 const stamp=b=>isRenko?(b.sourceTime??b.source_time):b.time;
 const clock=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 const names={R:'Asia reference',M:'London reference',E:'New York reference'};
 const lines=sessions.filter(s=>s.time>=stamp(bars[0])&&s.time<=stamp(bars.at(-1))).map(s=>({
  aiKind:s.kind,xloc:'bt',x1:s.time*1000,x2:s.time*1000,y1:0,y2:0,
  nativeSessionLabel:names[s.kind]+' · '+s.kind+' '+clock.format(s.time*1000)+' IST'
 }));
 return rangeObjects({lines,boxes:[]},bars,isRenko).lines;
}
class SwingLevels{
 constructor(){this.rows=[];this.high=null;this.low=null;this.count=0;this.lastKey=null;}
 update(bars){
  if(this.count>bars.length){this.rows=[];this.high=this.low=null;this.count=0;}
  if(this.count&&this.lastKey!==JSON.stringify([bars[this.count-1]?.time,bars[this.count-1]?.close]))return this.snapshot('CONFIRMED_HISTORY_CHANGED');
  for(let i=this.count;i<bars.length;i++){
   const b=bars[i];if(b.provisional||b.is_forming||b.closed===false)break;
   if(!Number.isFinite(b.close)||!Number.isFinite(b.time))break;
   this.rows.push({price:b.close,time:b.time});
   if(this.rows.length>=5){
    const w=this.rows.slice(-5),c=w[2],others=w.filter((_,n)=>n!==2);
    for(const [key,up] of [['high',true],['low',false]])if(others.every(r=>up?c.price>r.price:c.price<r.price))this[key]={price:c.price,origin_at:c.time,confirmed_at:b.time};
   }
   this.rows=this.rows.slice(-5);this.count=i+1;this.lastKey=JSON.stringify([b.time,b.close]);
  }return this.snapshot();
 }
 snapshot(error=null){return {high:this.high,low:this.low,count:this.count,pivot_left:2,pivot_right:2,error};}
}
// Presentation snapshots are keyed by selected-source context and completed-bar cutoff.
function snapshotCompletedRows(bars,asOf,endOfBar){
 return bars.filter(bar=>!bar.provisional&&!bar.historyOnly&&[bar.time,bar.open,bar.high,bar.low,bar.close].every(Number.isFinite)&&endOfBar(bar.time)<=asOf).map(bar=>({...bar}));
}
function viewedReferenceSessions(bars,range,endOfBar,bounds){
 if(!bars.length||!range)return [];
 const first=Math.max(0,Math.floor(range.from)),last=Math.min(bars.length-1,Math.floor(range.to));
 if(last<first)return [];
 const bySession=new Map();
 for(let i=first;i<=last;i++){
  const bar=bars[i],time=bar.sourceTime??bar.source_time??bar.time;
  if(bar.provisional||!Number.isFinite(time))continue;
  const session=bounds(time),asOf=endOfBar(time);
  if(!session||!Number.isFinite(session.open)||!Number.isFinite(session.end)||!(asOf>time))continue;
  const prior=bySession.get(session.open);
  if(!prior||asOf>prior.asOf)bySession.set(session.open,{...session,asOf:Math.min(asOf,session.end),time,price:bar.close});
 }
 return [...bySession.values()].sort((a,b)=>b.open-a.open);
}
function latestReferenceView(selected,bars,isRenko,latestSource,now){
 if(!selected||now<selected.open||now>=selected.end)return false;
 const latest=isRenko?bars.findLast(b=>!b.provisional&&!b.historyOnly):latestSource;
 const time=isRenko?(latest?.sourceTime??latest?.source_time??latest?.time):latest?.time;
 return Number.isFinite(time)&&selected.time===time;
}
function clipReferenceGeometry(geometry,bars,isRenko,session){
 const stamp=b=>b.sourceTime??b.source_time??b.time;
 const inside=bars.filter(b=>stamp(b)>=session.open&&stamp(b)<Math.min(session.end,session.asOf));
 if(!inside.length)return {labels:[],lines:[],boxes:[]};
 const left=isRenko?inside[0].time:session.open,right=isRenko?inside.at(-1).time:Math.min(session.end,session.asOf);
 const result={labels:[],lines:[],boxes:[]};
 const knownCoordinate=raw=>{
  if(!Number.isFinite(raw.nativeKnownAt))return left;
  if(raw.nativeKnownAt>session.asOf)return Infinity;
  if(!isRenko)return raw.nativeKnownAt;
  return inside.find(b=>stamp(b)>=raw.nativeKnownAt)?.time??right;
 };
 for(const raw of geometry.lines||[]){
  if(raw.x2<left||raw.x1>right||knownCoordinate(raw)>right)continue;
  result.lines.push({...raw,x1:Math.max(left,raw.x1,knownCoordinate(raw)),x2:Math.min(right,raw.x2),extend:'n'});
 }
 for(const raw of geometry.boxes||[]){
  if(raw.right<left||raw.left>right||(Number.isFinite(raw.nativeKnownAt)&&raw.nativeKnownAt>session.asOf))continue;
  result.boxes.push({...raw,left:Math.max(left,raw.left,raw.nativeSourceCandle?left:knownCoordinate(raw)),right:Math.min(right,raw.right)});
 }
 for(const raw of geometry.labels||[]){
  // A source anchor before the session is a preceding-session reference, not future data.
  if(raw.x>right||(Number.isFinite(raw.nativeKnownAt)&&raw.nativeKnownAt>session.asOf))continue;
  result.labels.push({...raw,x:Math.max(left,raw.x,raw.nativeSourceCandle?left:knownCoordinate(raw)),tooltip:(raw.tooltip||'')+'\nSession reference as of '+new Date(session.asOf*1000).toISOString()});
 }
 return result;
}
function sessionShadowSourceObjects(model,bars,isRenko,session,zone='Asia/Kolkata'){
 const candidates=model.archive.filter(row=>row.start>=session.open&&row.closed<=Math.min(session.asOf,session.end));
 const row=candidates.sort((a,b)=>b.closed-a.closed)[0];
 if(!row||!bars.length)return {labels:[],lines:[],boxes:[]};
 const stamp=b=>b.sourceTime??b.source_time??b.time;
 const map=t=>!isRenko?t:bars.find(b=>stamp(b)>=t)?.time??bars.at(-1).time;
 const start=map(row.start),end=map(row.closed),labelEnd=bars.findLast(b=>stamp(b)>=row.start&&stamp(b)<row.closed)?.time??end;
 const date=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 const format=n=>n.toLocaleString('en-IN',{maximumFractionDigits:2});
 const tooltip='Completed session Shadow Candle\nSource '+date.format(row.start*1000)+'–'+date.format(row.closed*1000)+' IST\nConfirmed '+date.format(row.closed*1000)+' IST\nHigh '+format(row.high)+' · Low '+format(row.low)+'\nLevels do not apply before confirmation.';
 const meta={nativeSourceCandle:true,nativeKnownAt:row.closed};
 return {lines:[],boxes:[{...meta,left:start,right:end,top:row.high,bottom:row.low,xloc:'bar_time',border_color:'#1e40af',border_width:3,border_style:'style_solid',bgcolor:'#2563eb55'}],
 labels:[{...meta,x:labelEnd,y:row.high,xloc:'bar_time',text:'SC candle · '+shadowSourceDate(row.start,zone),nativeReferenceLabel:true,style:'style_label_down',color:'#1d4ed8',textcolor:'#ffffff',size:10,tooltip}]};
}

function buildSessionReferenceGeometry(model,bars,isRenko,session,inputs={}){
 const main=rangeObjects(model.ranges,bars,isRenko);
 if(inputs.nativeReferenceLinesVisible===false)main.lines=[];
 if(inputs.nativeRangeZonesVisible===false)main.boxes=[];
 const labels=inputs.nativeRedLabelsVisible===false?[]:labelObjects(model.labels,bars,isRenko,inputs.nativeRedLabelsFullText===true);
 const parts=[];
 if(inputs.nativeNearestShadowVisible!==false)parts.push(neighborObjects(model.neighbors,bars,inputs.referenceTimezone));
 if(inputs.nativePreviousShadowVisible!==false)parts.push(previousShadowObjects(model.previousShadow,bars,isRenko,inputs.referenceTimezone),sessionShadowSourceObjects(model,bars,isRenko,session,inputs.referenceTimezone));
 if(v1TargetsVisible(inputs,inputs.chartType||'Candles'))parts.push(targetObjects(model.targets,bars,isRenko,inputs.nativeV1TargetBandsVisible!==false));
 if(inputs.nativeLiquidityZonesVisible!==false)parts.push(liquidityObjects(model.liquidity,bars,isRenko));
 if(inputs.nativeSessionSeparatorsVisible!==false)main.lines.push(...sessionObjects(model.sessions,bars,isRenko));
 for(const part of parts){
  labels.push(...part.labels.map(label=>inputs.compact&&/^(BULL|BEAR) T/.test(label.text||'')?{...label,nativeShadowOnLine:false,nativeReferenceLabel:true,size:11,text:label.text+' · '+Number(label.y).toLocaleString('en-IN',{maximumFractionDigits:2})}:label));
  main.lines.push(...part.lines);main.boxes.push(...part.boxes);
 }
 const sessionBars=bars.filter(b=>{const t=b.sourceTime??b.source_time??b.time;return t>=session.open&&t<Math.min(session.asOf,session.end);});
 if(sessionBars.length&&inputs.nativePreviousDayVisible!==false)for(const [name,row] of Object.entries(model.previousDay)){
  const left=sessionBars[0].time,right=sessionBars.at(-1).time,color=name==='PDH'?'#b45309':'#0f766e';
  main.lines.push({x1:left,x2:right,y1:row.price,y2:row.price,xloc:'bar_time',color,width:2,style:'style_dashed'});
  labels.push({x:right,y:row.price,xloc:'bar_time',text:name,nativeShadowOnLine:true,color,textcolor:'#fff',size:10,style:'style_label_left',tooltip:row.tooltip});
 }
 return clipReferenceGeometry({...main,labels},bars,isRenko,session);
}
function referenceAxisKey(bars,isRenko){
 return JSON.stringify(bars.map(b=>isRenko?[b.time,b.sourceTime??b.source_time??b.time]:b.time));
}
const sessionGeometryCache=new WeakMap();
function sessionReferenceGeometry(model,bars,isRenko,session,inputs={}){
 const {referenceAxisKey:axis,...presentation}=inputs;
 const axisKey=axis??referenceAxisKey(bars,isRenko),styleKey=JSON.stringify(presentation);
 const cached=sessionGeometryCache.get(model);
 if(cached&&cached.axisKey===axisKey&&cached.version===model.version&&cached.open===session.open&&cached.end===session.end&&cached.asOf===session.asOf&&cached.isRenko===isRenko&&cached.styleKey===styleKey)return cached.geometry;
 const geometry=buildSessionReferenceGeometry(model,bars,isRenko,session,presentation);
 sessionGeometryCache.set(model,{axisKey,version:model.version,open:session.open,end:session.end,asOf:session.asOf,isRenko,styleKey,geometry});
 return geometry;
}

function snapshotDataVersion(bars,asOf,endOf,includeVolume=true){
 let a=2166136261,b=5381,count=0;
 for(const row of bars){
  if(row.provisional||row.historyOnly||endOf(row.time)>asOf)continue;
  count++;const text=[row.time,row.open,row.high,row.low,row.close,includeVolume?(row.volume??0):0].join('|')+';';
  for(let i=0;i<text.length;i++){a=Math.imul(a^text.charCodeAt(i),16777619);b=Math.imul(b,33)^text.charCodeAt(i);}
 }
 return [count,a>>>0,b>>>0].join(':');
}
class SessionReferenceCache{
 constructor(load,options={}){this.load=load;this.options=options;this.entries=new Map();this.jobs=[];this.active=false;}
 request(session,revision='',priority=0){
  const key=[session.open,session.asOf,revision].join('|');
  const prior=this.entries.get(key);
  if(prior&&prior.status!=='cancelled'&&!prior.controller?.signal.aborted){prior.wanted=true;prior.priority=priority;return prior;}
  const entry={session,revision,status:'loading',model:null,error:null,wanted:true,priority};
  this.entries.set(key,entry);
  entry.promise=new Promise(resolve=>entry.resolve=resolve);
  this.jobs.push(entry);
  Promise.resolve().then(()=>this.pump());
  return entry;
 }
 retry(entry){
  if(!entry||entry.status==='ready')return entry;
  entry.wanted=false;entry.controller?.abort(new DOMException('Calculation explicitly restarted','AbortError'));
  const key=[entry.session.open,entry.session.asOf,entry.revision].join('|');
  if(this.entries.get(key)===entry)this.entries.delete(key);
  return this.request(entry.session,entry.revision,entry.priority);
 }
 cancelObsolete(){
  const entry=this.runningEntry;if(entry&&!entry.wanted&&!entry.controller.signal.aborted)entry.controller.abort(new DOMException('Viewport moved','AbortError'));
 }
 async pump(){
  if(this.active)return;this.active=true;
  try{
   while(this.jobs.length){
    this.jobs.sort((a,b)=>a.priority-b.priority);
    const entry=this.jobs.shift();
    if(!entry.wanted){entry.status='cancelled';entry.resolve(entry);continue;}
    entry.controller=new AbortController();this.runningEntry=entry;
    try{
     for(let attempt=0;;attempt++){
      entry.retryAt=null;this.options.onChange?.(entry);
      try{entry.model=await this.load(entry.session,entry.controller.signal);entry.status='ready';entry.retryAt=null;break;}
      catch(error){
       const delay=this.options.retryDelay?.(error,attempt);
       if(entry.controller.signal.aborted||!Number.isFinite(delay)||delay<0||attempt>=4)throw error;
       entry.retryAt=Date.now()+delay;entry.retryReason=error.message;entry.retryAttempt=attempt+1;this.options.onChange?.(entry);
       await this.options.wait(delay,entry.controller.signal);
      }
     }
    }
    catch(error){entry.status=error.name==='AbortError'?'cancelled':'unavailable';entry.error=error.message;}
    this.runningEntry=null;entry.resolve(entry);
    // Keep the active view plus a bounded cache; no persistent/provider budgets are changed.
    if(this.entries.size>64)for(const [key,old] of this.entries){
     if(this.entries.size<=64)break;
     if(!old.wanted&&old.status!=='loading')this.entries.delete(key);
    }
   }
  }finally{this.active=false;}
 }
}
root.SectorPulseAiV1Display={MARKER,Model,snapshotCompletedRows,viewedReferenceSessions,latestReferenceView,clipReferenceGeometry,sessionShadowSourceObjects,referenceAxisKey,sessionReferenceGeometry,SessionReferenceCache,snapshotDataVersion,referenceSource,referenceClock,markerPoints,labelObjects,rangeObjects,sessionObjects,shadowObjects,placeReferenceLabel,nearestRanges,neighborObjects,previousSessionRange,previousShadowObjects,shadowReferenceTables,readTargetObjects,targetObjects,readLiquidityObjects,liquidityObjects,targetVisibilityKey,v1TargetsVisible,SwingLevels};
})(typeof window==='undefined'?globalThis:window);

/* One maintained Sector Pulse program. The chart evaluator projects its sections
   onto their verified clock domains (completed Renko / regular broker candles).
   These are internal evaluation passes, not separately installed indicators. */
(function(root){'use strict';
const marker='SP_UNIFIED_SECTOR_PULSE_20261128';
function body(source){return source.replace(/^\/\/@version=.*\n/,'').replace(/^indicator\([^\n]*\)\s*\n/m,'');}
function section(source,name){
 const a=source.indexOf('// SP_BEGIN_'+name+'\n'),b=source.indexOf('// SP_END_'+name,a);
 if(a<0||b<a)throw Error('Sector Pulse source section is missing: '+name);
 return source.slice(a+('// SP_BEGIN_'+name+'\n').length,b);
}
function header(source){return source.match(/^indicator\([^\n]*\)/m)?.[0]||'indicator("Sector Pulse", overlay=true)';}
function supertrend(source){
 if(!source.includes(marker))return source;
 return '//@version=6\n'+section(source,'SUPERTREND').replace(/^\/\/ SP_COMPONENT_DECLARATION (.*)\n/,'$1\n');
}
function references(source){
 if(!source.includes(marker))throw Error('A unified Sector Pulse program is required.');
 return '//@version=6\n'+section(source,'REFERENCES').replace(/^\/\/ SP_COMPONENT_DECLARATION (.*)\n/,'$1\n');
}
const native=String.raw`
string sp_nativeGroup="Sector Pulse — Midline / RSI"
int sp_period=input.int(123,"Gaussian period",minval=5,maxval=500,group=sp_nativeGroup)
int sp_rsiLength=input.int(14,"RSI period",minval=1,maxval=500,group=sp_nativeGroup)
int sp_maLength=input.int(14,"RSI SMA period",minval=1,maxval=500,group=sp_nativeGroup)
bool sp_midVisible=input.bool(true,"Midline",group=sp_nativeGroup)
bool sp_rsiVisible=input.bool(true,"RSI Zones (Candles)",group=sp_nativeGroup)
float sp_beta=(1-math.cos(2*math.pi/sp_period))/(math.pow(2,1.0/3)-1)
float sp_alpha=-sp_beta+math.sqrt(sp_beta*sp_beta+2*sp_beta)
var float sp_g1=na
var float sp_g2=na
var float sp_g3=na
var int sp_trend=0
sp_g1 := na(sp_g1[1]) ? close : sp_alpha*close+(1-sp_alpha)*sp_g1[1]
sp_g2 := na(sp_g2[1]) ? close : sp_alpha*sp_g1+(1-sp_alpha)*sp_g2[1]
sp_g3 := na(sp_g3[1]) ? close : sp_alpha*sp_g2+(1-sp_alpha)*sp_g3[1]
sp_trend := not na(sp_g3[1]) and sp_g3!=sp_g3[1] ? (sp_g3>sp_g3[1]?1:-1) : sp_trend
float sp_rsi=ta.rsi(close,sp_rsiLength)
float sp_rsiMa=ta.sma(sp_rsi,sp_maLength)
plot(sp_midVisible?sp_g3:na,"Market Min Midline",color=sp_trend>0?#2ea043:sp_trend<0?#e53935:#ffb84d,linewidth=2,force_overlay=true)
bool sp_showRsi=sp_rsiVisible and chart.is_standard
plot(sp_showRsi?sp_rsi:na,"RSI",color=#7e57c2,linewidth=2)
plot(sp_showRsi?sp_rsiMa:na,"RSI SMA",color=#ff0000,linewidth=2)
sp_z0=plot(sp_showRsi?0:na,"0",color=na)
sp_z40=plot(sp_showRsi?40:na,"40",color=#000000)
sp_z60=plot(sp_showRsi?60:na,"60",color=#000000)
sp_z80=plot(sp_showRsi?80:na,"80",color=#000000)
sp_z100=plot(sp_showRsi?100:na,"100",color=na)
fill(sp_z0,sp_z40,color=#ff000059)
fill(sp_z40,sp_z60,color=#80808059)
fill(sp_z60,sp_z80,color=#00800059)
fill(sp_z80,sp_z100,color=#00800059)
fill(sp_z80,sp_z100,color=#ff000040)
`;
function baseCleanReference(source){
 return source.split('\n').map(line=>line.trim().startsWith('string caption = rzLabels ?')&&line.includes('rzSourceTf')&&line.includes('str.tostring(z.lo')
  ?line.slice(0,line.length-line.trimStart().length)+'string caption = rzLabels ? (z.side == 1 ? "DEMAND" : "SUPPLY")+" OB · "+(z.state == 2 ? "Invalidated" : z.touching ? "Retesting" : z.tests > 0 ? "Retested" : "Fresh") : ""':line).join('\n');
}
function extendReferenceGrid(source){
 if(source.includes('SP_UNBOUNDED_TARGET_GRID_V1'))return source;
 if(!source.includes('type TargetSession')||!source.includes('f_targetSegment('))return source;
 return source.replace('type TargetSession',"// SP_UNBOUNDED_TARGET_GRID_V1\ntype SPXTarget\n    float hi\n    float lo\n    int key\n    int n\n    bool upper\n    int reveal\n    int hit\n    int finish\nvar array<SPXTarget> spxTargets=array.new<SPXTarget>()\nvar int spxUpMax=0\nvar int spxDnMax=0\n"+'\n'+'type TargetSession').replace('f_targetSegment(int left',"// Logical grid indices are unbounded; retain only nearby drawing evidence.\nif newSession\n    spxUpMax := 0\n    spxDnMax := 0\nif active and array.size(targetSessions)>0\n    TargetSession spxRec=array.last(targetSessions)\n    float spxSpan=spxRec.hi-spxRec.lo\n    if spxSpan>0\n        spxUpMax := math.max(spxUpMax,int(math.floor((high-spxRec.hi)/spxSpan)))\n        spxDnMax := math.max(spxDnMax,int(math.floor((spxRec.lo-low)/spxSpan)))\n        for spxSide=0 to 1\n            bool spxUpper=spxSide==0\n            int spxAchieved=spxUpper ? spxUpMax : spxDnMax\n            if (spxUpper or bothDirections) and spxAchieved>=targetCount-forward\n                int spxFirst=math.max(targetCount+1,spxAchieved-8)\n                int spxLast=math.max(spxFirst,spxAchieved+forward)\n                if array.size(spxTargets)>0\n                    for spxJ=array.size(spxTargets)-1 to 0\n                        SPXTarget spxOld=array.get(spxTargets,spxJ)\n                        if spxOld.key==spxRec.key and spxOld.upper==spxUpper and spxOld.n<spxFirst\n                            array.remove(spxTargets,spxJ)\n                for spxN=spxFirst to spxLast\n                    SPXTarget spxFound=na\n                    for spxItem in spxTargets\n                        if spxItem.key==spxRec.key and spxItem.upper==spxUpper and spxItem.n==spxN\n                            spxFound:=spxItem\n                    float spxPrice=spxUpper ? spxRec.hi+spxN*spxSpan : spxRec.lo-spxN*spxSpan\n                    bool spxHit=spxUpper ? high>=spxPrice : low<=spxPrice\n                    if na(spxFound)\n                        spxFound:=SPXTarget.new(spxRec.hi,spxRec.lo,spxRec.key,spxN,spxUpper,time,spxHit ? time : na,time)\n                        array.push(spxTargets,spxFound)\n                    else\n                        spxFound.finish:=time\n                        if spxHit and na(spxFound.hit)\n                            spxFound.hit:=time\n                while array.size(spxTargets)>120\n                    array.shift(spxTargets)\n"+'\n'+'f_targetSegment(int left').replace('// Shared TradingView object budget: keep newest targetLines.',"// Render the retained window using the original anchor and span.\nif barstate.islast and showTargets and targetMode!=\"OFF\"\n    for spxItem in spxTargets\n        float spxSpan=spxItem.hi-spxItem.lo\n        float spxPrice=spxItem.upper ? spxItem.hi+spxItem.n*spxSpan : spxItem.lo-spxItem.n*spxSpan\n        color spxReached=spxItem.upper ? upperColor : lowerColor\n        if na(spxItem.hit)\n            f_targetSegment(spxItem.reveal,spxItem.finish,spxPrice,spxSpan,pendingColor)\n        else\n            if spxItem.hit>spxItem.reveal\n                f_targetSegment(spxItem.reveal,spxItem.hit,spxPrice,spxSpan,pendingColor)\n            f_targetSegment(math.max(spxItem.reveal,spxItem.hit),spxItem.finish,spxPrice,spxSpan,spxReached)\n        if targetLabels\n            array.push(targetText,label.new(spxItem.finish,spxPrice,\"T\"+str.tostring(spxItem.n),xloc=xloc.bar_time,style=label.style_label_left,color=color.new(color.black,100),textcolor=na(spxItem.hit) ? pendingColor : spxReached,size=size.tiny,force_overlay=true))\n"+'\n'+'// Shared TradingView object budget: keep newest targetLines.');
}
function cleanReference(source){return extendReferenceGrid(baseCleanReference(source));}
function build(superSource,referenceSource){
 const rawReference=referenceSource.split('// RSI Zones — separate indicator pane.')[0];
 if(superSource.includes(marker)){
  const prior=references(superSource).trimEnd();
  // Upgrade our unchanged maintained reference body; preserve imported edits.
  if(prior!==rawReference.trimEnd()&&prior!==baseCleanReference(rawReference).trimEnd()&&prior!==cleanReference(rawReference).trimEnd())return superSource;
  if(section(superSource,'NATIVE').trim()!==native.trim())return superSource;
  superSource=supertrend(superSource);
 }
 const ref=cleanReference(rawReference);
 // One declaration; all Supertrend price plots explicitly target the main pane.
 const priceBody=body(superSource).trimEnd().replace(/\bplot(?:shape)?\([^\n]*\)/g,call=>call.includes('force_overlay=')?call:call.replace(/\)$/,', force_overlay=true)'));
 return '//@version=6\nindicator("Sector Pulse", overlay=false, behind_chart=true, precision=2, max_lines_count=500, max_labels_count=500, max_boxes_count=500, max_bars_back=5000)\n// '+marker+
 '\n// One indicator. Runtime broker-clock projections and historical viewport/cache are browser infrastructure.\n'+
 '// SP_BEGIN_SUPERTREND\n// SP_COMPONENT_DECLARATION '+header(superSource)+'\n'+priceBody+'\n// SP_END_SUPERTREND\n'+
 '// SP_BEGIN_REFERENCES\n// SP_COMPONENT_DECLARATION '+header(ref)+'\n'+body(ref).trimEnd()+'\n// SP_END_REFERENCES\n'+
 '// SP_BEGIN_NATIVE\n'+native+'\n// SP_END_NATIVE\n';
}
root.SectorPulseUnifiedSource={marker,build,supertrend,references,native,section,cleanReference};
})(typeof window==='undefined'?globalThis:window);

/* Validated historical model reuse. No credentials, account mutation or orders. */
(function(root){'use strict';
const VERSION=3,TTL=7*86400000,MAX=64,fields=['tables','labels','ranges','sessions','shadowLabels','archive','previousDay','neighbors','previousShadow','targets','liquidity','pins','labelPins','version','price','computations'];
async function digest(value){
 const bytes=new TextEncoder().encode(JSON.stringify(value));
 const result=await root.crypto.subtle.digest('SHA-256',bytes);
 return Array.from(new Uint8Array(result),n=>n.toString(16).padStart(2,'0')).join('');
}
function sourceUsesVolume(source){
 const code=String(source).replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,'');
 return /\bvolume\b|\bta\.(?:vwap|vwma|mfi|obv|accdist|pvi|nvi|pvt|iii|wvad)\b/.test(code);
}
function candleInput(rows,includeVolume=true){
 return rows.map(r=>[r.openTime,r.closeTime,r.open,r.high,r.low,r.close,includeVolume?(r.volume??null):null,r.provisional===true,r.historicalPrefixThrough??null]);
}
function candleDigest(rows,includeVolume=true){return digest(candleInput(rows,includeVolume));}
function abortable(promise,signal){
 if(!signal)return promise;signal.throwIfAborted();
 return new Promise((resolve,reject)=>{const abort=()=>reject(signal.reason);signal.addEventListener('abort',abort,{once:true});Promise.resolve(promise).then(v=>{signal.removeEventListener('abort',abort);resolve(v)},e=>{signal.removeEventListener('abort',abort);reject(e)});});
}
function snapshot(model){
 const out={};for(const field of fields)out[field]=model[field] instanceof Map?[...model[field]]:model[field];
 return JSON.parse(JSON.stringify(out));
}
function restore(data,asOf){
 if(!data||!Array.isArray(data.tables)||!data.tables.length||!Array.isArray(data.archive)||data.archive.some(x=>!Number.isFinite(x.closed)||x.closed>asOf)||data.previousShadow?.closed>asOf)return null;
 if(!Array.isArray(data.pins)||!Array.isArray(data.labelPins))return null;
 const model=new root.SectorPulseAiV1Display.Model();
 for(const field of fields)if(Object.hasOwn(data,field))model[field]=['pins','labelPins'].includes(field)?new Map(data[field]||[]):data[field];
 return model;
}
function indexedStore(){
 let opening,lastError=null;
 const database=()=>opening??=(new Promise(resolve=>{
  if(!root.indexedDB){resolve(null);return;}
  let ended=false;const timer=setTimeout(()=>{ended=true;lastError='cache-open-timeout';resolve(null)},2000);
  const request=root.indexedDB.open('sector-pulse-historical-reference-models-v3');
  request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('models'))request.result.createObjectStore('models',{keyPath:'key'});};
  request.onsuccess=()=>{clearTimeout(timer);request.result.onversionchange=()=>request.result.close();if(ended)request.result.close();else resolve(request.result)};
  request.onerror=()=>{clearTimeout(timer);lastError=request.error?.name||'cache-open-error';ended=true;resolve(null)};
  request.onblocked=()=>{clearTimeout(timer);lastError='cache-open-blocked';ended=true;resolve(null)};
 }));
 async function transaction(mode,run){
  const db=await database();if(!db)return null;
  return new Promise(resolve=>{let value=null;const tx=db.transaction('models',mode);const store=tx.objectStore('models');run(store,v=>value=v);tx.oncomplete=()=>resolve(value);tx.onerror=tx.onabort=()=>{lastError=tx.error?.name||'cache-transaction-aborted';resolve(null)};});
 }
 return {
  get diagnostics(){return {lastError};},
  get:key=>transaction('readonly',(s,done)=>{const r=s.get(key);r.onsuccess=()=>done(r.result||null)}),
  put:record=>transaction('readwrite',(s,done)=>{s.put(record);const r=s.getAll();r.onsuccess=()=>{const rows=r.result.sort((a,b)=>a.savedAt-b.savedAt),now=Date.now();let remaining=rows.length;for(const row of rows)if(now-row.savedAt>TTL||remaining>MAX){s.delete(row.key);remaining--;}done(true)}}),
  delete:key=>transaction('readwrite',s=>s.delete(key))
 };
}
let sharedStore;
class PersistentReferenceCache{
 constructor({namespace,source,store,hash=digest,now=()=>Date.now()}){
  this.namespace=namespace;this.source=source;this.includeVolume=sourceUsesVolume(source);this.store=store||(sharedStore??=indexedStore());this.hash=hash;this.now=now;
 }
 async key(session,revision){try{return await this.hash([VERSION,this.namespace,this.source,session.open,session.asOf,revision]);}catch(error){error.code='CACHE_UNAVAILABLE';throw error;}}
 async read(session,revision,loadInput,signal,onProgress){
  const key=await this.key(session,revision),record=await abortable(this.store.get(key),signal);
  if(!record||record.schema!==VERSION||record.asOf!==session.asOf||this.now()-record.savedAt>TTL||!Array.isArray(record.dependencies)||!record.dependencies.length){this.lastRead={reason:!record?'missing':'invalid-or-expired',key:key.slice(0,12)};return null;}
  const started=root.performance?.now?.()||0;
  let cursor=0,changed=null,failed=null;
  const timings=[];
  // Independent intervals validate concurrently, with a small fixed bound.
  // The selected account/source and every dependency fingerprint remain mandatory.
  const validate=async()=>{
   while(cursor<record.dependencies.length&&!changed&&!failed){
    const dep=record.dependencies[cursor++];signal?.throwIfAborted();
    onProgress?.('Validating cached '+dep.request.interval+' candles…');
    try{
     const begin=root.performance?.now?.()||0;
     const rows=await abortable(loadInput(dep.request),signal),loaded=root.performance?.now?.()||0;
     const actualHash=await this.hash(candleInput(rows,this.includeVolume));
     timings.push({interval:dep.request.interval,loadMs:loaded-begin,hashMs:(root.performance?.now?.()||0)-loaded});
     if(actualHash!==dep.hash)changed={reason:'dependency-changed',interval:dep.request.interval,key:key.slice(0,12),expected:dep.sample,actual:{count:rows.length,first:candleInput(rows.slice(0,1))[0],last:candleInput(rows.slice(-1))[0]}};
    }catch(error){failed=error;}
   }
  };
  await Promise.all(Array.from({length:Math.min(3,record.dependencies.length)},validate));
  if(failed)throw failed;
  if(changed){this.lastRead=changed;await this.store.delete(key);return null;}

  const model=restore(record.model,session.asOf);if(!model){this.lastRead={reason:'invalid-model',key:key.slice(0,12)};await this.store.delete(key);return null;}
  this.lastRead={reason:'validated-hit',key:key.slice(0,12)};
  return {model,validationMs:(root.performance?.now?.()||0)-started,dependencies:record.dependencies.length,timings};
 }
 async write(session,revision,model,dependencies){
  if(!dependencies.length||dependencies.length>64)return false;
  const key=await this.key(session,revision);
  return this.store.put({key,schema:VERSION,asOf:session.asOf,savedAt:this.now(),model:snapshot(model),dependencies});
 }
}
class SnapshotReplayEngine{
 constructor({start,result,max=64}){this.start=start;this.result=result;this.max=max;this.completed=new Map();}
 begin(job){
  this.job=job;
  this.pending=new Promise((resolve,reject)=>{this.resolve=resolve;this.reject=reject;});
  // Cancellation of one viewport must not create an unhandled shared rejection.
  void this.pending.catch(()=>{});
 }
 dispose(){this.control?.stop?.();}
 finish(plots){
  const model=this.result(this.job,plots);
  this.completed.set(this.job.key,model);
  while(this.completed.size>this.max)this.completed.delete(this.completed.keys().next().value);
  this.resolve(model);
 }
 async evaluate(job,signal,onProgress){
  if(this.completed.has(job.key))return this.completed.get(job.key);
  this.progress=onProgress;onProgress?.(this.ready?'Waiting for the current reference calculation…':'Initializing the shared reference engine…');
  if(!this.ready){
   this.begin(job);this.replay={...job.replay,controlled:true,onControl:c=>this.control=c};
   this.ready=Promise.resolve(this.start(this.replay,plots=>{try{this.finish(plots)}catch(e){this.reject(e)}},message=>this.progress?.(message)))
    .then(data=>this.finish(data.plots)).catch(error=>{this.failed=error;this.reject(error);throw error;});
   void this.ready.catch(()=>{});
  }
  await abortable(this.ready,signal);
  await abortable(this.pending,signal);
  if(this.failed)throw this.failed;
  if(this.completed.has(job.key))return this.completed.get(job.key);
  signal?.throwIfAborted();
  this.begin(job);Object.assign(this.replay,job.replay);this.replay.controlled=true;
  this.control.refresh(true);
  return abortable(this.pending,signal);
 }
}
function compactReferenceResult(message){
 if(!message||typeof message!=='object'||!message.plots)return message;
 return {...message,plots:Object.fromEntries(Object.entries(message.plots).map(([key,plot])=>[key,plot&&Array.isArray(plot.data)?{...plot,data:plot.data.slice(-1)}:plot]))};
}
function referenceWorkerBootstrap(url){
 return 'const __spCompactReference='+compactReferenceResult.toString()+';const __spPostMessageRaw=self.postMessage.bind(self);self.postMessage=(message,...rest)=>__spPostMessageRaw(__spCompactReference(message),...rest);importScripts('+JSON.stringify(url)+');';
}

root.SectorPulseReferenceCache={PersistentReferenceCache,SnapshotReplayEngine,digest,candleInput,candleDigest,sourceUsesVolume,compactReferenceResult,referenceWorkerBootstrap,abortable,snapshot,restore,indexedStore};
})(typeof window==='undefined'?globalThis:window);
