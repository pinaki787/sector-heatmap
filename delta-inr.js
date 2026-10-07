(function(root){
 const source='https://www.delta.exchange/support/solutions?articleId=80001200076&categoryId=80000463147&folderId=80000717765';
 let policy=null;
 function valid(p=policy,now=Date.now()/1000){return p?.source===source&&p.native_currency==='USD'&&p.equivalent_currency==='INR'&&Number.isFinite(p.rate)&&p.rate>0&&Number.isFinite(p.verified_at)&&now-p.verified_at>=-2&&now-p.verified_at<=86400;}
 function value(n,currency='USD',p=policy,now=Date.now()/1000){if(n==null||n===''||!Number.isFinite(Number(n)))return null;if(currency==='INR')return Number(n);return currency==='USD'&&valid(p,now)?Number(n)*p.rate:null;}
 function format(n,currency='USD',p=policy,now=Date.now()/1000){const v=value(n,currency,p,now);return v==null?'INR unavailable':new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(v);}
 function set(p){policy=p;return valid();}
 function note(){return valid()?'INR display · ₹'+policy.rate+' per USD · Delta fixed settlement policy · verified '+new Date(policy.verified_at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'INR unavailable · Delta fixed settlement conversion policy is missing or stale.';}
 async function load(){try{const r=await fetch('/api/delta-india/status');if(!r.ok)throw Error('Conversion unavailable');const d=await r.json();set(d.inr_conversion);return valid();}catch{set(null);return false;}}
 root.DeltaINR={load,set,valid,value,format,note,source,get policy(){return policy;}};
 if(typeof module!=='undefined')module.exports=root.DeltaINR;
})(typeof window==='undefined'?globalThis:window);
