"""Explicit multi-instrument activation with durable, non-replaying batch IDs."""
import hashlib
import json
from pathlib import Path
import re
import threading
import time


class Batch:
    def __init__(self,path,create,lookup):
        self.path=Path(path);self.create=create;self.lookup=lookup;self.lock=threading.RLock()

    def save(self,file,data):
        self.path.mkdir(parents=True,exist_ok=True)
        temporary=file.with_suffix('.tmp');temporary.write_text(json.dumps(data,allow_nan=False));temporary.chmod(0o600);temporary.replace(file)

    def start(self,payload,background=True):
        token=payload.get('request_id');symbols=payload.get('instruments');broker=payload.get('broker');settings=payload.get('settings')
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',token):raise ValueError('Unique batch request ID required.')
        if broker not in ('FYERS','DELTA_INDIA') or not isinstance(symbols,list) or not 1<=len(symbols)<=20 or len(set(symbols))!=len(symbols) or any(not isinstance(s,str) or not s for s in symbols):raise ValueError('Select 1–20 distinct instruments and their broker.')
        if not isinstance(settings,dict) or settings.get('mode') not in ('PAPER','LIVE'):raise ValueError('Review one shared configuration and explicit Paper/Live mode.')
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        file=self.path/(hashlib.sha256(token.encode()).hexdigest()+'.json')
        with self.lock:
            if file.exists():
                result=json.loads(file.read_text())
                if result['digest']!=digest:raise ValueError('Batch ID reused with different settings.')
                # Recovery never replays starts that may already have armed runners.
                for row in result['results']:
                    if row['status']=='STARTING':row.update(status='REVIEW_REQUIRED',error='Interrupted activation; inspect the durable instance. No automatic replay.')
                return result
            result=dict(request_id=token,digest=digest,broker=broker,mode=settings['mode'],created_at=time.time(),results=[])
            self.save(file,result)
            for symbol in symbols:
                row=dict(instrument=symbol,status='PREPARING');result['results'].append(row);self.save(file,result)
                try:
                    key=self.create(broker,symbol);runner=self.lookup(broker,key)
                    row['instance_key']=key
                    config=dict(settings,underlying=symbol,configuration_revision=runner.runtime_revision)
                    if settings.get('configuration_revision')!=runner.runtime_revision:raise ValueError('Strategy revision changed; reload before batch start.')
                    if runner.state.get('running'):
                        if runner.configure(config)!=runner.configure(runner.state['config']):raise ValueError('Instance already running with different settings; its settings were preserved.')
                        row['status']='ALREADY_RUNNING';self.save(file,result);continue
                    if runner.state.get('position') or runner.state.get('pending'):raise ValueError('Saved exposure/pending intent requires its exact recovery control.')
                    runner.preview(config)
                    if hasattr(runner,'save_preferences'):
                        visible={('symbol' if k=='underlying' else k.replace('_','-')):v for k,v in config.items()}
                        runner.save_preferences({'settings':visible})
                    row['status']='STARTING';self.save(file,result)
                    state=runner.activate(config,background=background)
                    row.update(status='STARTED',running=state['running'],mode=state['config']['mode'])
                except Exception as error:row.update(status='REVIEW_REQUIRED' if row['status']=='STARTING' else 'BLOCKED',error=str(error))
                self.save(file,result)
            result['complete']=True
            result['started_count']=sum(r['status']=='STARTED' for r in result['results'])
            result['blocked_count']=sum(r['status']=='BLOCKED' for r in result['results'])
            result['all_selected_active']=all(r['status'] in ('STARTED','ALREADY_RUNNING') for r in result['results'])
            self.save(file,result);return result
