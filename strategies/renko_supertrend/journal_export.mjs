import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const [source, output, preview] = process.argv.slice(2);
const data = JSON.parse(await fs.readFile(source, 'utf8'));
const trades = data.trades || [];
const wb = Workbook.create();
const names = ['Executive summary','Trades','Indicators','Order events','Costs','Position ranges'];
const sheets = names.map(n => wb.worksheets.add(n));
const navy='#172C46', muted='#64748B', green='#16805D', red='#BB3748';
const native=data.broker==='DELTA_INDIA';
const currency=native?(data.pnl_currency||trades[0]?.quote_currency||'native currency'):'INR';
const money=native?'"'+currency+'" #,##0.00;("'+currency+'" #,##0.00);"'+currency+'" –':'"₹" #,##0.00;("₹" #,##0.00);"₹" –';
const known = x => typeof x==='number' && Number.isFinite(x);
const cell = x => x==null ? 'n.a.' : typeof x==='string' && /^[=+@-]/.test(x) ? "'"+x : x;
const date = x => known(x) ? (x+19800)/86400+25569 : 'n.a.';
const join = x => Array.isArray(x) ? x.join(', ') : 'n.a.';
function setup(s,title,subtitle,width=16){
  s.showGridLines=false;
  s.getRange('A1:AN2000').format={font:{name:'Arial',size:11,color:navy},columnWidth:width,rowHeight:22};
  s.getRange('B2').values=[[title]];s.getRange('B2').format={font:{size:18,bold:true},rowHeight:32};
  s.getRange('B3').values=[[subtitle]];s.getRange('B3').format={font:{size:10,color:muted},rowHeight:25};
  s.freezePanes.freezeRows(6);s.freezePanes.freezeColumns(3);
}
function table(s,headers,rows,id){
  const count=Math.max(1,rows.length);
  const range=s.getRangeByIndexes(5,1,count+1,headers.length);
  range.values=[headers,...(rows.length?rows: [headers.map((_,i)=>i===0?'No recorded trades':'')])];
  const t=s.tables.add(range,true,id);t.style='TableStyleLight1';t.showFilterButton=true;
  s.getRangeByIndexes(5,1,1,headers.length).format={fill:navy,font:{color:'#FFFFFF',bold:true},wrapText:true,rowHeight:44};
  s.getRangeByIndexes(6,1,count,headers.length).format={rowHeight:48,wrapText:true,verticalAlignment:'center'};
  return count;
}
function pnlFormat(s,range){
  const r=s.getRange(range);r.setNumberFormat(money);
  r.conditionalFormats.add('cellIs',{operator:'greaterThan',formula:0,format:{font:{color:green}}});
  r.conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{font:{color:red}}});
}
setup(sheets[0],'RENKO SUPERTREND | Trading journal','Board review · Owned option fills · Gross and estimated net P&L · '+currency+' · IST');
setup(sheets[1],'Option trade register','Actual broker-confirmed Live fills and simulated Paper fills; chart signals excluded.');
setup(sheets[2],'Saved strategy evidence','Immutable entry / exit snapshots. Missing historical values remain unavailable.');
setup(sheets[3],'Order and reconciliation audit','Broker and Paper IDs, partial fills, status changes, and recorded execution evidence.');
setup(sheets[4],'Gross and net option P&L',native?'Delta native currency · recorded commissions in order evidence · complete tax/liquidation costs unavailable; no FYERS fee estimate.':'Estimates · ₹15 per executed order · Additional slippage separately configured · Broker contract notes not reconciled.');
setup(sheets[5],'Intra-position ranges and quick-loss locks','Underlying ticks during actual exposure only · No pre-entry swings · 3 host candles touched by default · After-cost loss.');
const rows=trades.map(t=>[
  t.mode,t.trade_id,t.contract,t.option_type,t.strike,date(t.expiry_epoch),t.status,date(t.entry_time),date(t.end_time),
  t.entry_filled,t.exit_filled,t.remaining_quantity,t.entry_price,t.exit_price,t.spot_entry,t.spot_exit,t.realized_pnl,t.unrealized_pnl,
  t.quantity_multiplier,t.entry_requested,t.exit_requested,t.run_id,join(t.entry_order_ids),join(t.exit_order_ids),join(t.exit_reasons),
  t.pnl_basis,t.spot_basis,t.matched_quantity,t.realized_pnl,
  t.lots,t.entry_side,join(t.entry_reasons),t.spot_target,t.spot_stop,t.trailing_enabled,t.trailing_mode,t.trailing_step,t.valuation?.bid,date(t.valuation?.exchange_at),date(t.valuation?.observed_at),t.ema_exit_enabled,t.ema_exit_length
].map(cell));
const count=table(sheets[1],['Mode','Trade ID','Option contract','Type','Strike','Expiry · IST','Status','Entry fill · IST','End fill · IST','Entry filled','Exit filled','Remaining','Entry premium','Exit premium','Underlying entry','Underlying exit','Realized P&L','Open P&L','Multiplier','Entry requested','Exit requested','Run ID','Entry order IDs','Exit order IDs','Exit reasons','P&L basis','Underlying basis','Matched quantity','Recorded realized P&L','Filled lots','Entry side','Entry reasons','Configured spot target','Configured spot stop','Trailing enabled','Trailing mode','Trailing step','Executable option bid','Quote exchange · IST','Valuation observed · IST','EMA exit enabled','Exit EMA period'],rows,'RenkoTrades');
const end=6+count;
for (let i=0;i<trades.length;i++){
  const r=i+7;
  // Do not turn incomplete or legacy fill records into invented performance.
  sheets[1].getRange(`R${r}`).formulas=[[`=IF(ISNUMBER(AD${r}),IF(AND(ISNUMBER(N${r}),ISNUMBER(O${r}),ISNUMBER(T${r}),ISNUMBER(AC${r}),AC${r}>0,T${r}>0),(O${r}-N${r})*AC${r}*T${r},"n.a."),"n.a.")`]];
}
for(const range of [`G7:G${end}`,`I7:J${end}`])sheets[1].getRange(range).setNumberFormat('dd-mmm-yyyy hh:mm');
pnlFormat(sheets[1],`R7:S${end}`);sheets[1].getRange(`N7:Q${end}`).setNumberFormat('0.00');
sheets[1].getRange('C:C').format.columnWidth=35;sheets[1].getRange('D:D').format.columnWidth=32;
sheets[1].getRange('I:J').format.columnWidth=25;sheets[1].getRange('X:AB').format.columnWidth=40;
const indicatorRows=[];const orderRows=[];
for(const t of trades){
  const snapshots=[['ENTRY',t.entry_indicator_snapshot],...(t.exit_indicator_snapshots||[]).map(s=>['EXIT',s])];
  for(const [kind,s] of snapshots){const v=s?.indicators||{}, cfg=s?.settings||{};
    indicatorRows.push([t.mode,t.trade_id,kind,date(s?.captured_at),s?.reason,s?.settings_revision,date(s?.initialization_anchor),
      v.close,v.ema10,v.ema30,v.ema_gap,v.supertrend,v.box,v.adx,cfg.atr_length,cfg.factor,cfg.brick_mode,cfg.manual_brick,cfg.use_adx,cfg.widening_window,
      s?JSON.stringify(s):'Unavailable in original journal'].map(cell));
  }
  for(const o of t.orders||[]){
    const events=o.reconciliation_events?.length?o.reconciliation_events:[{}];
    for(const e of events)orderRows.push([t.mode,t.trade_id,t.run_id,o.order_id||o.paper_order_id,o.symbol,o.side,date(o.submitted_at),date(o.first_fill_confirmed_at),date(e.at),e.status??o.status,e.filled??o.filled,e.remaining??o.remaining,e.average_price??o.average_price,o.requested,o.reason,JSON.stringify({order:o,reconciliation:e})].map(cell));
  }
}
const ic=table(sheets[2],['Mode','Trade ID','Event','Captured · IST','Reason','Revision','History anchor','Host close','EMA 10','EMA 30','EMA gap','Supertrend','Brick size','ADX','ATR length','Factor','Brick mode','Manual brick','ADX enabled','Widening window','Complete saved evidence'],indicatorRows,'RenkoIndicators');
sheets[2].getRange(`E7:E${6+ic}`).setNumberFormat('dd-mmm-yyyy hh:mm');sheets[2].getRange(`H7:H${6+ic}`).setNumberFormat('dd-mmm-yyyy hh:mm');sheets[2].getRange('C:C').format.columnWidth=38;sheets[2].getRange('E:H').format.columnWidth=28;sheets[2].getRange('I:U').setNumberFormat('0.00');sheets[2].getRange('V:V').format.columnWidth=80;
const oc=table(sheets[3],['Mode','Trade ID','Run ID','Order ID','Contract','Side','Submitted · IST','First fill · IST','Reconciled · IST','Status','Filled','Remaining','Average premium','Requested','Reason','Complete order evidence'],orderRows,'RenkoOrderEvents');
sheets[3].getRange(`H7:J${6+oc}`).setNumberFormat('dd-mmm-yyyy hh:mm');sheets[3].getRange('C:F').format.columnWidth=32;sheets[3].getRange('Q:Q').format.columnWidth=80;
const costRows=trades.map(t=>{const c=t.costs||{},i=c.incurred||{};return [t.mode,t.trade_id,t.exit_filled?t.realized_pnl:0,c.available?(c.entry_costs_allocated_realized+c.exit_costs_incurred):null,c.realized_additional_slippage,c.realized_net,t.remaining_quantity?t.unrealized_pnl:0,c.entry_costs_remaining,c.estimated_exit_costs?.total??(t.remaining_quantity?null:0),c.open_liquidation_additional_slippage,c.unrealized_net,i.brokerage,i.exchange,i.sebi,i.stt,i.stamp,i.gst,i.total,c.kind,JSON.stringify(c)].map(cell);});
const cc=table(sheets[4],['Mode','Trade ID','Gross realized','Realized allocated charges','Additional realized slippage','Net realized · estimate','Gross open','Entry costs remaining','Estimated exit costs','Additional open slippage','Net liquidation · estimate','Brokerage','Exchange','SEBI','STT','Stamp','GST','Total incurred','Cost evidence type','Complete assumptions / rates / sources'],costRows,'RenkoCosts');
for(let i=0;i<trades.length;i++){const r=i+7,c=trades[i].costs||{};
 if(c.realized_net!=null)sheets[4].getRange(`G${r}`).formulas=[[`=D${r}-E${r}-F${r}`]];
 if(c.unrealized_net!=null)sheets[4].getRange(`L${r}`).formulas=[[`=H${r}-I${r}-J${r}-K${r}`]];
}
sheets[4].getRange(`D7:S${6+cc}`).setNumberFormat(money);sheets[4].getRange('C:C').format.columnWidth=40;sheets[4].getRange('D:S').format.columnWidth=23;sheets[4].getRange('T:U').format.columnWidth=65;pnlFormat(sheets[4],`G7:G${6+cc}`);pnlFormat(sheets[4],`L7:L${6+cc}`);
const rangeRows=trades.map(t=>[t.mode,t.trade_id,t.exposure_range?.high,t.exposure_range?.low,date(t.exposure_range?.entry_at),date(t.end_time),t.exposure_host_candles,t.costs?.realized_net,t.sideways_lock_trigger?.reason,date(t.sideways_lock_trigger?.triggered_at),t.sideways_lock_release?.release_reason,date(t.sideways_lock_release?.released_at),JSON.stringify({range:t.exposure_range,trigger:t.sideways_lock_trigger,release:t.sideways_lock_release})].map(cell));
const rc=table(sheets[5],['Mode','Trade ID','Position high','Position low','Exposure begins · IST','Final exit · IST','Host candles touched','Net loss basis · estimate','Lock trigger','Triggered · IST','Release reason','Released · IST','Complete range evidence'],rangeRows,'RenkoPositionRanges');
sheets[5].getRange('C:C').format.columnWidth=40;sheets[5].getRange('J:N').format.columnWidth=32;sheets[5].getRange('N:N').format.columnWidth=80;
for(const col of ['F','G','K','M'])sheets[5].getRange(`${col}7:${col}${6+rc}`).setNumberFormat('dd-mmm-yyyy hh:mm:ss');
const summary=sheets[0];summary.getRange('B5').values=[['Report generated · IST']];summary.getRange('E5').values=[[date(data.exported_at)]];summary.getRange('E5').setNumberFormat('dd-mmm-yyyy hh:mm');
summary.getRange('B7:H7').values=[['Execution mode','Recorded trades','Closed trades','Gross realized','Gross open','Net realized · estimate','Net liquidation · estimate']];
summary.getRange('B7:H7').format={fill:navy,font:{bold:true,color:'#FFFFFF'},rowHeight:36,wrapText:true};
for(const [i,mode]of ['LIVE','PAPER'].entries()){
 const r=i+8, items=trades.filter(t=>t.mode===mode), realized=items.filter(t=>t.exit_filled>0),open=items.filter(t=>t.remaining_quantity>0);
 summary.getRange(`B${r}:D${r}`).values=[[mode,items.filter(t=>t.entry_filled>0).length,items.filter(t=>t.status==='CLOSED'&&t.entry_filled>0).length]];
 summary.getRange(`E${r}`).formulas=[[realized.length&&realized.every(t=>known(t.realized_pnl))?`=SUMIF('Trades'!B7:B${end},B${r},'Trades'!R7:R${end})`:'="n.a."']];
 summary.getRange(`F${r}`).formulas=[[items.some(t=>t.entry_filled>0)&&open.every(t=>known(t.unrealized_pnl))?`=SUMIF('Trades'!B7:B${end},B${r},'Trades'!S7:S${end})`:'="n.a."']];
 summary.getRange(`G${r}`).formulas=[[items.length&&items.every(t=>t.costs?.realized_net!=null)?`=SUMIF('Costs'!B7:B${6+cc},B${r},'Costs'!G7:G${6+cc})`:'="n.a."']];
 summary.getRange(`H${r}`).formulas=[[items.length&&items.every(t=>t.costs?.unrealized_net!=null)?`=SUMIF('Costs'!B7:B${6+cc},B${r},'Costs'!L7:L${6+cc})`:'="n.a."']];
}
pnlFormat(summary,'E8:H9');summary.getRange('B8:H9').format.rowHeight=38;summary.getRange('B:H').format.columnWidth=23;
summary.getRange('C8:H9').format.horizontalAlignment='center';
summary.getRange('B12').values=[[trades.length?'Fill evidence available in Trades; strategy decisions in Indicators; broker changes in Order events.':'No recorded option trades. Performance metrics are unavailable.']];
summary.getRange('B14').values=[['READING THIS REPORT']];summary.getRange('B14').format.font.bold=true;
const notes=[
 'Live and Paper results remain separate. This workbook is a static snapshot at export time.',
 'P&L uses actual option premium fills and filled quantity; open P&L uses an executable option bid.',
 'Gross excludes charges; net includes estimated brokerage/statutory charges and configured additional slippage. Unavailable evidence is shown as n.a.',
 'Underlying values are observations at local fill confirmation, not exact exchange-fill spot prices.',
 'Historical chart entry / exit simulations are excluded from trading performance.',
 'Runner P&L on the dashboard is per run; this workbook covers the durable trade register.',
 native?'Delta costs require native commission/tax evidence. Unknown costs remain unavailable; no INR conversion or FYERS rates.':'Costs uses ₹15 per executed BUY/SELL; statutory rounding is estimated at runner-only day level.',
 'Live fee estimates are not broker-confirmed charges. Extra slippage defaults to zero; actual fill slippage is embedded.',
 'Costs and Position ranges preserve charge assumptions and actual exposure evidence; missing old extrema stay n.a.'
];notes.forEach((v,i)=>{summary.getRange(`B${16+i}`).values=[[v]];summary.getRange(`B${16+i}:G${16+i}`).merge();summary.getRange(`B${16+i}:G${16+i}`).format={wrapText:true,rowHeight:34,font:{size:11,color:muted}};});
// Apply cell formats after all column and row layout edits.
summary.getRange('E8:H9').setNumberFormat(money);
sheets[1].getRange(`G7:G${end}`).setNumberFormat('dd-mmm-yyyy');
sheets[1].getRange(`I7:J${end}`).setNumberFormat('dd-mmm-yyyy hh:mm');
sheets[1].getRange(`N7:Q${end}`).setNumberFormat('0.00');
sheets[1].getRange(`R7:S${end}`).setNumberFormat(money);
sheets[2].getRange(`E7:E${6+ic}`).setNumberFormat('dd-mmm-yyyy hh:mm');
sheets[2].getRange(`H7:H${6+ic}`).setNumberFormat('dd-mmm-yyyy hh:mm');
sheets[2].getRange(`I7:O${6+ic}`).setNumberFormat('0.00');
sheets[3].getRange(`H7:J${6+oc}`).setNumberFormat('dd-mmm-yyyy hh:mm');
sheets[3].getRange(`N7:N${6+oc}`).setNumberFormat('0.00');
sheets[1].getRange(`AN7:AO${end}`).setNumberFormat('dd-mmm-yyyy hh:mm:ss');
sheets[1].getRange('AF:AF').format.columnWidth=38;
sheets[1].getRange('AN:AO').format.columnWidth=27;
wb.recalculate();
if(preview){await fs.mkdir(preview,{recursive:true});for(let i=0;i<sheets.length;i++){const img=await wb.render({sheetName:names[i],range:i?'B2:J12':'B2:H25',scale:1.5,format:'png'});await fs.writeFile(`${preview}/${i+1}.png`,new Uint8Array(await img.arrayBuffer()));}await fs.writeFile(`${preview}/inspection.txt`,String(await wb.inspect({kind:'table',range:'Executive summary!B7:F9',include:'values,formulas',tableMaxRows:4,maxChars:3000})));}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(output);
