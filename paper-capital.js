(function(root){
 async function ensure(mode){
  if(String(mode).toUpperCase()!=='PAPER')return;
  let response;
  try{response=await fetch('/api/paper-capital/status',{signal:AbortSignal.timeout(15000),cache:'no-store'});}
  catch(error){throw Error('Paper capital verification could not reach the server'+(error.name==='TimeoutError'?' within 15 seconds':'')+'. No new Paper session was started. Existing sessions and exit controls remain available.');}
  if(response.status===401)throw Error('Your login expired. Sign in again before starting a new Paper session. Existing server runners remain separate.');
  if(response.status===403)throw Error('Paper capital verification was denied for this account (HTTP 403). No new Paper session was started.');
  if(!response.ok)throw Error('Paper capital verification failed (HTTP '+response.status+'). No new Paper session was started. Existing sessions and exit controls remain available.');
  let status;
  try{status=await response.json();}catch{throw Error('Paper capital verification received an invalid server response. No new Paper session was started.');}
  if(status.revision!=='paper-capital-inr-v1')throw Error('This account backend has not loaded the required Paper capital revision. No new Paper session was started. Existing sessions and exit controls remain available.');
 }
 root.PaperCapital={ensure};
 if(typeof module!=='undefined')module.exports=root.PaperCapital;
})(typeof window==='undefined'?globalThis:window);
