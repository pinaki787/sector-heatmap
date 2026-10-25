/* Read-only sector detail through the authenticated settings sidecar. */
(function(root){
'use strict';
function read(accountId,sector,mode,RequestType=root.XMLHttpRequest){
 if(!/^[a-f0-9]{32}$/.test(accountId||''))return Promise.reject(Error('Select your saved sector data account.'));
 if(!['intraday','swing'].includes(mode))return Promise.reject(Error('Choose Intraday or Swing.'));
 const path='/api/notification-admin/sector-detail?'+new URLSearchParams({account_id:accountId,sector,mode});
 // The legacy workspace fetch wrapper rewrites every /api URL. Native XHR
 // deliberately retains this same-origin sidecar path and normal session cookie.
 return new Promise((resolve,reject)=>{
  const request=new RequestType();request.open('GET',path,true);request.timeout=28000;
  request.setRequestHeader('Accept','application/json');
  request.onload=()=>{
   let value;
   try{value=JSON.parse(request.responseText);}catch{reject(Error('Sector detail is temporarily unavailable. Retry when the read-only service recovers.'));return;}
   if(request.status<200||request.status>=300){reject(Error(value.error||'Selected account sector detail unavailable.'));return;}
   if(!value.sector){reject(Error('Selected account sector detail is missing.'));return;}
   resolve(value);
  };
  request.onerror=()=>reject(Error('The read-only sector detail connection failed.'));
  request.ontimeout=()=>reject(Error('Sector candles are taking too long. Retry this sector shortly.'));
  request.send();
 });
}
root.SectorDetailClient={read};
if(typeof module!=='undefined'&&module.exports)module.exports={read};
})(typeof window==='undefined'?globalThis:window);
