"""Read-only account ownership admission; never recovers or stops another strategy."""
from pathlib import Path

def legacy_ownership(owner):
 from sector_heatmap.service_restart import runtime_states
 from sector_heatmap.restart_state_read import read_runtime_state
 source=Path('/home/trading/sector-heatmap/.private/dashboard-login/accounts')/owner/'source'
 states=[]
 for path in runtime_states(source):
  state=read_runtime_state(path,source)
  if any(state.get(k) for k in ('running','accepting_entries','position','positions','pending','active','loop_running')):
   states.append(state)
 return dict(running=any(any(s.get(k) for k in ('running','accepting_entries','active','loop_running')) for s in states),position=next((s.get('position') or s.get('positions') for s in states if s.get('position') or s.get('positions')),None),pending=next((s.get('pending') for s in states if s.get('pending')),None))

def assert_attach_available(config):
 state=legacy_ownership(config['account'])
 if state.get('running') or state.get('position') or state.get('pending'):
  raise ValueError('Another account strategy retains activity, exposure or a pending order; attachment is blocked until its ownership is reconciled')
