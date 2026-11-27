"""Recognize an audited local rejection without inventing a broker fill."""
import math

def resolved(receipt,owner,run,config,owned):
 if config.get('broker')!='DELTA_INDIA' or config.get('account')!=owner:return False
 if any(owned.get(k) for k in ('position','pending','detached_position','positions','closing_legs','stop_verification_position')):return False
 if receipt.get('phase')!='LOCAL_REJECTION_CONFIRMED' or receipt.get('account_id')!=owner or receipt.get('run_id')!=run:return False
 if not config.get('runtime_session') or receipt.get('runtime_session')!=config['runtime_session']:return False
 if receipt.get('symbol')!=config.get('underlying') or receipt.get('broker_flat') is not True or receipt.get('orders_submitted')!=0:return False
 at=receipt.get('completed_at')
 if isinstance(at,bool) or not isinstance(at,(int,float)) or not math.isfinite(at) or at<=0:return False
 return any(r.get('key')==receipt.get('key') and r.get('key') and r.get('phase')=='LOCAL_REJECTION_CONFIRMED' and r.get('broker_flat') is True and r.get('orders_submitted')==0 and r.get('at',0)<=at for r in owned.get('reconciled_intents',[]))
