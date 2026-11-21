"""Read-only exit attribution of saved ledgers; does not rerun strategy."""
import json
from pathlib import Path
import pandas as pd
p=Path(__file__).resolve().parent
t=pd.read_csv(p/'entries.csv');l=pd.read_csv(p/'legs.csv');o=pd.read_csv(p/'orders.csv');e=pd.read_csv(p/'events.csv')
t['entry_time']=pd.to_datetime(t.entry_time);t['exit_time']=pd.to_datetime(t.exit_time);t['duration_minutes']=(t.exit_time-t.entry_time).dt.total_seconds()/60
def group(d,key):
 return d.groupby(key).agg(count=('net_pnl','size'),gross_pnl=('gross_pnl','sum'),costs=('costs','sum'),net_pnl=('net_pnl','sum'),wins=('net_pnl',lambda x:int(x.gt(0).sum()))).reset_index()
terminal=group(t,'exit_reason');terminal['pct_entries']=terminal['count']/len(t)*100
terminal=terminal.merge(t.groupby('exit_reason').duration_minutes.agg(['mean','median','min','max']).reset_index(),on='exit_reason')
leg=group(l,'exit_reason');leg['pct_lot_legs']=leg['count']/len(l)*100
# trigger-bar elapsed time, not execution elapsed time.
stops=e[e.event=='stop_trigger'].copy();stops['time']=pd.to_datetime(stops.time)
stops=stops.merge(t[['entry_id','entry_time','exit_reason','net_pnl']],on='entry_id')
stops['trigger_minutes_after_entry']=(stops.time-stops.entry_time).dt.total_seconds()/60
initial=stops[stops.exit_reason=='initial_stop']
side=group(t,'side')
trigger_stats={str(k):int(v) for k,v in initial.trigger_minutes_after_entry.value_counts().sort_index().items()}
out=dict(entries=len(t),lot_legs=len(l),terminal_exit_breakdown=terminal.to_dict('records'),leg_exit_breakdown=leg.to_dict('records'),side_breakdown=side.to_dict('records'),target_reached_entries=int(t.activated.sum()),partial_entries=int(t.partial_booked.sum()),target_hit_rate_pct=float(t.activated.mean()*100),initial_stop_trigger=dict(count=len(initial),entry_minute=int(initial.trigger_minutes_after_entry.eq(0).sum()),within_first_2_minutes_including_entry=int(initial.trigger_minutes_after_entry.le(1).sum()),within_first_5_minutes_including_entry=int(initial.trigger_minutes_after_entry.le(4).sum()),median_minutes_after_entry=float(initial.trigger_minutes_after_entry.median()),histogram=trigger_stats),ambiguous_same_bar_stop_target=int(stops.ambiguous.fillna(False).sum()),all_entry_duration_minutes=dict(mean=float(t.duration_minutes.mean()),median=float(t.duration_minutes.median())),initial_stop_distance_points=dict(median=float((t[t.exit_reason=='initial_stop'].entry_spot-t[t.exit_reason=='initial_stop'].initial_stop).abs().median()),mean=float((t[t.exit_reason=='initial_stop'].entry_spot-t[t.exit_reason=='initial_stop'].initial_stop).abs().mean())))
# Stop/target distance as known at entry, by final closure reason.
t['initial_risk_points']=(t.entry_spot-t.initial_stop).abs();t['first_target_distance_points']=(t.entry_spot-t.first_target).abs()
out['entry_distance_by_final_reason']=t.groupby('exit_reason')[['initial_risk_points','first_target_distance_points']].median().reset_index().to_dict('records')
out['eod_entry_details']=t[t.exit_reason=='scheduled_15:29'][['entry_id','side','partial_booked','activated','gross_pnl','costs','net_pnl']].to_dict('records')
assert terminal['count'].sum()==256 and leg['count'].sum()==512
assert abs(terminal.net_pnl.sum()-l.net_pnl.sum())<1e-6
(p/'exit_analysis.json').write_text(json.dumps(out,indent=2))
terminal.to_csv(p/'exit_terminal_summary.csv',index=False);leg.to_csv(p/'exit_leg_summary.csv',index=False)
print(json.dumps(out,indent=2))

