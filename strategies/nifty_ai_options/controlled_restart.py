"""One-shot, evidence-checked resumption of an already user-started Delta run.
No signal, broker mutation, position adoption or process action.
"""
import hashlib,json,math,os,time
from pathlib import Path
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def verify(delta,config,directory,state_path,*,clock=time.time):
 from strategies.renko_supertrend.delta_execution import Execution
 path=Path(directory)/'restart-authorization.json'
 proof=json.loads(path.read_text())
 if not proof.get('user_approved') or proof.get('operation')!='SUPPORT_RETEST_DEPLOY' or proof.get('account')!=config.get('account') or proof.get('underlying')!=config.get('underlying') or proof.get('run_id')!=Path(directory).name or not 0<=clock()-proof.get('authorized_at',0)<=180:
  raise ValueError('Controlled restart requires fresh exact-run authorization evidence')
 state=json.loads(Path(state_path).read_text())
 if digest(state)!=proof.get('state_sha256'):raise ValueError('Owned ledger changed after restart preflight; no resumption')
 if any(state.get(k) for k in ('pending','positions','closing_legs','detached_position','stop_verification_position')) or state.get('management_mode') not in (None,'MANAGED'):raise ValueError('Unresolved position control/order blocks controlled restart')
 owned=state.get('position');meta=delta.product(config['underlying']);pid=int(meta['id'])
 native=Execution(delta);native.authenticate()
 orders=[r for r in native.active_orders() if int(r.get('product_id',-1))==pid]
 if orders:raise ValueError('Selected broker contract has active orders; controlled restart blocked')
 quantity=delta._position(pid)
 if owned:
  if owned.get('symbol')!=config['underlying'] or int(owned.get('product_id',-1))!=pid or not owned.get('order_id') or owned.get('side') not in ('LONG','SHORT'):raise ValueError('Exact pre-existing strategy ownership required')
  expected=owned.get('quantity',0)*(1 if owned['side']=='LONG' else -1)
  if expected==0 or quantity!=expected:raise ValueError('Broker and owned position differ; no position adoption')
 elif quantity!=0:raise ValueError('Unmanaged broker exposure blocks controlled restart')
 quote=delta.ticker(config['underlying']);at=clock()
 if not all(isinstance(quote.get(k),(int,float)) and not isinstance(quote.get(k),bool) and math.isfinite(quote[k]) for k in ('bid','ask','exchange_at')) or quote['bid']<=0 or quote['ask']<quote['bid'] or not 0<=at-quote['exchange_at']<=15:raise ValueError('Fresh executable quote required before controlled restart')
 target=proof.get('position_target')
 if target:
  if not owned or not config.get('swing_retest_required') or target.get('direction')!=owned.get('side') or not isinstance(target.get('id'),str) or not all(isinstance(target.get(k),(int,float)) and math.isfinite(target[k]) for k in ('price','confirmed_at','origin_at')) or target['confirmed_at']>owned['entry_timestamp'] or not (target['price']<owned['fill_price'] if owned['side']=='SHORT' else target['price']>owned['fill_price']):raise ValueError('Causal original-entry target evidence is invalid')
  target=dict(target,fresh_touch_after=at,fresh_touch_armed=quote['bid']>target['price'] if owned['side']=='SHORT' else quote['ask']<target['price'])
 trailing=proof.get('trailing_snapshot')
 if trailing:
  from .zone_targets import TargetLadder
  if not owned or not config.get('grid_trailing_enabled'):raise ValueError('Trailing restore requires the exact owned position')
  ladder=TargetLadder.restore(trailing)
  if ladder.entry!=owned.get('fill_price') or ladder.direction!=owned['side'] or ladder.grid.get('available_at',at+1)>owned['entry_timestamp']:raise ValueError('Trailing evidence differs from the original fill')
  if ladder.stop is not None and (quote['ask']>=ladder.stop if owned['side']=='SHORT' else quote['bid']<=ladder.stop):raise ValueError('Restored trailing stop is already crossed; no catch-up close authorized')
 warmup=None
 if proof.get('warmup_sha256'):
  warmfile=Path(directory)/'controlled-restart-history.json';warmup=json.loads(warmfile.read_text())
  if digest(warmup)!=proof['warmup_sha256'] or warmup.get('account')!=config['account'] or warmup.get('symbol')!=config['underlying'] or warmup.get('frame')!=config['timeframe'] or not 0<=at-warmup.get('at',0)<=180:raise ValueError('Controlled history provenance/freshness mismatch')
  rows=warmup['rows'];frame=config['timeframe']*60
  if not rows or rows[-1][0]+frame>at or rows[-1][0]+frame<at-120:raise ValueError('Controlled history is not current and completed')
  previous=None
  for row in rows:
   if len(row)<5 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in row[:5]) or previous is not None and row[0]<=previous or not row[3]<=min(row[1],row[4])<=max(row[1],row[4])<=row[2]:raise ValueError('Invalid controlled history')
   previous=row[0]
 # A used proof cannot silently turn an unrelated later Start into a resume.
 path.rename(Path(directory)/('restart-authorization-consumed-'+str(time.time_ns())+'.json'))
 return dict(account=config['account'],underlying=config['underlying'],at=at,state_sha256=digest(state),broker_quantity=quantity,position=owned,position_target=target,trailing_snapshot=trailing,warmup_rows=warmup['rows'] if warmup else None)
def accepts(proof,state,owner,now):
 return bool(proof and proof.get('account')==owner and 0<=now-proof.get('at',0)<=30 and proof.get('state_sha256')==digest(state) and not state.get('pending'))
