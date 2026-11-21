"""Owner-bound controls for shared Telegram analysis reports. No trading imports."""
from pathlib import Path
import json,os,time,fcntl,tempfile,subprocess,sqlite3
from .notification_controls import preferences,set_paused

UNIT='sector-pulse-combined-reports.service'
class ReportDelivery:
    def __init__(self,root,store,service=None,clock=time.time):
        self.root=Path(root);self.folder=self.root/'.private/notifications';self.store=store;self.clock=clock;self.service=service or self._service
    def _service(self,action):
        if action=='status':
            p=subprocess.run(['systemctl','is-active',UNIT],capture_output=True,text=True,timeout=5)
            return p.stdout.strip()=='active'
        raise ValueError('Report service lifecycle is managed separately.')
    def _config(self):return json.loads((self.folder/'config.json').read_text())
    def authorize(self,user,section,config):
        if section not in ('sectors','handoff'):raise ValueError('Choose Sector rotation or Analysis Handoff.')
        if user.get('username')!=config.get('primary_owner_username',config.get('owner_username')):raise PermissionError('Only the report owner can manage this Telegram destination.')
        if not self.store.sidebar_visibility().get(section,False) or not(user.get('admin') or section in user.get('features',[])):raise PermissionError('This report section is not available for this sign-in.')
    def status(self,user,section):
        c=self._config();self.authorize(user,section,c)
        shared=(c.get('telegram_destinations') or {}).get('shared_market') or {};prefs=preferences(self.folder/'preferences.json')['scopes']
        configured=bool(c.get('combined_reports',{}).get('enabled') and shared.get('enabled'))
        global_paused=bool(prefs.get('all',{}).get('telegram',{}).get('paused'))
        category_paused=bool(prefs.get('combined',{}).get('telegram',{}).get('paused'))
        running=self.service('status');last=None
        dbpath=self.folder/'combined-outbox.sqlite3'
        if dbpath.exists():
            with sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True,timeout=2) as db:
                row=db.execute("SELECT d.updated FROM delivery d WHERE d.channel='telegram' AND d.state='SENT' ORDER BY d.updated DESC LIMIT 1").fetchone()
                last=row[0] if row else None
        return dict(configured_enabled=configured and not category_paused,enabled=configured and not category_paused and not global_paused and running,global_paused=global_paused,service_running=running,destination=shared.get('title','Shared analysis channel'),interval_minutes=c.get('combined_reports',{}).get('refresh_interval_ms',900000)/60000,refresh_interval_ms=c.get('combined_reports',{}).get('refresh_interval_ms',900000),session='NSE market hours',last_delivery_at=last,scope='Sector rotation and Analysis Handoff · combined report',can_manage=True)
    def configure(self,user,payload):
        interval_only=isinstance(payload,dict) and set(payload)=={'section','refresh_interval_ms'}
        if interval_only and (payload.get('section')!='sectors' or type(payload.get('refresh_interval_ms')) is not int or payload['refresh_interval_ms'] not in (5000,15000,30000,60000,300000,900000,3600000,14400000)):raise ValueError('Choose a supported Sector Rotation refresh interval.')
        if not interval_only and (not isinstance(payload,dict) or set(payload)!={'section','enabled'} or type(payload.get('enabled')) is not bool):raise ValueError('Choose a report section and an enabled checkbox.')
        self.folder.mkdir(parents=True,exist_ok=True)
        with (self.folder/'shared-restore.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            c=self._config();self.authorize(user,payload['section'],c)
            routes=c.get('telegram_destinations') or {};shared=routes.get('shared_market') or {};private=routes.get('private_trades') or {}
            if not routes.get('enabled') or not isinstance(shared.get('chat_id'),int) or shared['chat_id']>=0 or shared['chat_id']==private.get('chat_id'):raise ValueError('A verified, separate shared analysis destination is required.')
            enabled=bool(c.get('combined_reports',{}).get('enabled') and shared.get('enabled')) if interval_only else payload['enabled'];previous=bool(c.get('combined_reports',{}).get('enabled') and shared.get('enabled'))
            if interval_only:c.setdefault('combined_reports',{})['refresh_interval_ms']=payload['refresh_interval_ms']
            else:c.setdefault('combined_reports',{})['enabled']=enabled;shared['enabled']=enabled
            if enabled and not previous:shared['activated_at']=self.clock();c['combined_reports']['activated_at']=self.clock()
            target=self.folder/'config.json'
            with tempfile.NamedTemporaryFile(mode='w',dir=self.folder,prefix='.reports-',delete=False) as f:
                temp=Path(f.name);os.fchmod(f.fileno(),0o600);json.dump(c,f,indent=2);f.flush();os.fsync(f.fileno())
            os.replace(temp,target)
            if not interval_only:set_paused('combined','telegram',not enabled,path=self.folder/'preferences.json',clock=self.clock)
            # Delivery preferences are read immediately by the publisher.
            # The web settings service never starts/stops services or trading.
            self.service('status')
            audit={'at':self.clock(),'actor':user['username'],'section':payload['section'],'enabled':enabled,'refresh_interval_ms':c.get('combined_reports',{}).get('refresh_interval_ms',900000),'private_trade_route_changed':False}
            with (self.folder/'report-control-audit.jsonl').open('a') as f:os.chmod(f.name,0o600);f.write(json.dumps(audit)+'\n')
        return self.status(user,payload['section'])
