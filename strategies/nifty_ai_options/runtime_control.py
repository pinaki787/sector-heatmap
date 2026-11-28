"""User-requested, session-bound changes handled between runner decisions."""
import json,time,secrets
from pathlib import Path
try:from .run import atomic
except ImportError:from run import atomic

class HandoverReady(RuntimeError):pass

def enqueue(directory,config,payload,*,target_config=None,preparing=False):
    for key,value in dict(account_id=config['account'],broker=config['broker'],run_id=Path(directory).name,runtime_session=config['runtime_session']).items():
        if payload.get(key)!=value:raise ValueError('Runtime change differs from the active '+key)
    # Execution basis is captured by Start. A view request cannot change it.
    if payload.get('display_mode',config.get('display_mode','CANDLES'))!=config.get('display_mode','CANDLES'):
        raise ValueError('Execution chart basis is pinned at Start; chart view is display-only')
    if payload.get('calculation_mode',config.get('calculation_mode','RENKO'))!=config.get('calculation_mode','RENKO'):
        raise ValueError('Signal calculation basis is pinned at Start')
    changing=payload.get('underlying')!=config['underlying'] or payload.get('calculation_mode',config.get('calculation_mode','RENKO'))!=config.get('calculation_mode','RENKO')
    changing=changing or config.get('calculation_mode') in ('CANDLES','HYBRID') and payload.get('timeframe')!=config['timeframe']
    if changing:
        if not target_config or target_config.get('underlying')!=payload.get('underlying'):raise ValueError('Verified target instrument configuration required')
        for key in ('account','broker','execution_route','execution_mode','lots','product','sma_exit_enabled'):
            if target_config.get(key)!=config.get(key):raise ValueError('Instrument handover cannot change '+key)

    frame=payload.get('timeframe')
    if isinstance(frame,bool) or frame not in (1,5,30):raise ValueError('Choose 1, 5 or 30 minutes')
    display=payload.get('display_mode')
    if display is not None:
        if display not in ('CANDLES','RENKO'):raise ValueError('Choose Candles or Renko exit confirmation')
        if display!=config.get('display_mode','CANDLES') and config.get('supertrend_basis')!='COMPLETED_RENKO':raise ValueError('Restart with completed-brick Supertrend before changing exit mode')
    command=dict(request_id=secrets.token_hex(16),runtime_session=config['runtime_session'],account_id=config['account'],underlying=config['underlying'],timeframe=frame,requested_at=time.time(),phase='QUEUED')
    if display is not None:command['display_mode']=display
    if changing:command.update(target_config=target_config,target_underlying=target_config['underlying'])
    if preparing:
        if not changing:raise ValueError('Target preparation requires an instrument change')
        command['phase']='PREPARING_TARGET'
    atomic(Path(directory)/'reconfigure.json',command)
    return command

class RuntimeControl:
    def __init__(self,config,directory,*,apply,apply_mode=None):
        self.config=config;self.directory=Path(directory);self.apply=apply;self.apply_mode=apply_mode;self.seen=None;self.entry_blocked=False
        self.execution_basis={k:config.get(k) for k in ('display_mode','calculation_mode','supertrend_basis','exit_confirmation_mode','indicator_length','indicator_factor')}
    def poll(self,*,busy=False,position=False):
        path=self.directory/'reconfigure.json'
        if not path.exists():return
        stat=path.stat();identity=(stat.st_ino,stat.st_mtime_ns,stat.st_size)
        if identity==self.seen:return
        command=json.loads(path.read_text())
        if command.get('phase') not in ('QUEUED','PREPARING_TARGET'):
            self.entry_blocked=False;self.seen=identity;return
        target=command.get('target_config') or {}
        if (command.get('display_mode',self.config.get('display_mode','CANDLES'))!=self.config.get('display_mode','CANDLES')
            or any(k in target and target[k]!=v for k,v in self.execution_basis.items())):
            self.entry_blocked=False
            atomic(path,dict(command,phase='REJECTED',error='Execution basis is pinned at Start; view changes cannot reconfigure it'))
            self.seen=None
            return
        self.entry_blocked=bool(command.get('target_config'))
        if command.get('runtime_session')!=self.config.get('runtime_session') or command.get('account_id')!=self.config.get('account') or command.get('underlying')!=self.config.get('underlying'):raise ValueError('Runtime change belongs to a different session')
        if command.get('phase')=='PREPARING_TARGET' or busy:return
        if command.get('target_config'):
            if position:return
            atomic(self.directory/'handover-ready.json',command)
            atomic(path,dict(command,phase='READY_TO_HANDOVER'))
            raise HandoverReady('Confirmed instrument handover is flat and ready')
        self.entry_blocked=False
        if time.time()-command['requested_at']>30:
            atomic(path,dict(command,phase='REJECTED',error='Runtime change expired'));return
        frame=command['timeframe']
        if isinstance(frame,bool) or frame not in (1,5,30):raise ValueError('Unsupported runtime timeframe')
        display=command.get('display_mode',self.config.get('display_mode','CANDLES'))
        if display not in ('CANDLES','RENKO'):raise ValueError('Invalid exit confirmation mode')
        if display!=self.config.get('display_mode','CANDLES') and not self.apply_mode:raise ValueError('Runtime cannot acknowledge this exit mode')
        if frame!=self.config['timeframe']:self.apply(frame)
        # Display changes never call the runner's mode mutation callback.
        self.config['timeframe']=frame
        atomic(self.directory/'config.json',self.config)
        atomic(path,dict(command,phase='APPLIED',applied_at=time.time()))
        self.seen=None
