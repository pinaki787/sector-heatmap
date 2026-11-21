"""Stage a display-only simulated-signal control across existing owner variants."""
import hashlib
import json
from pathlib import Path

base=Path('.private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119')
out=Path('.private/chart-order-rollouts/renko-signal-label-control-20261119')
out.mkdir(parents=True,exist_ok=True)
prior=json.loads((base/'marker-plan.json').read_text())
helper="""  function chartSimulationMarkers(markers,showSimulated){
    return showSimulated===true?markers:markers.filter(marker=>!String(marker.text||'').startsWith('SIM '));
  }
"""
old_legend="if(!el('signal-label-legend')){const legend=document.createElement('p');legend.id='renko-signal-label-legend';legend.className='muted';legend.textContent='SIM BUY / SELL: historical strategy simulation after all selected entry checks. SIM EXIT: closes its paired simulated trade. FILL: confirmed owned order ledger. Forming bricks do not generate signal labels.';el('chart').before(legend);}"
new_legend="""if(!el('signal-label-legend')){
        const legend=document.createElement('div');legend.id='renko-signal-label-legend';legend.className='muted';legend.style.cssText='display:flex;align-items:center;gap:8px 18px;flex-wrap:wrap;padding:8px 0;font-size:12px';
        const label=document.createElement('label');label.style.cssText='display:inline-flex;align-items:center;gap:7px;white-space:nowrap;cursor:pointer';
        const toggle=document.createElement('input');toggle.type='checkbox';toggle.id='renko-show-simulated-signals';
        try{toggle.checked=localStorage.getItem('sector-pulse:simulated-signal-labels:'+dhanAccount+':'+brokerName)==='true';}catch{}
        toggle.addEventListener('change',()=>setSimulationLabels(toggle.checked));
        label.append(toggle,document.createTextNode('Show simulated signals'));
        const note=document.createElement('span');note.textContent='FILL marks confirmed orders. SIM marks historical simulation.';
        legend.append(label,note);el('chart').before(legend);
      }"""
setter="""    function setSimulationLabels(enabled){
      const toggle=el('show-simulated-signals');if(toggle)toggle.checked=enabled===true;
      try{localStorage.setItem('sector-pulse:simulated-signal-labels:'+dhanAccount+':'+brokerName,String(enabled===true));}catch{}
      paintMarkers();
    }
"""
plan={'status':'STAGED','sources':[]}
for i,item in enumerate(prior['sources']):
 path=Path(item['path']);original=path.read_text();changed=original
 replacements=[
 ('  function executionMarkers(history,state,symbol,timeframe){',helper+'  function executionMarkers(history,state,symbol,timeframe){'),
 (old_legend,new_legend),
 ('    function paintMarkers(){',setter+'    function paintMarkers(){'),
 ('executionMarkers(historicalMarkers,lastRunner,','executionMarkers(chartSimulationMarkers(historicalMarkers,el(\'show-simulated-signals\')?.checked===true),lastRunner,'),
 ("el('latest-signal').onclick=()=>{if(chart","el('latest-signal').onclick=()=>{setSimulationLabels(true);if(chart"),
 ('module.exports={','module.exports={chartSimulationMarkers,')]
 for old,new in replacements:
  if changed.count(old)!=1:raise ValueError(f'{path}: expected one {old[:65]} got {changed.count(old)}')
  changed=changed.replace(old,new)
 candidate=out/f'owner-{i}.js';candidate.write_text(changed)
 (out/f'owner-{i}.backup.js').write_text(original)
 plan['sources'].append({'path':str(path),'base_sha256':hashlib.sha256(original.encode()).hexdigest(),'candidate':str(candidate),'candidate_sha256':hashlib.sha256(changed.encode()).hexdigest()})
(out/'manifest.json').write_text(json.dumps(plan,indent=2))
print('staged',len(plan['sources']),'owner variants')
