"""External Delta dashboard liveness supervisor. Never arms runners or sends orders."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from .file_lock import lock_file
from .workspaces import WorkspaceStore, WorkspaceRuntime, isolated_environment, private_write


def decide(*, enabled, disconnected, owner_alive, port_busy, maintenance, attempts, now, next_attempt):
    if not enabled:return 'DISABLED'
    if disconnected:return 'DISCONNECTED'
    if owner_alive:return 'RUNNING'
    if port_busy:return 'BLOCKED_PORT_OCCUPIED'
    if maintenance:return 'MAINTENANCE'
    recent=[at for at in attempts if 0<=now-at<1800]
    if len(recent)>=5:return 'CIRCUIT_OPEN'
    if now<next_attempt:return 'BACKOFF'
    return 'RECOVER'


class Supervisor:
    def __init__(self, registry, root, account_id, portal_port=8080, clock=time.time):
        self.store=WorkspaceStore(registry);self.root=Path(root).resolve();self.aid=account_id
        self.runtime=WorkspaceRuntime(self.store,self.root,portal_port);self.clock=clock
        with self.store.db() as db:row=db.execute('SELECT * FROM accounts WHERE id=?',(account_id,)).fetchone()
        if not row or row['broker']!='DELTA_INDIA':raise ValueError('Supervisor is restricted to the configured Delta account.')
        self.account=dict(row);self.folder=self.store.folder(self.account)
        self.config=self.folder/'external-supervisor-config.json';self.status=self.folder/'external-supervisor-status.json'
        self.events=self.folder/'external-supervisor-events.jsonl'

    def emit(self, value, event=False):
        private_write(self.status,json.dumps(value,indent=2))
        if event:
            fd=os.open(self.events,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
            with os.fdopen(fd,'a') as output:output.write(json.dumps(value)+'\n')
        return value

    def tick(self):
        now=self.clock()
        child=getattr(self,'child',None)
        if child is not None:child.poll()
        if hasattr(self.store,'db'):
            with self.store.db() as db:registered=db.execute('SELECT * FROM accounts WHERE id=?',(self.aid,)).fetchone()
            if not registered or any(registered[k]!=self.account[k] for k in ('broker','user_id','port')):
                return self.emit(dict(status='REGISTRATION_CHANGED',updated_at=now),event=True)
        cfg=json.loads(self.config.read_text()) if self.config.exists() else {}
        saved=json.loads(self.status.read_text()) if self.status.exists() else {}
        attempts=[at for at in saved.get('attempts',[]) if 0<=now-at<1800]
        maintenance=False
        p=self.folder/'bounce-status.json'
        if p.exists():
            bounce=json.loads(p.read_text())
            maintenance=bounce.get('status') in {'CHECKING','RESTARTING','WAITING'} and now-bounce.get('updated_at',0)<120
        with socket.socket() as sock:
            busy=sock.connect_ex(('127.0.0.1',self.account['port']))==0
        alive=self.runtime.running(self.aid)
        phase=decide(enabled=cfg.get('enabled') is True,disconnected=(self.folder/'disconnected.json').exists(),
            owner_alive=alive,port_busy=busy,maintenance=maintenance,attempts=attempts,now=now,next_attempt=saved.get('next_attempt',0))
        value=dict(status=phase,updated_at=now,attempts=attempts,next_attempt=saved.get('next_attempt',0),
                   policy='DASHBOARD_ONLY_LIVE_DISABLED',owner_present=alive,port_listening=busy)
        if phase!='RECOVER':
            if alive and not busy:value['status']='PROCESS_ALIVE_NOT_SERVING'
            # Never kill a live/hung process: it could own pending financial work.
            return self.emit(value,event=value['status']!=saved.get('status'))
        source=self.folder/'source'
        if not (source/'heatmap_server.py').is_file():raise ValueError('Existing isolated dashboard source missing; provisioning is prohibited.')
        # The startup owner lock serializes this launch with browser Open/reloads.
        env=isolated_environment(self.account,self.folder,self.store.path,self.runtime.portal_port)
        env['DELTA_INDIA_ENABLE_LIVE_ORDERS']='0'
        env['SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS']='0'
        env['SECTOR_PULSE_DASHBOARD_RECOVERY_ONLY']='1'
        if (self.folder/'disconnected.json').exists() or json.loads(self.config.read_text()).get('enabled') is not True:
            return self.emit(dict(status='DISABLED_BEFORE_LAUNCH',updated_at=now,attempts=attempts),event=True)
        if self.runtime.running(self.aid):
            return self.emit(dict(status='RUNNING',updated_at=now,attempts=attempts),event=True)
        attempts.append(now)
        value.update(status='RECOVERING_READ_ONLY',attempts=attempts,next_attempt=now+min(300,10*2**(len(attempts)-1)))
        self.emit(value,event=True)  # Durable attempt before launching; survives this supervisor's crash.
        fd=os.open(self.folder/'dashboard.log',os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
        with os.fdopen(fd,'a') as output:
            child=subprocess.Popen([sys.executable,'heatmap_server.py'],cwd=source,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        self.child=child
        value.update(launched_pid=child.pid)
        return self.emit(value,event=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry',required=True);parser.add_argument('--root',required=True);parser.add_argument('--account',required=True)
    parser.add_argument('--portal-port',type=int,default=8080);parser.add_argument('--once',action='store_true')
    parser.add_argument('--enable',action='store_true');parser.add_argument('--disable',action='store_true')
    args=parser.parse_args();supervisor=Supervisor(args.registry,args.root,args.account,args.portal_port)
    if args.enable and args.disable:parser.error('Choose enable or disable.')
    if args.enable or args.disable:
        private_write(supervisor.config,json.dumps(dict(enabled=args.enable,policy='DASHBOARD_ONLY_LIVE_DISABLED',updated_at=time.time())))
        print('External Delta dashboard recovery '+('enabled' if args.enable else 'disabled')+'. No existing runner or process changed.')
        return
    with (supervisor.folder/'external-supervisor.lock').open('a') as handle:
        lock_file(handle.fileno(),blocking=False)
        while True:
            try:result=supervisor.tick()
            except Exception as error:
                try:previous=json.loads(supervisor.status.read_text())
                except (OSError,ValueError):previous={}
                result=supervisor.emit({**previous,'status':'CHECK_FAILED','updated_at':time.time(),'error':type(error).__name__},event=True)
            if args.once:print(json.dumps(result));return
            time.sleep(10)

if __name__=='__main__':main()
