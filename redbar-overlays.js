/* Port of Pinaki's redbar-theory-floating.pine, supply/demand lines 338–469
   and Global Sessions lines 147–187, 544–565. Original source is untouched.
   Uses the source defaults; values differ when feed, settings or history differs. */
(function(root){
 const defaults={maxBase:6,baseAtr:1.8,weak:.35,strong:.9,keep:6,age:300,tentative:true,tick:1};
 const sessionDefaults=[{name:'ASIA',timezone:'Asia/Tokyo',start:'09:00',color:'#0096b4'},{name:'LONDON',timezone:'Europe/London',start:'08:00',color:'#e69114'},{name:'NEW YORK',timezone:'America/New_York',start:'08:00',color:'#aa4bd2'}];
 const ist=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 function parts(format,time){return Object.fromEntries(format.formatToParts(new Date(time*1000)).map(p=>[p.type,p.value]));}
 function supplyDemand(candles,symbol,options={}){
  const c={...defaults,...options},rows=candles.filter(x=>!x.is_forming),zones=[],atr=[],days=[],inside=[];let average=null,total=0;
  for(let i=0;i<rows.length;i++){
   const bar=rows[i],p=parts(ist,bar.timestamp),minutes=+p.hour*60+(+p.minute);days.push(p.year+p.month+p.day);inside.push(minutes>=(symbol.startsWith('MCX:')?540:555)&&minutes<(symbol.startsWith('MCX:')?1410:930));
   const tr=i?Math.max(bar.high-bar.low,Math.abs(bar.high-rows[i-1].close),Math.abs(bar.low-rows[i-1].close)):bar.high-bar.low;
   total+=tr;if(i===13)average=total/14;else if(i>13)average=(average*13+tr)/14;atr.push(average);
   for(let j=zones.length-1;j>=0;j--){const z=zones[j],broken=z.supply?bar.close>z.high:bar.close<z.low;if(broken||i-z.born>c.age){zones.splice(j,1);continue;}
    const touching=bar.high>=z.low&&bar.low<=z.high;if(touching&&!z.touching&&i>z.born)z.touches++;z.touching=touching;
    const departure=z.supply?z.low-bar.close:bar.close-z.high;if(!z.strong&&z.touches===0&&i-z.born<=3&&departure>=Math.max(c.strong,c.weak)*z.atr)z.strong=true;z.right=bar.timestamp;
   }
   let made=false;if(!inside[i]||i-c.maxBase-3<0||atr[i-c.maxBase-3]===null)continue;
   for(let departure=1;departure<=3&&!made;departure++){
    let baseHigh=-Infinity,baseLow=Infinity,bodyHigh=-Infinity,bodyLow=Infinity,bodyTotal=0,rangeTotal=0,compact=true;
    for(let n=1;n<=c.maxBase;n++){
     const k=departure+n-1,index=i-k,base=rows[index];if(!base)break;
     baseHigh=Math.max(baseHigh,base.high);baseLow=Math.min(baseLow,base.low);bodyHigh=Math.max(bodyHigh,base.open,base.close);bodyLow=Math.min(bodyLow,base.open,base.close);bodyTotal+=Math.abs(base.close-base.open);rangeTotal+=base.high-base.low;compact=compact&&inside[index]&&days[index]===days[i];
     if(n>1)compact=compact&&base.high>=rows[index+1].low&&base.low<=rows[index+1].high;
     const a=atr[i-departure],width=baseHigh-baseLow;
     if(n<2||!compact||width<=c.tick||width>c.baseAtr*a||bodyTotal>.6*rangeTotal||made)continue;
     const down=bar.close<baseLow-c.weak*a,up=bar.close>baseHigh+c.weak*a;let valid=down||up,impulse=0;
     for(let d=0;d<departure;d++){const b=rows[i-d];valid=valid&&inside[i-d]&&days[i-d]===days[i]&&(down?b.close<=baseHigh:b.close>=baseLow);impulse=Math.max(impulse,down?b.open-b.close:b.close-b.open);}
     const distance=down?baseLow-bar.close:bar.close-baseHigh,strong=distance>=Math.max(c.strong,c.weak)*a&&impulse>=.5*a,high=down?baseHigh:bodyHigh,low=down?bodyLow:baseLow;
     const side=zones.filter(z=>z.supply===down),duplicate=side.some(z=>high>=z.low&&low<=z.high);
     if(valid&&impulse>=.25*a&&(strong||c.tentative)&&high-low>=c.tick&&!duplicate){if(side.length>=c.keep)zones.splice(zones.indexOf(side[0]),1);zones.push({supply:down,strong,atr:a,born:i,detected:bar.timestamp,timestamp:base.timestamp,low,high,touches:0,touching:false,right:bar.timestamp});made=true;}
    }
   }
  }
  return zones;
 }
 function zonedTimestamp(year,month,day,start,timezone){
  const [hour,minute]=start.split(':').map(Number),wanted=Date.UTC(year,month-1,day,hour,minute),format=new Intl.DateTimeFormat('en-GB',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});let guess=wanted;
  for(let i=0;i<3;i++){const p=parts(format,guess/1000),represented=Date.UTC(+p.year,+p.month-1,+p.day,+p.hour,+p.minute);guess+=wanted-represented;}
  return guess/1000;
 }
 function sessionMarkers(candles,sessions=sessionDefaults){
  const dates=new Map();for(const row of candles){const p=parts(ist,row.timestamp);dates.set(p.year+p.month+p.day,p);}
  return [...dates.values()].flatMap(p=>sessions.map(s=>({...s,timestamp:zonedTimestamp(+p.year,+p.month,+p.day,s.start,s.timezone)}))).sort((a,b)=>a.timestamp-b.timestamp);
 }
 function fibonacciReferences(candles,sessions=sessionDefaults){
  const rows=candles.filter(c=>!c.is_forming),slots=new Map();let lastKey=null,redDone=false,slot=0,floating=null;
  const markers=sessionMarkers(rows.length?[{timestamp:rows[0].timestamp-86400},...rows]:[],sessions);let cursor=-1;
  for(const row of rows){while(cursor+1<markers.length&&markers[cursor+1].timestamp<=row.timestamp)cursor++;const marker=markers[cursor];if(!marker)continue;
   if(marker.timestamp!==lastKey){lastKey=marker.timestamp;redDone=false;slot=marker.name==='ASIA'?0:marker.name==='LONDON'?2:4;slots.set(slot,{name:marker.name,opening:true,...row});}
   else if(!redDone&&row.close<row.open){redDone=true;slots.set(slot+1,{name:marker.name,opening:false,...row});}
   if(row.close<row.open)floating=row;
  }
  const levels=row=>[.382,.5,.618].map(ratio=>({...row,ratio,price:row.high-(row.high-row.low)*ratio}));
  return {fixed:[...slots.values()].flatMap(levels),floating:floating?levels(floating):[]};
 }
 function dailyReferences(daily,livePrice,now=Date.now()/1000){
  const today=parts(ist,now),day=today.year+today.month+today.day;const rows=daily.map(r=>{const p=parts(ist,r[0]);return {timestamp:r[0],open:r[1],high:r[2],low:r[3],close:r[4],day:p.year+p.month+p.day,year:+p.year,month:+p.month,date:+p.day};}).sort((a,b)=>a.timestamp-b.timestamp);
  const prior=rows.filter(r=>r.day<day).at(-1),current=rows.find(r=>r.day===day);if(current&&Number.isFinite(livePrice)){current.high=Math.max(current.high,livePrice);current.low=Math.min(current.low,livePrice);current.close=livePrice;}
  const weekDate=new Date(Date.UTC(+today.year,+today.month-1,+today.day));weekDate.setUTCDate(weekDate.getUTCDate()-((weekDate.getUTCDay()+6)%7));const week=weekDate.toISOString().slice(0,10).replaceAll('-','');const refs=[];
  if(prior){const pivot=(prior.high+prior.low+prior.close)/3,mid=(prior.high+prior.low)/2,reflected=2*pivot-mid;refs.push({group:'cpr',name:'CPR Pivot',price:pivot,timestamp:prior.timestamp,color:'#e69114'},{group:'cpr',name:'CPR TC',price:Math.max(mid,reflected),timestamp:prior.timestamp,color:'#ab77d9'},{group:'cpr',name:'CPR BC',price:Math.min(mid,reflected),timestamp:prior.timestamp,color:'#ab77d9'},{group:'periods',name:'Previous Day High',price:prior.high,timestamp:prior.timestamp,color:'#e69114'},{group:'periods',name:'Previous Day Low',price:prior.low,timestamp:prior.timestamp,color:'#e69114'});}
  for(const [name,group,color]of [['Current Week',rows.filter(r=>r.day>=week),'#26a69a'],['Current Month',rows.filter(r=>r.year===+today.year&&r.month===+today.month),'#ce72c5']])if(group.length)refs.push({group:'periods',name:name+' High',price:Math.max(...group.map(r=>r.high)),timestamp:group[0].timestamp,color},{group:'periods',name:name+' Low',price:Math.min(...group.map(r=>r.low)),timestamp:group[0].timestamp,color});
  return refs;
 }
 root.RedBarOverlays={supplyDemand,sessionMarkers,sessionDefaults,defaults,fibonacciReferences,dailyReferences};if(typeof module!=='undefined')module.exports=root.RedBarOverlays;
})(typeof window==='undefined'?globalThis:window);
