const fs=require('fs'),crypto=require('crypto');
const [library,input,output]=process.argv.slice(2);require(library);
const rows=JSON.parse(fs.readFileSync(input)),bars=rows.map(r=>Object.fromEntries(['open','high','low','close'].map(k=>[k,+r[k]]))),c=bars.map(b=>b.close),i=globalThis.SectorPulseChartStudies.indicators;
const trix=i.TRIX.run(bars,c,18)[0],fisher=i.Fisher.run(bars,c,9);
function compare(values,key,tail){
 let max=0,total=0,n=0;for(let j=Math.max(1,rows.length-tail);j<rows.length;j++){
 const got=values[j],want=Number(rows[j][key]);
 if(rows[j][key]===''||!Number.isFinite(got)||!Number.isFinite(want))continue;
 const error=Math.abs(got-want);max=Math.max(max,error);total+=error;n++;}
 return {tail,n,max_error:max,mean_error:n?total/n:null};
}
const trixWindows=[50,75,100,150].map(n=>compare(trix,'TRIX',n)),fisherResult=compare(fisher[0],'Fisher',150),trigger=compare(fisher[1],'Trigger',150);
const report={status:trixWindows[1].max_error<1e-8&&fisherResult.max_error<1e-8&&trigger.max_error<1e-8?'PASS_TAIL_REFERENCE':'FAIL',completed_rows:rows.length,trix_tail_windows:trixWindows,fisher:fisherResult,trigger,last:{trix:trix.at(-1),native_trix:Number(rows.at(-1).TRIX)},library_sha256:crypto.createHash('sha256').update(fs.readFileSync(library)).digest('hex'),scope:'Same native-export OHLC. TRIX last75 compared after224cold-start bars; full earlier-history seed parity unproven. All tail error windows retained, including larger earlier transient errors. Fisher/trigger last150.'};
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));if(report.status==='FAIL')process.exitCode=1;
