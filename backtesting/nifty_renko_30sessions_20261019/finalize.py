import os,json,pathlib,hashlib,zipfile
P=pathlib.Path(__file__).resolve().parent;os.environ['MPLCONFIGDIR']=str(P/'.mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
d=json.loads((P/'results.json').read_text())
fig,(ax,bx)=plt.subplots(2,1,figsize=(12,7),sharex=True,gridspec_kw={'height_ratios':[2,1]})
for name,label in [('saved_5m_15m','Saved 5m / 15m'),('prior_1m_5m','Prior 1m / 5m'),('RSI_slope_only','Exploratory: RSI slope only')]:
 r=next(r for r in d['results'] if r['name']==name);a=r['scenarios']['base']['development'];b=r['scenarios']['base']['validation'];curve=a['curve']+[x+a['metrics']['net'] for x in b['curve']];peak=0;dd=[]
 for v in curve:peak=max(peak,v);dd.append(v-peak)
 ax.plot(curve,label=label,linewidth=1.5);bx.plot(dd,linewidth=1.1)
for axis in (ax,bx):axis.axvline(len(a['curve']),color='#666',linestyle='--',linewidth=1);axis.grid(alpha=.2)
ax.axhline(0,color='#333',linewidth=.6);ax.legend(loc='upper left');ax.set_ylabel('Cumulative simulated net P&L (INR)');bx.set_ylabel('Drawdown (INR)');bx.set_xlabel('Trading sessions, 4 September to 19 October 2026; split after session 20')
bx.set_xticks([0,1500,3375,5250,7125,9000,10875],['1','5','10','15','20','25','30'])
fig.suptitle('Nifty ATM options — one lot, estimated FYERS fees and 0.05% slippage per side')
fig.text(.5,.01,'Research only. Fixed entry strike. Historical candles are not executable quotes; no live-ready winner.',ha='center',fontsize=9);fig.tight_layout(rect=(0,.035,1,.96));fig.savefig(P/'equity-drawdown.png',dpi=160);plt.close(fig)
checked=0
for r in d['results']:
 for scenario,periods in r['scenarios'].items():
  for period,s in periods.items():
   assert s['valid']
   assert abs(sum(t['net'] for t in s['trades'])-s['metrics']['net'])<.001
   for t in s['trades']:
    assert t['entry_at']<=t['exit_at'] and t['entry_at']==t['signal_at']
    assert t['strike']%50==0
    assert abs((t['sell']-t['buy'])*65-t['gross'])<.001
    assert abs(t['gross']-t['fees']-t['net'])<.001
    checked+=1
audit={'status':'passed','scenario_period_replays':39*4,'trade_records_checked':checked,'source_drift':json.loads((P/'decision.json').read_text())['source_drift'],'note':'Signal timestamp is completed prior-bar boundary; fills use next minute open at that same boundary.'}
(P/'final-audit.json').write_text(json.dumps(audit,indent=2))
with zipfile.ZipFile(P/'Nifty_Renko_30_Session_Review.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in ['report.md','report.html','comparison.csv','trade-journal.csv','equity-drawdown.png','decision.json','saved-config.json','plan.json','research.py','report.py','test_research.py','final-audit.json']:
  z.write(P/name,name)
print(json.dumps(audit));print('Report bundle ready')

