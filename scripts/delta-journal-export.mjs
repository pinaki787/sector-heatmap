import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
import './delta-journal.js';
const [inputPath,outputPath,previewPrefix]=process.argv.slice(2);
const input=JSON.parse(await fs.readFile(inputPath,'utf8'));
const events=(globalThis.DeltaJournalRows||globalThis.window?.DeltaJournalRows)(input),wb=Workbook.create();
const date=t=>Number.isFinite(Number(t))&&t!=null?(Math.floor(Number(t))+19800)/86400+25569:'Not recorded';
const value=v=>v==null?'Not recorded':typeof v==='string'&&/^[=+@]/.test(v)?"'"+v:v;
const summaries=[];
for(const t of input.state.paper?.trades||[]){const e=events.find(r=>r.workflow==='PAPER'&&r.event==='ENTRY'&&r.id===(t.lifecycle_id||t.id));summaries.push([t.lifecycle_id||t.id,'PAPER',t.symbol,e?.strike,t.side,t.status,date(t.entry_time),date(t.exit_time),t.contracts,t.entry_price,t.exit_price,t.quote_currency,e?.native_value,e?.inr_rate,e?.inr_equivalent,t.realized_pnl,t.entry_reason||'Not recorded',e?.value_basis,e?.evidence,e?.inr_basis]);}
for(const o of input.state.orders||[]){const e=events.find(r=>r.workflow==='LIVE'&&r.id?.startsWith(o.request_id)),amount=e?.contract_value!=null&&o.average_fill_price!=null?Number(o.filled_contracts)*Number(o.average_fill_price)*e.contract_value:null;summaries.push([o.request_id,'LIVE',o.symbol,e?.strike,o.request?.side,o.status,date(o.created_at),date(o.updated_at),o.filled_contracts,o.average_fill_price,null,e?.currency,amount,e?.inr_rate,e?.currency==='USD'&&amount!=null&&e?.inr_rate!=null?amount*e.inr_rate:null,null,o.event_context?.reason||o.execution_reason,e?.value_basis,e?.evidence,'Actual fills and timestamps on Evidence sheet']);}
const summaryHeaders=['Trade / order ID','Workflow','Contract','Option strike','Side','Status','Entry / request time IST','Exit / observation time IST','Filled quantity','Entry / order average','Exit average','Native currency','Entry premium / notional','INR per USD','INR equivalent','Realized P&L native','Entry / order reason','Value basis','Evidence status','Conversion / timing basis'];
const fields=['id','workflow','event','symbol','strike','side','time','quantity','fill_price','currency','status','underlying','timeframe','candle_time','candle_completed','open','high','low','close','rsi_length','rsi','ma_type','ma_length','rsi_ma','bb_length','bb_deviation','bb_upper','bb_middle','bb_lower','bb_basis','transition','signal_price','reversal_price','reason','observed_at','evidence','price_basis','native_value','inr_rate','inr_equivalent','inr_source','inr_verified_at','inr_basis','unavailable','context_json'];
const headers=['Event ID','Workflow','Event','Traded contract','Option strike','Side','Actual fill / observation time IST','Fill / snapshot qty','Actual fill / average price','Native currency','Status','Underlying signal contract','Timeframe','Candle opening time IST','Completed candle','Candle open','Candle high','Candle low','Candle close','RSI length','RSI value','RSI MA type','RSI MA length','RSI MA value','BB length','BB deviation sigma','BB upper','BB middle SMA','BB lower','BB calculation basis','Transition','Signal candle close price','Reversal candle close price','Reason','Context observed time IST','Capture kind','Price basis','Premium / notional native','INR per USD','INR equivalent','Conversion source','Conversion verified time IST','Conversion basis','Unavailable reason','Full recorded context (includes forming candle / touch evidence)'];
const evidence=events.map(r=>fields.map(k=>['time','candle_time','observed_at','inr_verified_at'].includes(k)?date(r[k]):value(r[k])));
const sheets=[['Summary',summaryHeaders,summaries],['Evidence',headers,evidence]];
for(const [name,columns,rows] of sheets){
 const sh=wb.worksheets.add(name),width=columns.length,count=Math.max(rows.length,1);sh.showGridLines=false;
 sh.getRange('A2').values=[['Delta India trading journal — '+name]];sh.getRange('A2').format.font={name:'Arial',size:14,bold:true};
 sh.getRange('A3').values=[['Times: IST. Legacy indicators: not recorded. Native USD retained. INR uses cited fixed Delta platform policy, not market FX.']];sh.getRange('A3').format.font={name:'Arial',size:10,italic:true};
 sh.getRangeByIndexes(4,0,1,width).values=[columns];
 sh.getRangeByIndexes(5,0,count,width).values=rows.length?rows.map(r=>r.map(value)):[columns.map((_,i)=>i===0?'No recorded events':null)];
 const region=sh.getRangeByIndexes(4,0,count+1,width);region.format.font={name:'Arial',size:10};region.format.rowHeight=28;region.format.columnWidth=19;region.format.verticalAlignment='center';
 sh.getRangeByIndexes(4,0,1,width).format={fill:'#243C56',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:52,horizontalAlignment:'center'};
 sh.getRangeByIndexes(5,0,count,width).setNumberFormat('#,##0.0000;[Red](#,##0.0000);0.0000');
 const whole=name==='Summary'?[8]:[7,19,22,24];for(const index of whole)sh.getRangeByIndexes(5,index,count,1).setNumberFormat('#,##0');
 const dates=name==='Summary'?[6,7]:[6,13,34,41];for(const index of dates)sh.getRangeByIndexes(5,index,count,1).setNumberFormat('dd-mmm-yyyy hh:mm:ss');
 const table=sh.tables.add(sh.getRangeByIndexes(4,0,count+1,width),true,name+'Events');table.showFilterButton=true;
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(3);sh.getRangeByIndexes(4,0,count+1,1).format.columnWidth=name==='Evidence'?55:38;sh.getRangeByIndexes(4,2,count+1,1).format.columnWidth=29;
 const textColumns=name==='Summary'?[[16,35],[17,45],[18,35],[19,65]]:[[29,45],[30,30],[33,35],[35,40],[36,45],[40,65],[42,65],[43,45],[44,100]];
 for(const [index,columnWidth] of textColumns){const cells=sh.getRangeByIndexes(4,index,count+1,1);cells.format.columnWidth=columnWidth;cells.format.wrapText=true;}
 sh.getRangeByIndexes(5,0,count,width).format.rowHeight=72;
 if(name==='Summary'){
  const pnl=sh.getRangeByIndexes(5,15,count,1);pnl.setNumberFormat('+#,##0.0000;[Red]-#,##0.0000;0.0000');
  pnl.conditionalFormats.addCustom('AND($F6="CLOSED",ISNUMBER($P6),$P6>0)',{fill:'#E2F3E9',font:{color:'#146B3A',bold:true}});
  pnl.conditionalFormats.addCustom('AND($F6="CLOSED",ISNUMBER($P6),$P6<0)',{fill:'#FBE8E7',font:{color:'#9C2525',bold:true}});
 }
 if(name==='Summary')for(let i=0;i<rows.length;i++)if(typeof rows[i][12]==='number'&&typeof rows[i][13]==='number')sh.getCell(i+5,14).formulas=[[`=M${i+6}*N${i+6}`]];
}
wb.recalculate();
if(previewPrefix)for(const [name]of sheets){const preview=await wb.render({sheetName:name,range:name==='Summary'?'A2:H10':'A2:J12',scale:1.5,format:'png'});await fs.writeFile(previewPrefix+'-'+name+'.png',new Uint8Array(await preview.arrayBuffer()));}
if(previewPrefix){const preview=await wb.render({sheetName:'Summary',range:'I5:T12',scale:1.5,format:'png'});await fs.writeFile(previewPrefix+'-SummaryValues.png',new Uint8Array(await preview.arrayBuffer()));}
await (await SpreadsheetFile.exportXlsx(wb)).save(outputPath);
console.log(JSON.stringify({events:events.length,summaryRows:summaries.length,sheets:2}));
