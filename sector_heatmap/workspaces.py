"""Local user registry and isolated broker workspaces. Never starts a strategy."""
from contextlib import contextmanager
from http.cookies import SimpleCookie
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import tarfile
import threading
import time

COOKIE = 'sector_pulse_session'
BROKERS = {'FYERS', 'DELTA_INDIA', 'DHAN'}
LIVE_KEYS = ('SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS', 'SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS',
             'SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS', 'SECTOR_PULSE_ENABLE_PARSER_PROTECTION',
             'DELTA_INDIA_ENABLE_LIVE_ORDERS', 'DHAN_ENABLE_LIVE_ORDERS')


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def private_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    from .config import _atomic_private_write
    _atomic_private_write(path, content)


class WorkspaceStore:
    def __init__(self, path, clock=time.time):
        self.path = Path(path).resolve()
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL, password TEXT NOT NULL, admin INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                csrf TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                broker TEXT NOT NULL, label TEXT NOT NULL, account_ref TEXT NOT NULL,
                port INTEGER UNIQUE NOT NULL, live_enabled INTEGER NOT NULL DEFAULT 0,
                credential_identity TEXT UNIQUE, UNIQUE(broker, account_ref));
            CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS user_features(user_id TEXT NOT NULL,feature TEXT NOT NULL,PRIMARY KEY(user_id,feature));
            CREATE TABLE IF NOT EXISTS attempts(username TEXT PRIMARY KEY, failures INTEGER NOT NULL,
                until REAL NOT NULL);
            ''')
        self.path.chmod(0o600)

    def sidebar_visibility(self):
        from .section_permissions import FEATURES
        defaults={**{key:True for key in FEATURES},'renko-engine':True,'broker-connection':True}
        with self.db() as db:
            row=db.execute("SELECT value FROM app_settings WHERE key='sidebar_visibility'").fetchone()
        if row:
            try:
                saved=json.loads(row['value'])
                defaults.update({k:saved[k] for k in defaults if type(saved.get(k)) is bool})
            except (ValueError,TypeError):pass
        return defaults

    def set_sidebar_visibility(self,actor,settings):
        if not actor.get('admin'):raise PermissionError('Administrator access required.')
        if not isinstance(settings,dict) or set(settings)!=set(self.sidebar_visibility()) or any(type(v) is not bool for v in settings.values()):
            raise ValueError('Choose visibility for every sidebar section.')
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO app_settings(key,value) VALUES('sidebar_visibility',?)",(json.dumps(settings),))
        return self.sidebar_visibility()

    def renko_visibility(self):
        defaults={'entry_rules':False,'exit_rules':False,'settings':False}
        with self.db() as db:
            row=db.execute("SELECT value FROM app_settings WHERE key='renko_visibility'").fetchone()
        if row:
            try:
                saved=json.loads(row['value'])
                defaults.update({key:saved[key] for key in defaults if type(saved.get(key)) is bool})
            except (ValueError,TypeError):pass
        return defaults

    def set_renko_visibility(self,actor,settings):
        if not actor.get('admin'):raise PermissionError('Administrator access required.')
        keys={'entry_rules','exit_rules','settings'}
        if not isinstance(settings,dict) or set(settings)!=keys or any(type(v) is not bool for v in settings.values()):
            raise ValueError('Choose visibility for entry rules, exit rules and settings.')
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO app_settings(key,value) VALUES('renko_visibility',?)",(json.dumps(settings),))
        return self.renko_visibility()

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_user(self, username, password, actor=None, bootstrap=False):
        username = str(username).strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,39}', username):
            raise ValueError('Username must be 3–40 letters, digits, dots, underscores or hyphens.')
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ValueError('Use a password of 12–256 characters.')
        salt = secrets.token_hex(16)
        encoded = password_hash(password, salt)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            first = db.execute('SELECT count(*) FROM users').fetchone()[0] == 0
            if bootstrap:
                if not first:
                    raise PermissionError('An administrator already exists.')
            elif not actor or not db.execute('SELECT 1 FROM users WHERE id=? AND admin=1', (actor['id'],)).fetchone():
                raise PermissionError('Only an administrator can add users.')
            uid = secrets.token_hex(16)
            try:
                db.execute('INSERT INTO users VALUES(?,?,?,?,?)', (uid, username, salt, encoded, int(first)))
            except sqlite3.IntegrityError:
                raise ValueError('Username already exists.') from None
        return dict(id=uid, username=username, admin=first)

    def login(self, username, password):
        username = str(username).strip().lower()[:40]
        if not isinstance(password, str) or len(password) > 256:
            raise PermissionError('Invalid username or password.')
        with self.db() as db:
            attempt = db.execute('SELECT * FROM attempts WHERE username=?', (username,)).fetchone()
            if attempt and attempt['until'] > self.clock():
                raise PermissionError('Too many attempts. Try again in a minute.')
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        actual = password_hash(password, user['salt'] if user else '00'*16)
        if not user or not hmac.compare_digest(actual, user['password']):
            with self.db() as db:
                previous = db.execute('SELECT * FROM attempts WHERE username=?', (username,)).fetchone()
                failures = previous['failures']+1 if previous and previous['until'] >= self.clock()-60 else 1
                db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)', (username, failures, self.clock()+60 if failures >= 5 else self.clock()))
            raise PermissionError('Invalid username or password.')
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('DELETE FROM attempts WHERE username=?', (username,))
            db.execute('DELETE FROM sessions WHERE expires<=?', (self.clock(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf, self.clock()+8*3600))
        return token, self.session(token)

    def session(self, token):
        if not isinstance(token, str) or not token or len(token) > 100:
            raise PermissionError('Sign in to Sector Pulse.')
        with self.db() as db:
            row = db.execute('SELECT u.id,u.username,u.admin,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.digest=? AND s.expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), self.clock())).fetchone()
        if not row:
            raise PermissionError('Session expired. Sign in again.')
        user=dict(row)
        from .section_permissions import FEATURES
        with self.db() as db:user['features']=list(FEATURES) if user['admin'] else [r[0] for r in db.execute('SELECT feature FROM user_features WHERE user_id=? ORDER BY feature',(user['id'],))]
        return user

    def renew_session(self, token):
        user = self.session(token)
        with self.db() as db:
            changed = db.execute('UPDATE sessions SET expires=? WHERE digest=? AND expires>?',
                (self.clock()+8*3600, hashlib.sha256(token.encode()).hexdigest(), self.clock())).rowcount
        if changed != 1:
            raise PermissionError('Session expired. Sign in again.')
        return user

    def logout(self, token):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE digest=?', (hashlib.sha256(token.encode()).hexdigest(),))

    def change_password(self, user, current_password, new_password):
        if not isinstance(current_password,str) or len(current_password)>256 or not isinstance(new_password,str) or not 12<=len(new_password)<=256:
            raise ValueError('Use a new password of 12–256 characters.')
        with self.db() as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
            if not row or not hmac.compare_digest(password_hash(current_password,row['salt']),row['password']):
                raise PermissionError('Current password is incorrect.')
            salt=secrets.token_hex(16)
            db.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,password_hash(new_password,salt),user['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))

    def users(self, actor):
        from .section_permissions import FEATURES
        with self.db() as db:
            if not actor or not db.execute('SELECT 1 FROM users WHERE id=? AND admin=1', (actor['id'],)).fetchone():
                raise PermissionError('Only an administrator can open User Master.')
            rows=[]
            for user in db.execute('SELECT id,username,admin FROM users ORDER BY username').fetchall():
                rows.append({'username':user['username'],'admin':bool(user['admin']),'features':list(FEATURES) if user['admin'] else [r[0] for r in db.execute('SELECT feature FROM user_features WHERE user_id=? ORDER BY feature',(user['id'],))]})
            return rows

    def set_features(self, actor, username, features):
        from .section_permissions import FEATURES
        if not isinstance(features,list) or len(features)>len(FEATURES) or any(not isinstance(f,str) or f not in FEATURES for f in features):
            raise ValueError('Select supported dashboard sections.')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not actor or not db.execute('SELECT 1 FROM users WHERE id=? AND admin=1',(actor['id'],)).fetchone():
                raise PermissionError('Only an administrator can assign sections.')
            target=db.execute('SELECT id,admin FROM users WHERE username=?',(str(username).strip().lower(),)).fetchone()
            if not target:raise ValueError('User does not exist.')
            if target['admin']:raise PermissionError('Administrators retain access to every section.')
            db.execute('DELETE FROM user_features WHERE user_id=?',(target['id'],))
            db.executemany('INSERT INTO user_features VALUES(?,?)',[(target['id'],f) for f in sorted(set(features))])
        return {'username':str(username).strip().lower(),'features':sorted(set(features))}

    def accounts(self, user):
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT id,broker,label,account_ref,port,live_enabled FROM accounts WHERE user_id=? ORDER BY label', (user['id'],))]

    def account(self, user, account_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM accounts WHERE id=? AND user_id=?', (account_id, user['id'])).fetchone()
        if not row:
            raise PermissionError('Broker workspace is unavailable for this user.')
        return dict(row)

    def rename_account(self, user, aid, label):
        self.account(user, aid)
        if not isinstance(label, str):
            raise ValueError('Enter a display name.')
        label = label.strip()
        if not 1 <= len(label) <= 80 or any(ord(c) < 32 for c in label):
            raise ValueError('Use a display name of 1 to 80 characters.')
        with self.db() as db:
            db.execute('UPDATE accounts SET label=? WHERE id=? AND user_id=?', (label, aid, user['id']))
        return self.account(user, aid)

    def create_account(self, user, broker, label, account_ref):
        if broker not in BROKERS:
            raise ValueError('Choose FYERS, Dhan or Delta India.')
        label, account_ref = str(label).strip(), str(account_ref).strip().upper()
        if not 1 <= len(label) <= 80 or not re.fullmatch(r'[A-Z0-9_.-]{2,80}', account_ref):
            raise ValueError('Enter a label and broker account reference (2–80 letters/digits).')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            port = db.execute('SELECT COALESCE(MAX(port),8099)+1 FROM accounts').fetchone()[0]
            if port > 8999:
                raise ValueError('Workspace port allocation exhausted.')
            aid = secrets.token_hex(16)
            try:
                db.execute('INSERT INTO accounts(id,user_id,broker,label,account_ref,port) VALUES(?,?,?,?,?,?)',
                           (aid,user['id'],broker,label,account_ref,port))
            except sqlite3.IntegrityError:
                raise ValueError('This broker account reference is already registered.') from None
        return self.account(user, aid)

    def folder(self, account):
        # Account IDs are generated server-side, never taken as filesystem paths.
        if not re.fullmatch(r'[a-f0-9]{32}', account['id']):
            raise ValueError('Invalid workspace identity.')
        return self.path.parent/'accounts'/account['id']

    def configure(self, user, aid, fields, live_enabled=False):
        account = self.account(user, aid)
        if not isinstance(live_enabled, bool) or not isinstance(fields, dict):
            raise ValueError('Invalid credential settings.')
        allowed = {'FYERS': {'FYERS_APP_ID','FYERS_SECRET_KEY','FYERS_REDIRECT_URI'}, 'DHAN': {'DHAN_CLIENT_ID','DHAN_ACCESS_TOKEN','DHAN_API_KEY','DHAN_API_SECRET'}, 'DELTA_INDIA': {'DELTA_INDIA_API_KEY','DELTA_INDIA_API_SECRET'}}[account['broker']]
        if set(fields)-allowed:
            raise ValueError('Unsupported credential field.')
        if any(not isinstance(v,str) or len(v)>4096 or any(c in v for c in '\r\n\x00') for v in fields.values()):
            raise ValueError('Credential values must be single-line text.')
        folder = self.folder(account)
        path = folder/'credentials.json'
        prior = json.loads(path.read_text()) if path.exists() else {}
        credentials = {**prior, **{k:v.strip() for k,v in fields.items() if v.strip()}}
        identity_key = {'FYERS':'FYERS_APP_ID','DHAN':'DHAN_CLIENT_ID','DELTA_INDIA':'DELTA_INDIA_API_KEY'}[account['broker']]
        required = allowed-{'FYERS_REDIRECT_URI'}
        if account['broker']=='DHAN':
            required={'DHAN_CLIENT_ID'}
            if not credentials.get('DHAN_ACCESS_TOKEN') and not (credentials.get('DHAN_API_KEY') and credentials.get('DHAN_API_SECRET')):
                raise ValueError('Enter an access token or both Dhan API key and API secret.')
            if bool(credentials.get('DHAN_API_KEY')) != bool(credentials.get('DHAN_API_SECRET')):
                raise ValueError('Enter both Dhan API key and API secret.')
        if not all(credentials.get(k) for k in required):
            raise ValueError('Complete both broker credential fields.')
        if prior.get(identity_key) and credentials[identity_key] != prior[identity_key]:
            raise ValueError('Use a new workspace for a different broker application/key.')
        if account['broker']=='DHAN':
            if not credentials['DHAN_CLIENT_ID'].isdigit() or credentials['DHAN_CLIENT_ID'] != account['account_ref']:
                raise ValueError('Dhan client ID must match this account reference.')
        if account['broker']=='FYERS':
            from .config import public_origin
            origin = public_origin()
            expected = origin + f"/broker-workspace/{account['id']}/callback" if origin else f"http://127.0.0.1:{account['port']}/callback"
            selected = credentials.get('FYERS_REDIRECT_URI') or expected
            local = f"http://127.0.0.1:{account['port']}/callback"
            if selected not in {expected,local,origin+'/callback' if origin else local}:
                raise ValueError('Use this account callback '+expected+' or its SSH-tunnel callback '+local+'. Register the same URL with FYERS.')
            credentials['FYERS_REDIRECT_URI'] = selected
        digest = hashlib.sha256((account['broker']+'|'+credentials[identity_key]).encode()).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('UPDATE accounts SET credential_identity=?,live_enabled=? WHERE id=?', (digest,int(live_enabled),aid))
            except sqlite3.IntegrityError:
                raise ValueError('This broker application/key already belongs to another workspace.') from None
            private_write(path,json.dumps(credentials))
        return self.account(user, aid)


def cookie_token(headers):
    cookie = SimpleCookie()
    try:
        cookie.load(headers.get('Cookie',''))
        return cookie[COOKIE].value if COOKIE in cookie else cookie['sector_pulse_local_session'].value if 'sector_pulse_local_session' in cookie else ''
    except Exception:
        return ''


def isolated_environment(account, folder, registry, portal_port):
    # Allowlist: do not inherit broker, AI, Telegram, or live-capability secrets.
    env = {k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR','COMSPEC','TEMP','TMP','LANG','LC_ALL') if k in os.environ}
    home = folder/'home'
    home.mkdir(parents=True,exist_ok=True,mode=0o700)
    env.update(HOME=str(home),USERPROFILE=str(home),APPDATA=str(home/'AppData'),XDG_CONFIG_HOME=str(home/'.config'),
               HEATMAP_PORT=str(account['port']),FYERS_TOKEN_FILE=str(home/'.fyers/token.json'),
               SECTOR_PULSE_WORKSPACE_REGISTRY=str(registry),SECTOR_PULSE_WORKSPACE_ID=account['id'],
               SECTOR_PULSE_PORTAL_PORT=str(portal_port),PYTHONNOUSERSITE='1',TZ='Asia/Kolkata')
    env.update({k:'0' for k in LIVE_KEYS})
    if account['live_enabled']:
        env[{'FYERS':'SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS','DHAN':'DHAN_ENABLE_LIVE_ORDERS','DELTA_INDIA':'DELTA_INDIA_ENABLE_LIVE_ORDERS'}[account['broker']]]='1'
    source = folder/'source'
    for name, script in [('NIFTY','nifty_straddle.py'),('SENSEX','sensex_straddle.py')]:
        env['SECTOR_PULSE_'+name+'_STRADDLE_SCRIPT']=str(source/'strategies/long_straddle'/script)
    return env


class WorkspaceRuntime:
    def __init__(self, store, source, portal_port=8079):
        self.store,self.source,self.portal_port=store,Path(source).resolve(),portal_port
        self.processes={}
        self.lock=threading.RLock()

    def running(self, aid):
        p=self.processes.get(aid)
        if p and p.poll() is None:return True
        path=self.store.folder({'id':aid})/'dashboard-owner.lock'
        if not path.exists():return False
        from .file_lock import lock_file,unlock_file
        fd=os.open(path,os.O_RDWR)
        try:
            try:lock_file(fd,blocking=False)
            except (OSError,BlockingIOError):return True
            unlock_file(fd)
            return False
        finally:os.close(fd)

    def configure(self,user,aid,fields,live_enabled):
        with self.lock:
            account=self.store.account(user,aid)
            if self.running(aid):
                callback_only=account['broker']=='FYERS' and isinstance(fields,dict) and all(not value.strip() for key,value in fields.items() if key!='FYERS_REDIRECT_URI') and bool(live_enabled)==bool(account['live_enabled'])
                if not callback_only:
                    raise ValueError('Credentials/capabilities are locked while the workspace dashboard is running. Only the FYERS Redirect URL may be edited; existing strategies remain unchanged.')
            return self.store.configure(user,aid,fields,live_enabled)

    def disconnect(self, user, aid):
        with self.lock:
            account = self.store.account(user, aid)
            if self.running(aid):
                raise ValueError('Disconnect blocked: this account dashboard is still running. Stop its dashboard after checking strategies, positions and pending orders. No connection was changed.')
            folder = self.store.folder(account)
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            private_write(folder/'disconnected.json', json.dumps({'disconnected': True}))
            path = folder/'credentials.json'
            if account['broker']=='DHAN' and path.exists():
                values=json.loads(path.read_text())
                values.pop('DHAN_ACCESS_TOKEN', None)
                private_write(path,json.dumps(values))
            for path in (folder/'dhan-consent.json', folder/'home/.fyers/token.json', folder/'source/.fyers/token.json'):
                path.unlink(missing_ok=True)
            return {'disconnected': True, 'account_id': aid}

    def reconnect(self, user, aid):
        with self.lock:
            account = self.store.account(user, aid)
            (self.store.folder(account)/'disconnected.json').unlink(missing_ok=True)
            return {'disconnected': False, 'account_id': aid}

    def provision(self, account):
        folder=self.store.folder(account)
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        source=folder/'source'
        def valid(path):
            parts=Path(path).parts
            return bool(parts) and not Path(path).is_absolute() and '..' not in parts and not any(p.startswith('.') for p in parts) and not any(p in ('output','outputs','tmp','node_modules','__pycache__','cache') for p in parts)
        if not source.exists():
            stage=folder/('source-'+secrets.token_hex(8))
            stage.mkdir(mode=0o700)
            try:
                def valid(path):
                    parts=Path(path).parts
                    return bool(parts) and not Path(path).is_absolute() and '..' not in parts and not any(p.startswith('.') and p not in ('.env.example','.fyers.env.example','.gitignore','.gitattributes','.oxlintrc.json') for p in parts) and not any(p in ('output','outputs','tmp','node_modules','__pycache__','cache') for p in parts) and Path(path).suffix not in ('.log','.db','.sqlite','.sqlite3')
                if (self.source/'.git').exists():
                    data=subprocess.check_output(['git','archive','--format=tar','HEAD'],cwd=self.source)
                    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                        for m in archive.getmembers():
                            if m.issym() or m.islnk() or not valid(m.name):
                                raise ValueError('Unsupported source archive member: '+m.name)
                        archive.extractall(stage,filter='data')
                    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.source,text=True).strip()
                else:
                    inventory=json.loads((self.source/'release-source-files.json').read_text())
                    commit=inventory['commit']
                    for item in inventory['files']:
                        if not valid(item['path']):raise ValueError('Invalid release inventory path.')
                        original=self.source/item['path']
                        if original.is_symlink() or not original.resolve().is_relative_to(self.source):
                            raise ValueError('Release source escaped its directory.')
                        payload=original.read_bytes()
                        if hashlib.sha256(payload).hexdigest()!=item['sha256']:
                            raise ValueError('Release source changed: '+item['path'])
                        target=stage/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
                        target.write_bytes(payload)
                        target.chmod(original.stat().st_mode & 0o777)
                if not (stage/'sector_heatmap/workspaces.py').exists():
                    raise ValueError('Commit the multi-user release before opening workspaces.')
                stage.rename(source)
                private_write(folder/'source-commit.txt',commit+'\n')
            except Exception:
                import shutil
                shutil.rmtree(stage)
                raise
        # Refresh only reviewed public source; account credentials and journals stay local.
        if (self.source/'.git').exists():
            inventory=subprocess.check_output(['git','ls-files','-z'],cwd=self.source).decode().split('\0')
            inventory += ['sector_heatmap/screener_paging.py','sector_heatmap/advisory_jobs.py','sector_heatmap/runner_job_history.py','runner-jobs.js','user-guide.html','sector_heatmap/dhan_account_login.py','sector_heatmap/network_policy.py','sitecustomize.py','sector_heatmap/premium_exit_mapping.py','strategies/renko_supertrend/dhan_costs.py','sector_heatmap/dhan_handoff.py','sector_heatmap/dhan_recovery.py','sector_heatmap/dhan_sector_analysis.py','strategies/renko_supertrend/manual_brick.py','sector_heatmap/fyers_transport.py','sector_heatmap/fyers_oauth_routing.py','renko-engine.js','broker-connection-status.js','strategies/renko_engine/__init__.py','strategies/renko_engine/rules.py','strategies/renko_engine/runner.py','strategies/renko_engine/service.py','strategies/renko_supertrend/exit_indicators.py','strategies/renko_supertrend/indicator_selection.py', 'strategies/renko_supertrend/indicator_families.py','sector_heatmap/section_permissions.py','sector_heatmap/local_dashboard_auth.py','dashboard-login.html','dashboard-login.js','sector_heatmap/dhan_execution.py','dhan-orders.html','dhan-orders.js','broker-account-options.js', 'broker-form-routing.js', 'sector_heatmap/dhan_form_routes.py', 'sector_heatmap/dhan_indicator_runners.py', 'sector_heatmap/workspace_proxy.py', 'sector_heatmap/dhan_strategy_broker.py', 'sector_heatmap/dhan_mcx.py', 'sector_heatmap/dhan_strategy_service.py', 'dhan-strategies.html', 'dhan-strategies.js','strategies/renko_supertrend/rsi_level.py']
            public=[]
            for name in sorted(set(inventory)):
                path=Path(name)
                if not name or not valid(name) or path.suffix not in ('.py','.js','.html','.css'):continue
                if len(path.parts)>1 and path.parts[0] not in ('sector_heatmap','strategies','vendor'):continue
                original=self.source/path
                if not original.is_file() or original.is_symlink():continue
                target=source/path;target.parent.mkdir(parents=True,exist_ok=True)
                payload=original.read_bytes();target.write_bytes(payload)
                public.append({'path':name,'sha256':hashlib.sha256(payload).hexdigest()})
            private_write(folder/'public-source-overlay.json',json.dumps(public,indent=2))
        (source/'.private').mkdir(parents=True,exist_ok=True,mode=0o700)
        credentials=folder/'credentials.json'
        if credentials.exists():
            values=json.loads(credentials.read_text())
            if account['broker']=='FYERS':
                # FYERS loads the registered private profile directly.
                # Remove legacy generated duplicates on the next stopped-workspace launch.
                (source/".fyers.env").unlink(missing_ok=True)
            elif account['broker']=='DELTA_INDIA':
                private_write(source/'.private/delta-india-credentials.json',json.dumps(values))
        return folder

    def start(self,user,aid):
        with self.lock:
            account=self.store.account(user,aid)
            if (self.store.folder(account)/'disconnected.json').exists():
                raise ValueError('This broker account is disconnected. Use Reconnect in Accounts first.')
            if not self.running(aid):
                import socket
                with socket.socket() as sock:
                    try:sock.bind(('127.0.0.1',account['port']))
                    except OSError:raise ValueError('Workspace port is already occupied; no process was launched.') from None
                folder=self.provision(account)
                env=isolated_environment(account,folder,self.store.path,self.portal_port)
                # Bind a worker to its registered account before importing services.
                log=folder/'dashboard.log'
                fd=os.open(log,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
                with os.fdopen(fd,'a') as output:
                    self.processes[aid]=subprocess.Popen([sys.executable,'heatmap_server.py'],cwd=folder/'source',env=env,stdout=output,stderr=subprocess.STDOUT)
            import socket
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if not self.running(aid):
                    return dict(url=f"http://127.0.0.1:{account['port']}/",status='FAILED')
                try:
                    with socket.create_connection(('127.0.0.1',account['port']),timeout=.2):
                        return dict(url=f"http://127.0.0.1:{account['port']}/",status='READY')
                except OSError:time.sleep(.1)
            return dict(url=f"http://127.0.0.1:{account['port']}/",status='STARTING')
