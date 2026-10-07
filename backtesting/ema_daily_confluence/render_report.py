"""Render frequency and drawdown comparisons from saved research outputs."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
e=pd.read_csv(P/'equity.csv',index_col=0,parse_dates=True)
q=pd.read_csv(P/'diagnostic_equity.csv',index_col=0,parse_dates=True)
curves={'Original EMA crossover':e.iloc[:,0],'First trade only (4 of 5)':q.iloc[:,0],'Strict all five':q.iloc[:,1]}
fig,axs=plt.subplots(2,1,figsize=(11,7),sharex=True)
for name,s in curves.items():
    axs[0].plot(s.index,s,label=name,lw=1)
    axs[1].plot(s.index,s-s.cummax(),lw=1)
axs[0].set_title('Daily confluence: higher frequency did not produce a profitable edge')
axs[0].set_ylabel('Net index points');axs[1].set_ylabel('Drawdown (points)');axs[0].legend(fontsize=9)
for ax in axs:
    ax.grid(alpha=.2)
    ax.axvline(pd.Timestamp('2026-07-21',tz='Asia/Kolkata'),color='gray',ls='--')
fig.text(.08,.01,'245 sessions | 5-point roundtrip friction | ETF volume proxy | completed-close risk exits | research only',fontsize=9)
fig.tight_layout(rect=(0,.03,1,1));fig.savefig(P/'comparison.png',dpi=150)
daily=pd.read_csv(P/'strict_daily_counts.csv')
print('Strict setup zero-trade dates:');print(daily[daily.iloc[:,1]==0].to_string(index=False))
