from pathlib import Path
import hashlib,json,random,math
base=Path(__file__).parent
s=(base/'sector_pulse_v1_merged.pine').read_text(); old=(base/'v1_editor_before.pine').read_text()
checks={}
# Every existing input declaration remains verbatim: saved values retain identity/defaults.
inputs=[l for l in old.splitlines() if 'input.' in l]
checks['all_existing_input_declarations_preserved']=all(l in s for l in inputs)
checks['existing_reference_target_and_window_ratios_preserved']=all(x in s for x in ['f_level(h5,l5,0.44)','f_level(h5,l5,0.50)','f_level(h5,l5,0.56)','array.from(.44,.50,.56)','price+span*.06'])
checks['shadow_ratios_match_v1']=all(x in s for x in ['float sc_p1 = 44.0','float sc_p2 = 50.0','float sc_p3 = 56.0'])
checks['example_prices_not_hardcoded']=all(x not in s for x in ['1413.50','1416.50','1397.00','1401.00'])
checks['confirmed_creation_and_nonbackdated_boxes']='sdEnabled and chart.is_standard and barstate.isconfirmed' in s and 'box.new(time_close, hi, time_close, lo' in s
checks['shadow_previous_price_offsets']=all(x in s for x in ['[high[1], low[1], time[1], time_close[1]','[close[1], open, time]'])
# Independent numeric contract for inverse Wilder RSI, including both sides and equality.
rng=random.Random(20261109); count=0; max_error=0
for _ in range(10000):
 gain=rng.uniform(.001,50); loss=rng.uniform(.001,50); target=rng.uniform(.1,99.9); prev=rng.uniform(100,10000)
 rs=target/(100-target); delta=rs*loss-gain if gain<=rs*loss else loss-gain/rs
 threshold=prev+delta
 if threshold<=0:continue
 computed=100*(gain+max(delta,0))/(gain+max(delta,0)+loss+max(-delta,0))
 max_error=max(max_error,abs(computed-target))
 for shift in [-.01,0,.01]:
  d=delta+shift; actual=100*(gain+max(d,0))/(gain+max(d,0)+loss+max(-d,0))
  assert abs(actual-target)<1e-8 if shift==0 else (actual>target)==(shift>0)
 count+=1
checks['inverse_rsi_10000_random_states']=count>0 and max_error<1e-8
# Lifecycle contract cases independent of chart rendering: invalidation precedes retest;
# touches on consecutive bars count once, a new visit after separation counts again.
def step(z,h,l,c):
 invalid=c>z['hi'] if z['supply'] else c<z['lo']
 if invalid:z['state']='invalid';z['touching']=False;return
 touches=h>=z['lo'] and l<=z['hi']
 if touches and not z['touching']:z['tests']+=1
 z['touching']=touches
for supply in [True,False]:
 z=dict(hi=110,lo=100,supply=supply,state='fresh',tests=0,touching=False)
 step(z,108,102,105);step(z,109,101,106);assert z['tests']==1
 step(z,99,95,98) if supply else step(z,115,111,112)
 step(z,108,102,105);assert z['tests']==2
 step(z,115,108,112) if supply else step(z,102,95,98)
 assert z['state']=='invalid' and z['tests']==2
checks['symmetric_retest_and_invalidation_contract']=True
assert all(checks.values()),checks
result=dict(checks=checks,existing_input_count=len(inputs),inverse_rsi_cases=count,inverse_rsi_max_error=max_error,sha256=hashlib.sha256(s.encode()).hexdigest(),limitations=['Python numeric/contract checks do not compile or execute Pine; TradingView compiler and chart checks are recorded separately.'])
(base/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
