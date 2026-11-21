/* Browser downloads for the Investment view. */
(()=>{
'use strict';
const mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const format=new Intl.NumberFormat('en-IN',{maximumFractionDigits:2});
const show=value=>value==null?'Unavailable':typeof value==='number'?format.format(value):String(value);
function download(parts,type,name){
 const url=URL.createObjectURL(new Blob(parts,{type}));
 const link=document.createElement('a');
 link.href=url;link.download=name;link.click();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function fields(row,growth,returns){
 const fib=row.daily_pullback||{};
 const m=row.metrics||{},p=row.plan||{},rs=row.sector_strength?.windows||{},stock=row.relative_strength?.windows||{};
 return {
  Symbol:row.symbol,Company:row.name,Sector:row.sector,'Market bar':row.market_bar_at,
  'Price (INR)':row.price,'Reported ATH (INR)':row.reported_ath,'Below ATH (%)':row.distance_pct,
  '6M return (%)':returns(row,'6'),'12M return (%)':returns(row,'12'),
  '6M CAGR (%)':growth(row,'6'),'12M CAGR (%)':growth(row,'12'),
  'Rule assessment':row.rule_status,'Market cap (INR crore)':row.market_cap_crore,'Turnover (INR crore)':row.turnover_crore,
  'ROE (%)':m.return_on_equity,'P/E':m.price_earnings_ttm,'Revenue growth (%)':m.total_revenue_yoy_growth_ttm,
  'Diluted EPS growth (%)':m.earnings_per_share_diluted_yoy_growth_ttm,
  'Sector strength':row.sector_strength?.status,'6M sector RS (pp)':rs['6m']?.excess_pp,'12M sector RS (pp)':rs['12m']?.excess_pp,
  '6M stock RS (pp)':stock['6m'],'12M stock RS (pp)':stock['12m'],
  'Daily Fib 50% (INR)':fib.price_50,'Daily Fib 56% (INR)':fib.price_56,
  'Daily swing low (INR)':fib.swing_low,'Daily swing low date':fib.swing_low_date,
  'Daily swing high (INR)':fib.swing_high,'Daily swing high date':fib.swing_high_date,'Daily swing high status':fib.swing_high_status,
  'Daily data through':fib.as_of,
  'Daily Fib availability':fib.reason,
  'Plan status':p.status,'ATH breakout entry (INR)':p.entry,'Stop-loss (INR)':p.stoploss,'Target (INR)':p.target,'Reward / risk':p.reward_risk,
  'AI assessment':row.ai?.classification,'AI rationale':row.ai?.rationale,
  'AI risks':row.ai?.risks?.join('\n'),'AI evidence needed':row.ai?.evidence_needed?.join('\n'),
  'Rule checks':row.checks?.map(check=>check.name+' — '+(check.passed?'Pass':'Failed or unavailable')).join('\n'),
  'Missing evidence':row.missing?.join('\n'),
  ...Object.fromEntries(Array.from({length:10},(_,index)=>{
   const years=index+1,period=years+'y',window=row.annual_returns?.[years];
   return [[years+'Y return (%)',returns(row,period)],[years+'Y CAGR (%)',growth(row,period)],
    [years+'Y start',window?.from_date],[years+'Y end',window?.to_date]];
  }).flat()),
 };
}
const xml=value=>String(value).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\uFFFE\uFFFF]/g,'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
// XLSX is an OPC ZIP container. These entries use ZIP's stored method.
function zip(files){
 const encoder=new TextEncoder(),parts=[],directory=[];
 let offset=0,size=0;
 for(const [name,content] of Object.entries(files)){
  const path=encoder.encode(name),data=encoder.encode(content);
  let crc=-1;
  for(const byte of data){
   crc^=byte;
   for(let bit=0;bit<8;bit++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);
  }
  const local=new DataView(new ArrayBuffer(30)),central=new DataView(new ArrayBuffer(46));
  local.setUint32(0,0x04034b50,true);central.setUint32(0,0x02014b50,true);central.setUint16(4,20,true);
  for(const [view,base] of [[local,4],[central,6]]){
   view.setUint16(base,20,true);
   view.setUint16(base+8,33,true); // 1980-01-01
   view.setUint32(base+10,~crc,true);
   view.setUint32(base+14,data.length,true);view.setUint32(base+18,data.length,true);
   view.setUint16(base+22,path.length,true);
  }
  central.setUint32(42,offset,true);
  parts.push(local.buffer,path,data);directory.push(central.buffer,path);
  offset+=30+path.length+data.length;size+=46+path.length;
 }
 const end=new DataView(new ArrayBuffer(22)),count=Object.keys(files).length;
 end.setUint32(0,0x06054b50,true);end.setUint16(8,count,true);end.setUint16(10,count,true);
 end.setUint32(12,size,true);end.setUint32(16,offset,true);
 return [...parts,...directory,end.buffer];
}
function workbook(rows,growth,returns){
 if(!rows.length)return;
 const records=rows.map(row=>fields(row,growth,returns));
 const ns='http://schemas.openxmlformats.org',main=ns+'/spreadsheetml/2006/main',rel=ns+'/officeDocument/2006/relationships';
 const content=[Object.keys(records[0]),...records.map(Object.values)].map((row,index)=>{
  const cells=row.map((value,column)=>{
   let letters='';
   for(let n=column+1;n>0;n=Math.floor((n-1)/26))letters=String.fromCharCode(65+(n-1)%26)+letters;
   const address=letters+(index+1);
   const cell='<c r="'+address+'"';
   return Number.isFinite(value)?cell+' s="2"><v>'+value+'</v></c>':cell+(index===0?' s="1"':'')+' t="inlineStr"><is><t xml:space="preserve">'+xml(value??'Unavailable')+'</t></is></c>';
  });
  return '<row r="'+(index+1)+'">'+cells.join('')+'</row>';
 }).join('');
 download(zip({
  '[Content_Types].xml':'<Types xmlns="'+ns+'/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
  '_rels/.rels':'<Relationships xmlns="'+ns+'/package/2006/relationships"><Relationship Id="rId1" Type="'+rel+'/officeDocument" Target="xl/workbook.xml"/></Relationships>',
  'xl/workbook.xml':'<workbook xmlns="'+main+'" xmlns:r="'+rel+'"><sheets><sheet name="Investment" sheetId="1" r:id="rId1"/></sheets></workbook>',
  'xl/_rels/workbook.xml.rels':'<Relationships xmlns="'+ns+'/package/2006/relationships"><Relationship Id="rId1" Type="'+rel+'/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="'+rel+'/styles" Target="styles.xml"/></Relationships>',
  'xl/styles.xml':'<styleSheet xmlns="'+main+'"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
  'xl/worksheets/sheet1.xml':'<worksheet xmlns="'+main+'"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="22" customWidth="1"/><col min="2" max="2" width="32" customWidth="1"/><col min="3" max="'+Object.keys(records[0]).length+'" width="25" customWidth="1"/></cols><sheetData>'+content+'</sheetData></worksheet>',
 }),mime,'investment-selected.xlsx');
}
const rtf=value=>String(value??'').replace(/[\\{}\r\n\u0080-\uFFFF]/g,c=>{
 if(c==='\r')return '';
 if(c==='\n')return '\\line ';
 if(c.charCodeAt(0)<128)return '\\'+c;
 return '\\u'+((c.charCodeAt(0)<<16)>>16)+'?';
});
const line=value=>'\\pard\\sa85 '+rtf(value)+'\\par\n';
const heading=value=>'\\pard\\keepn\\sb180\\sa90\\b '+rtf(value)+'\\b0\\par\n';
function chart(title,items,min,max,paint,unit){
 const canvas=document.createElement('canvas');canvas.width=900;canvas.height=380;
 const ctx=canvas.getContext('2d');
 if(!ctx)return '';
 const left=85,right=875,top=55,bottom=325,step=(right-left)/items.length;
 const spread=max-min||1,y=v=>bottom-(bottom-top)*(v-min)/spread;
 ctx.fillStyle='#ffffff';ctx.fillRect(0,0,900,380);
 ctx.fillStyle='#102238';ctx.font='bold 23px sans-serif';ctx.fillText(title,left,34);
 ctx.font='14px sans-serif';
 for(let i=0;i<=4;i++){
  const value=min+spread*i/4,axis=y(value);
  ctx.fillStyle='#d9e1e8';ctx.fillRect(left,axis,right-left,1);
  ctx.fillStyle='#42546a';ctx.fillText(format.format(value)+unit,5,axis+4);
 }
 items.forEach((item,i)=>paint(ctx,item,left+step*(i+.5),step,y));
 ctx.fillStyle='#42546a';
 if(items.length>12){
  ctx.fillText(items[0].label,left,350);
  ctx.textAlign='right';ctx.fillText(items.at(-1).label,right,350);
 }else{
  ctx.textAlign='center';items.forEach((item,i)=>ctx.fillText(item.label,left+step*(i+.5),350));
 }
 const binary=atob(canvas.toDataURL('image/png').split(',')[1]);
 const hex=Array.from(binary,c=>c.charCodeAt(0).toString(16).padStart(2,'0')).join('');
 return '{\\pict\\pngblip\\picw900\\pich380\\picwgoal9000\\pichgoal3800\n'+hex.match(/.{1,120}/g).join('\n')+'}\\par\n';
}
async function report(row,output,paragraphs,period,growth,returns){
 const report=['{\\rtf1\\ansi\\uc1\\deff0{\\fonttbl{\\f0 Calibri;}}\\paperw12240\\paperh15840\\margl1080\\margr1080\\f0\\fs22\n',
  heading('Investment analysis · '+row.symbol),line('Captured '+show(output.created_at)),line('Active return period · '+(period.endsWith('y')?period.slice(0,-1)+' years':period+' months')),
  ...Object.entries(fields(row,growth,returns)).map(([label,value])=>line(label+' · '+show(value))),
  heading('Analysis and sources'),...paragraphs.map(line),
  ...[row.plan?.reason,output.ai_summary||output.ai_message].filter(Boolean).map(line),
  ...Object.entries(output.policy||{}).map(([key,value])=>line(key.replaceAll('_',' ')+' · '+show(value))),
  ...(output.limitations||[]).map(line),
 ];
 let history,error;
 try{
  const headers={'Content-Type':'application/json'};
  if(window.SectorPulseWorkspace?.csrf)headers['X-CSRF-Token']=window.SectorPulseWorkspace.csrf;
  const response=await fetch('/api/investment/seasonality/analyze',{method:'POST',headers,body:JSON.stringify({symbol:row.symbol})});
  const value=await response.json();
  if(!response.ok||value.schema!=='seasonality/v1')throw Error(value.error||'Completed history was unavailable.');
  history=value;
 }catch(failure){error=failure.message;}
 report.push(heading('Seasonality'));
 const monthly=history?.modes?.Monthly;
 const labels=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
 const months=labels.map((label,i)=>({label,value:monthly?.statistics?.find(stat=>stat.slot===i+1)?.average}));
 const averages=months.map(month=>month.value).filter(Number.isFinite);
 if(averages.length){
  const image=chart('Average monthly price returns',months,Math.min(0,...averages),Math.max(0,...averages),(ctx,item,x,step,y)=>{
   if(!Number.isFinite(item.value))return;
   ctx.fillStyle=item.value>=0?'#167c61':'#b34045';
   ctx.fillRect(x-step*.28,Math.min(y(0),y(item.value)),step*.56,Math.max(1,Math.abs(y(0)-y(item.value))));
  },'%');
  report.push(image||line('Seasonality image unavailable.'),line(months.map(month=>month.label+' '+show(month.value)).join(' · ')));
 }else report.push(line('Seasonality chart unavailable. '+(error||'No closed monthly return periods.')));
 if(history){
  report.push(line([history.source,history.daily_from,history.daily_to,history.price_basis,history.source_url].filter(Boolean).join(' · ')),
   line(history.method),...(history.limitations||[]).map(line));
  for(const [mode,data] of Object.entries(history.modes||{})){
   report.push(heading(mode+' historical returns (%)'),line('Net return · '+show(data.net_return)+' | CAGR · '+show(data.annualized_return)),
    ...(data.years||[]).map(year=>line(year.year+' · '+year.samples+'/'+year.expected+' periods | Net '+show(year.net_return)+' | '+year.periods.map(p=>p.slot+' '+show(p.value)).join(' · '))),
    ...(data.statistics||[]).map(stat=>line('Period '+stat.slot+' · Average '+show(stat.average)+' | Positive '+stat.positive+'/'+stat.samples+' | Win rate '+show(stat.win_rate))));
  }
 }
 report.push(heading('Trading chart · daily candlesticks'));
 const bars=(history?.chart?.candles||[]).slice(-90).map(bar=>({...bar,label:String(bar.time)}));
 if(bars.length){
  const image=chart('Completed daily price bars',bars,Math.min(...bars.map(b=>b.low)),Math.max(...bars.map(b=>b.high)),(ctx,bar,x,step,y)=>{
   ctx.fillStyle=bar.close>=bar.open?'#167c61':'#b34045';
   ctx.fillRect(x-.75,y(bar.high),1.5,Math.max(1,y(bar.low)-y(bar.high)));
   ctx.fillRect(x-step*.28,Math.min(y(bar.open),y(bar.close)),step*.56,Math.max(1,Math.abs(y(bar.open)-y(bar.close))));
  },'');
  report.push(image||line('Candlestick image unavailable.'),line(history.chart.basis),line('Date | Open | High | Low | Close'),
   ...bars.map(bar=>line([bar.label,bar.open,bar.high,bar.low,bar.close].map(show).join(' | '))));
 }else report.push(line('Candlestick chart unavailable. '+(history?.chart_unavailable_reason||error||'No completed daily candles.')));
 download([...report,'}'],'application/rtf','investment-'+row.symbol.replace(/[^a-z0-9_-]/gi,'_')+'.rtf');
}
window.SectorPulseInvestmentExports={workbook,report};
})();
