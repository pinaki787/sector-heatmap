"""Read-only attribution of saved corrected two-lot SMA-exit ledgers."""
import json
from pathlib import Path
import pandas as pd
P=Path(__file__).resolve().parent
t=pd.read_csv(P/'entries.csv');l=pd.read_csv(P/'legs.csv');o=pd.read_csv(P/'orders.csv');ev=pd.read_csv(P/'events.csv')
t.entry_time=pd.to_datetime(t.entry_time);t.exit_time=pd.to_datetime(t.exit_time)
t['minutes_held']=(t.exit_time-t.entry_time).dt.total_seconds()/60
t['entry_day']=t.entry_time.dt.strftime('%Y-%m-%d')
def agg(d,key):
 out=d.groupby(key).agg(entries=('entry_id','size'),wins=('net_pnl',lambda x:int(x.gt(0).sum())),losses=('net_pnl',lambda x:int(x.lt(0).sum())),gross_pnl=('gross_pnl','sum'),costs=('costs','sum'),net_pnl=('net_pnl','sum'),mean_minutes=('minutes_held','mean'),median_minutes=('minutes_held','median')).reset_index()
 return out
reason=agg(t,'exit_reason');reason['pct_entries']=reason.entries/len(t)*100
side=agg(t,'side');daily=agg(t,'entry_day')
win=t[t.net_pnl>0];loss=t[t.net_pnl<0];flip=t[t.exit_reason=='pre_target_SMA_flip']
trigger=ev[(ev.event=='exit_trigger')&(ev.reason=='pre_target_SMA_flip')].copy()
trigger.time=pd.to_datetime(trigger.time);trigger=trigger.merge(t[['entry_id','entry_time']],on='entry_id')
trigger['minutes_after_entry']=(trigger.time-trigger.entry_time).dt.total_seconds()/60
partial=l[l.exit_reason=='first_target_partial']
out=dict(status='READ_ONLY_LEDGER_ANALYSIS',total_entries=len(t),gross_pnl=t.gross_pnl.sum(),costs=t.costs.sum(),net_pnl=t.net_pnl.sum(),costs_pct_gross=t.costs.sum()/t.gross_pnl.sum()*100,whole_entry_wins=len(win),whole_entry_losses=len(loss),flat_entries=int(t.net_pnl.eq(0).sum()),positive_entry_profit_sum=win.net_pnl.sum(),negative_entry_loss_sum=loss.net_pnl.sum(),average_net_winner=win.net_pnl.mean(),average_net_loser=loss.net_pnl.mean(),average_winner_to_abs_loser=win.net_pnl.mean()/-loss.net_pnl.mean(),median_net_winner=win.net_pnl.median(),median_net_loser=loss.net_pnl.median(),net_expectancy_per_entry=t.net_pnl.mean(),average_cost_per_entry=t.costs.mean(),gross_positive_entries=int(t.gross_pnl.gt(0).sum()),gross_winners_turned_net_losses=int((t.gross_pnl.gt(0)&t.net_pnl.le(0)).sum()),whole_entry_exit_groups=reason.to_dict('records'),flip_group=dict(count=len(flip),wins=int(flip.net_pnl.gt(0).sum()),losses=int(flip.net_pnl.lt(0).sum()),average_net_pnl=flip.net_pnl.mean(),median_net_pnl=flip.net_pnl.median(),median_minutes_held=flip.minutes_held.median(),mean_minutes_held=flip.minutes_held.mean(),trigger_entry_minute=int(trigger.minutes_after_entry.eq(0).sum()),trigger_first_2_candles=int(trigger.minutes_after_entry.le(1).sum()),trigger_first_5_candles=int(trigger.minutes_after_entry.le(4).sum()),execution_within_5_elapsed_minutes=int(flip.minutes_held.le(5).sum()),median_trigger_minutes_after_entry=trigger.minutes_after_entry.median()),target_reached_entries=int(t.activated.sum()),target_reached_pct=t.activated.mean()*100,separate_partial_exit_count=len(partial),separate_partial_net_pnl=partial.net_pnl.sum(),side=side.to_dict('records'),daily=daily.to_dict('records'),daily_profit_concentration=dict(profitable_days=int(daily.net_pnl.gt(0).sum()),losing_days=int(daily.net_pnl.lt(0).sum()),best_day=daily.sort_values('net_pnl',ascending=False).iloc[0].to_dict(),worst_day=daily.sort_values('net_pnl').iloc[0].to_dict(),best_3_days_net=daily.nlargest(3,'net_pnl').net_pnl.sum(),remaining_days_excluding_best_3_net=t.net_pnl.sum()-daily.nlargest(3,'net_pnl').net_pnl.sum()),brokerage=o.brokerage.sum(),stt=o.stt.sum(),GST=o.gst.sum())
assert reason.entries.sum()==591 and len(win)+len(loss)==591
assert abs(reason.net_pnl.sum()-t.net_pnl.sum())<1e-7
assert abs(l.net_pnl.sum()-t.net_pnl.sum())<1e-7
assert abs(o.costs.sum()-t.costs.sum())<1e-7
reason.to_csv(P/'loss_exit_attribution.csv',index=False);daily.to_csv(P/'daily_attribution.csv',index=False);side.to_csv(P/'side_attribution.csv',index=False)
(P/'loss_analysis.json').write_text(json.dumps(out,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
print(json.dumps(out,indent=2,default=str))

