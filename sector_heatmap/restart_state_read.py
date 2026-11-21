"""Bounded, read-only validation of canonical restart state; no recovery writes."""
import json,math,os,stat
from pathlib import Path
SMALL_LIMIT=4_000_000
HARD_LIMIT=16_000_000

def _pairs(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('Duplicate state field blocks restart.')
  result[key]=value
 return result

def _large_schema(value):
 engine=value.get('renko_engine');config=value.get('config')
 if type(value.get('schema')) is not int or value['schema']!=1 or not isinstance(config,dict) or config.get('strategy')!='RENKO_SUPERTREND_V1':
  raise ValueError('Oversized unsupported runner state blocks restart.')
 if value.get('status') not in {'STOPPED','RUNNING','STOPPING','ERROR','WAITING','STOP_REQUESTED','BLOCKED','RECOVERY_REQUIRED','STOP_RECOVERY_BLOCKED','SIDEWAYS_LOCKED'}:
  raise ValueError('Unknown large Renko lifecycle status blocks restart.')
 if type(value.get('running')) is not bool or type(value.get('accepting_entries')) is not bool or 'position' not in value or 'pending' not in value:
  raise ValueError('Invalid large Renko lifecycle fields block restart.')
 if any(value.get(key) is not None and not isinstance(value[key],dict) for key in ('position','pending')):
  raise ValueError('Invalid large Renko exposure fields block restart.')
 if not isinstance(engine,dict) or any(not isinstance(engine.get(k),dict) for k in ('state','identity','last')) or not isinstance(engine.get('rows'),list) or len(engine['rows'])>500:
  raise ValueError('Oversized unsupported Renko engine blocks restart.')
 for row in engine['rows']:
  if not isinstance(row,dict):raise ValueError('Malformed retained Renko row blocks restart.')
  for key in ('timestamp','open','high','low','close'):
   number=row.get(key)
   if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or number<=0:
    raise ValueError('Invalid retained Renko price row blocks restart.')
  if row['high']<row['low']:raise ValueError('Invalid retained Renko range blocks restart.')
 stack=[(value,0)];nodes=0
 while stack:
  item,depth=stack.pop();nodes+=1
  if depth>48 or nodes>600_000:raise ValueError('Excessive retained state structure blocks restart.')
  if isinstance(item,dict):
   if len(item)>50_000:raise ValueError('Excessive retained state mapping blocks restart.')
   stack.extend((v,depth+1) for v in item.values())
  elif isinstance(item,list):
   if len(item)>50_000:raise ValueError('Excessive retained history blocks restart.')
   stack.extend((v,depth+1) for v in item)
  elif isinstance(item,str):
   if len(item)>1_000_000:raise ValueError('Excessive retained state text blocks restart.')
  elif isinstance(item,float) and not math.isfinite(item):raise ValueError('Nonfinite state value blocks restart.')

def read_runtime_state(path,source):
 source=Path(source).absolute();path=Path(path).absolute()
 roots=[source/'.private',source.parent/'dhan-strategies',source.parent/'motilal-strategies']
 if source.resolve()!=source or path.resolve()!=path or not any(path.is_relative_to(r) for r in roots):
  raise ValueError('Untrusted or symlinked runner state blocks restart.')
 try:
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as stream:
   before=os.fstat(stream.fileno())
   if not stat.S_ISREG(before.st_mode):raise ValueError('Nonregular runner state blocks restart.')
   if before.st_size>HARD_LIMIT:raise ValueError('Oversized current runner state blocks restart.')
   raw=stream.read(HARD_LIMIT+1);after=os.fstat(stream.fileno())
  current=path.lstat()
  if len(raw)>HARD_LIMIT or len(raw)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or (current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns)!=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns):
   raise ValueError('Runner state changed during restart inspection.')
  value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite state value blocks restart.')))
 except (OSError,UnicodeError,RecursionError,json.JSONDecodeError) as error:
  raise ValueError('Unreadable current runner state blocks restart.') from error
 if not isinstance(value,dict):raise ValueError('Invalid current runner state blocks restart.')
 if len(raw)>SMALL_LIMIT:_large_schema(value)
 return value
