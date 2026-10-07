"""Post-selection daily-cap and strict-confluence diagnostics; not fresh holdout."""
import json
import numpy as np
import pandas as pd
from research import OUT,prepare,events,simulate,metrics

d=prepare();days=np.array(sorted(set(d.index.date)))
frozen=json.loads((OUT/'frozen_selection.json').read_text())
plan=json.loads((OUT/'search_plan.json').read_text())
ranks=pd.read_csv(OUT/'ranking.csv')
strict=ranks[ranks.name.str.contains('score5')].iloc[0]['name']
configs={'Daily coverage: first trade only':dict(frozen['config'],daily_cap=1),
         'Strict all five: up to three trades':plan['configs'][strict]}
(OUT/'diagnostic_plan.json').write_text(json.dumps(dict(configs=configs,strict_name=strict,
    note='Post-selection diagnostics. Strict candidate ranked using development only. Holdout baseline and previous candidate were already observed. No retuning follows this diagnostic.'),indent=2))
rows=[];curves={}
for name,cfg in configs.items():
    ev=events(d,cfg)
    for cost in [0,5,10]:
        t,eq=simulate(d,ev,cost)
        for p,ds in [('full',days),('test',days[196:])]:rows.append(dict(name=name,period=p,cost=cost,**metrics(d,t,eq,ds)))
        if cost==5:
            slug='first_trade' if cfg.get('daily_cap')==1 else 'strict'
            t.to_csv(OUT/f'{slug}_trades.csv',index=False)
            ev[-1].to_csv(OUT/f'{slug}_signals.csv',index=False)
            curves[name]=eq
            counts=t.groupby(pd.to_datetime(t['Entry Timestamp']).dt.date).size().reindex(days,fill_value=0)
            counts.to_csv(OUT/f'{slug}_daily_counts.csv')
            # Independent entry/exit price, ledger evidence and score verification.
            assert len(t)==len(ev[-1])
            for (_,tr),(_,signal) in zip(t.iterrows(),ev[-1].iterrows()):
                ts=pd.Timestamp(tr['Entry Timestamp']);xt=pd.Timestamp(tr['Exit Timestamp'])
                assert ts==pd.Timestamp(signal.entry_timestamp)
                assert ts-pd.Timestamp(signal.signal_timestamp)==pd.Timedelta(minutes=5)
                assert tr['Avg Entry Price']==d.loc[ts,'open'] and tr['Avg Exit Price']==d.loc[xt,'open']
                assert signal.score>=cfg['score']
                if cfg['score']==5:assert signal.volume_ok and signal.momentum_ok and signal.oscillator_ok
            if cfg.get('daily_cap')==1:assert counts.max()<=1
pd.DataFrame(rows).to_csv(OUT/'diagnostic_comparison.csv',index=False)
pd.DataFrame(curves).to_csv(OUT/'diagnostic_equity.csv')
print('Strict candidate:',strict);print(pd.DataFrame(rows).to_string(index=False))
