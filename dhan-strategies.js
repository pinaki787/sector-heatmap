(function(){
'use strict';
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search),account=params.get('account_id');
let instance=params.get('instance')||'default',snapshot=null,preview=null;
$('strategy').value=['renko','band','kama'].includes(params.get('strategy'))?params.get('strategy'):'rsi';
function base(){return ({renko:'/api/renko-dhan/',rsi:'/api/ema-dhan/',band:'/api/band-dhan/',kama:'/api/kama-dhan/'}[$('strategy').value])+encodeURIComponent(account||'')+'/';}
async function request(action,body){
 if(!account)throw Error('Select your Dhan account in Broker accounts.');
 const response=await fetch(base()+action+'?instance='+encodeURIComponent(instance),body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,broker:'DHAN',account_id:account})}:{});
 const result=await response.json();if(!response.ok||result.error)throw Error(result.error||'Strategy request failed');return result;
}
function invalidate(){preview=null;$('preview').hidden=true;$('start').disabled=true;}
function payload(){return {strategy:({renko:'RENKO_SUPERTREND_V1',rsi:'RSI_BASED_EMA_V1',band:'EMA_BAND_V1',kama:'KAMA_V6'})[$('strategy').value],execution_route:'OPTIONS',
 ema_length:$('ema-length').value,slope_lookback:$('slope-lookback').value,minimum_slope_atr:$('minimum-slope-atr').value,
 kama_length:$('kama-length').value,fast_length:$('fast-length').value,slow_length:$('slow-length').value,
 minimum_efficiency:$('minimum-efficiency').value,breakout_bars:$('breakout-bars').value,cooldown_bars:$('cooldown-bars').value,allow_reclaims:$('allow-reclaims').checked,
 broker:'DHAN',account_id:account,underlying:$('underlying').value,timeframe:$('timeframe').value,
 mode:$('mode').value,lots:$('lots').value,max_trades:$('max-trades').value,
 max_premium:$('max-premium').value,daily_budget:$('daily-budget').value,
 paper_capital_inr:$('paper-capital').value,rsi_length:$('rsi-length').value,ma_type:$('ma-type').value,ma_length:$('ma-length').value,
 exit_policy:'OPPOSITE_CONFIRMED_SIGNAL',configuration_revision:snapshot?.runtime_revision};}
async function status(){
 const value=await request('runner');snapshot=value;$('status').textContent=value.status;
 $('message').textContent=value.message||value.error||'';$('position').textContent=JSON.stringify({position:value.position,pending:value.pending,pnl:value.pnl},null,2);
 $('stop').disabled=!(value.running||value.position||value.pending);return value;
}
async function bind(){
 const symbol=$('underlying').value;if(!symbol)throw Error('Select an exact underlying first.');
 const result=await request('create',{underlying:symbol});instance=result.instance_key;await status();
}
$('search').oninput=(()=>{let timer;return()=>{clearTimeout(timer);timer=setTimeout(async()=>{
 try{const response=await fetch(base()+'search?q='+encodeURIComponent($('search').value));const result=await response.json();
 if(!response.ok)throw Error(result.error||'Instrument search failed');$('underlying').replaceChildren();
 for(const row of result.matches||[]){const option=document.createElement('option');option.value=row.symbol;option.textContent=row.description+' · '+row.symbol;$('underlying').append(option);}
 invalidate();}catch(error){$('error').textContent=error.message;}
 },350);};})();
$('review').onclick=async()=>{try{$('error').textContent='';await bind();preview=await request('preview',payload());
 $('preview-details').textContent=JSON.stringify(preview.context,null,2)+'\n\nConfirmation: '+preview.confirmation;
 $('confirmation').value='';$('preview').hidden=false;}catch(error){$('error').textContent=error.message;}};
$('confirmation').oninput=()=>{$('start').disabled=!preview||$('confirmation').value!==preview.confirmation;};
$('start').onclick=async()=>{try{if(!preview||$('confirmation').value!==preview.confirmation)throw Error('Review a fresh activation first.');
 $('start').disabled=true;
 await request('start',$('strategy').value==='renko'?payload():{preview_id:preview.id,confirmation:$('confirmation').value});
 invalidate();await status();}catch(error){$('error').textContent=error.message;}};
$('stop').onclick=async()=>{try{await request('stop',{});await status();}catch(error){$('error').textContent=error.message;}};
for(const node of document.querySelectorAll('input,select'))if(node.id!=='confirmation')node.addEventListener('change',invalidate);
$('strategy').onchange=()=>{invalidate();instance='default';sync();status().catch(error=>{$('error').textContent=error.message;});};
function sync(){for(const kind of ['rsi','band','kama','indicator'])for(const node of document.querySelectorAll('.'+kind))node.hidden=kind==='indicator'?!['band','kama'].includes($('strategy').value):$('strategy').value!==kind;$('renko-link').hidden=$('strategy').value!=='renko';
 $('renko-link').querySelector('a').href='/?'+new URLSearchParams({renkoBroker:'DHAN',brokerAccount:account,renkoInstance:instance});}
async function init(){try{const response=await fetch('/api/workspaces/accounts');const value=await response.json();
 const selected=(value.accounts||[]).find(row=>row.id===account&&row.broker==='DHAN');
 if(!selected)throw Error('This Dhan account is not accessible to your signed-in user.');
 $('account-label').textContent=selected.label;await status();sync();
 }catch(error){$('error').textContent=error.message;$('review').disabled=true;}}
init();setInterval(()=>status().catch(error=>{$('message').textContent='Status unavailable: '+error.message;}),5000);
})();