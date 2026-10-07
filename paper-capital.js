(function(root){
 async function ensure(mode){
  if(String(mode).toUpperCase()!=='PAPER')return;
  try{const r=await fetch('/api/paper-capital/status');if(!r.ok)throw Error();const s=await r.json();if(s.revision!=='paper-capital-inr-v1')throw Error();}
  catch{throw Error('Virtual Paper capital update awaits backend deployment. Existing sessions and exit controls remain available.');}
 }
 root.PaperCapital={ensure};
 if(typeof module!=='undefined')module.exports=root.PaperCapital;
})(typeof window==='undefined'?globalThis:window);
