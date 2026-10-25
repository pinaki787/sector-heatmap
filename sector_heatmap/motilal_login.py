"""Encrypted, account-bound saved login; OTP stays user-entered, no trading calls."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading
from cryptography.fernet import Fernet, InvalidToken
from .config import _atomic_private_write
from .motilal_api import Client, MotilalError, ORIGIN, session_deadline

AUTH_PATHS={'login':'/rest/login/v7/authdirectapi','otp':'/rest/login/v5/verifyotp','resend':'/rest/login/v5/resendotp'}

class SavedLogin:
    def __init__(self,service):
        self.service=service;self.folder=service.folder;self.lock=threading.RLock()
        self.vault=self.folder/'motilal-saved-login.enc'
        self.pending=self.folder/'motilal-otp-pending.enc'
        self.rate=self.folder/'motilal-login-rate.json'
    def cipher(self):
        # Installation key is outside individual account source/credential archives.
        parent=next((p for p in self.folder.parents if p.name=='.private'),self.folder.parent)
        directory=parent/'credential-vault';directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        key=directory/'motilal.key'
        try:
            fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:pass
        else:
            with os.fdopen(fd,'wb') as target:target.write(Fernet.generate_key())
        if key.stat().st_mode&0o077:raise PermissionError('Credential vault key permissions must be private.')
        return Fernet(key.read_bytes())
    def write(self,path,value):
        _atomic_private_write(path,self.cipher().encrypt(json.dumps(value).encode()).decode())
    def read(self,path):
        try:value=json.loads(self.cipher().decrypt(path.read_bytes()))
        except (InvalidToken,ValueError):raise ValueError('Saved login could not be unlocked; save credentials again.') from None
        if value.get('account_id')!=self.service.account['id']:raise PermissionError('Saved login belongs to another account.')
        return value
    def binding(self):
        c=self.service.credentials()
        return hashlib.sha256((c['MO_CLIENT_ID']+'\0'+c['MO_API_KEY']).encode()).hexdigest()
    def status(self,user,token):
        waiting=False
        if self.pending.exists():
            p=self.read(self.pending)
            waiting=p['user_id']==user['id'] and secrets.compare_digest(p['session'],self.digest(token)) and self.service.clock()<p['expires_at']
        return dict(configured=self.vault.exists(),client_id=self.service.account['account_ref'],otp_required=waiting,reauthentication_required=(self.folder/'motilal-reauthentication.json').exists())
    def save(self,payload):
        if payload.get('consent') is not True:raise ValueError('Explicitly enable saved login for this account.')
        client=str(payload.get('client_id') or '').strip().upper()
        if client!=self.service.account['account_ref']:raise PermissionError('Client code must match this Motilal account.')
        password=payload.get('password');pan=str(payload.get('pan') or '').strip().upper()
        if not isinstance(password,str) or not 1<=len(password)<=256 or any(c in password for c in '\r\n\x00'):raise ValueError('Enter the trading password in the private form.')
        if not re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]',pan):raise ValueError('Enter a valid PAN in the private form.')
        credentials=self.service.credentials()
        with self.lock:
            self.write(self.vault,dict(account_id=self.service.account['id'],client_id=client,pan=pan,
                password_hash=hashlib.sha256((password+credentials['MO_API_KEY']).encode()).hexdigest(),binding=self.binding()))
            self.pending.unlink(missing_ok=True)
        return dict(configured=True,client_id=client,message='Saved encrypted login. Password and PAN are never returned; OTP remains user-entered.')
    def forget(self):
        with self.lock:
            self.vault.unlink(missing_ok=True);self.pending.unlink(missing_ok=True)
        return dict(configured=False)
    @staticmethod
    def digest(token):return hashlib.sha256(token.encode()).hexdigest()
    def client(self,auth='LOGIN'):
        values=self.service.credentials();values.update(MO_AUTH_TOKEN=auth,MO_SESSION_EXPIRES_AT=session_deadline(self.service.clock()))
        return self.service.client_factory(values,live_enabled=bool(self.service.account['live_enabled']),clock=self.service.clock)
    def request(self,client,operation,payload):
        if operation not in AUTH_PATHS:raise ValueError('Only login and OTP verification are supported.')
        headers=client.headers(access_token_call=True)
        if operation=='login':
            headers.pop('Authorization',None);headers.pop('accesstoken',None)
        try:
            response=client.requester.post(ORIGIN+AUTH_PATHS[operation],headers=headers,json=payload,timeout=(3,10),allow_redirects=False)
            if response.status_code!=200:raise ValueError()
            value=response.json()
            if not isinstance(value,dict) or str(value.get('status','')).upper()!='SUCCESS':raise ValueError()
        except Exception:raise MotilalError('Motilal login verification failed. Check the credentials or OTP; no automatic retry was made.') from None
        if operation=='resend':
            message=str(value.get('message') or '').lower()
            if 'already' in message and not ('otp' in message and ('sent' in message or 'send' in message)):
                raise MotilalError('Motilal says this authorization is already verified; it did not confirm sending an OTP. Log out the broker session before requesting a new challenge.',code='OTP_ALREADY_VERIFIED')
        return value
    def start(self,user,token,require_otp=False):
        with self.lock:
            marker=self.folder/'motilal-reauthentication.json'
            if marker.exists():require_otp=require_otp or bool(json.loads(marker.read_text()).get('reauthentication_required'))
            value=self.read(self.vault)
            if value['binding']!=self.binding():raise ValueError('API application changed; save the trading login again.')
            now=self.service.clock()
            previous=json.loads(self.rate.read_text()) if self.rate.exists() else {}
            if now-float(previous.get('at',-100000))<60:raise ValueError('Login already requested; wait one minute before requesting another OTP.')
            _atomic_private_write(self.rate,json.dumps(dict(at=now)))
            self.pending.unlink(missing_ok=True)
            client=self.client();result=self.request(client,'login',dict(userid=value['client_id'],password=value['password_hash'],**{'2FA':value['pan']}))
            auth=result.get('AuthToken')
            if not isinstance(auth,str) or not auth or len(auth)>4096 or any(c in auth for c in '\r\n\x00'):raise MotilalError('Motilal did not return a valid login challenge.')
            pending=dict(account_id=self.service.account['id'],user_id=user['id'],session=self.digest(token),auth=auth,expires_at=now+300,sent_at=now)
            if require_otp:
                client.credentials['MO_AUTH_TOKEN']=auth
                self.request(client,'resend',{'clientcode':''})
            elif str(result.get('isAuthTokenVerified','')).upper()=='TRUE':return self.finish(client,auth)
            self.write(self.pending,pending)
            return dict(otp_required=True,expires_at=pending['expires_at'],message='Enter the OTP sent by Motilal. No trading action has been taken.')
    def resend(self,user,token):
        with self.lock:
            if not self.pending.exists():raise ValueError('Request a new login challenge first.')
            pending=self.read(self.pending)
            if pending['user_id']!=user['id'] or not secrets.compare_digest(pending['session'],self.digest(token)):raise PermissionError('OTP challenge belongs to another dashboard session.')
            now=self.service.clock()
            if now-pending.get('sent_at',pending['expires_at']-300)<60:raise ValueError('Wait one minute before requesting another OTP.')
            if now>pending['expires_at']+1800:raise ValueError('Login challenge is too old. Use Connect for a fresh login.')
            pending['sent_at']=now;self.write(self.pending,pending)
            self.request(self.client(pending['auth']),'resend',{'clientcode':''})
            pending['expires_at']=now+300;self.write(self.pending,pending)
            return dict(otp_required=True,expires_at=pending['expires_at'],message='Motilal accepted the OTP resend request. Check your registered mobile/email; delivery is not confirmed by this app.')

    def verify(self,user,token,otp):
        if not isinstance(otp,str) or not re.fullmatch(r'[0-9]{6}',otp):raise ValueError('Enter the six-digit OTP.')
        with self.lock:
            if not self.pending.exists():raise ValueError('Request a new login OTP.')
            pending=self.read(self.pending)
            if pending['user_id']!=user['id'] or not secrets.compare_digest(pending['session'],self.digest(token)):raise PermissionError('OTP challenge belongs to another dashboard session.')
            if self.service.clock()>=pending['expires_at']:
                self.pending.unlink();raise ValueError('OTP challenge expired. Request a new login.')
            # Consume before transport; an uncertain OTP response cannot be replayed.
            self.pending.unlink();client=self.client(pending['auth'])
            self.request(client,'otp',dict(otp=otp))
            return self.finish(client,pending['auth'])
    def finish(self,client,auth):
        client.credentials['MO_AUTH_TOKEN']=auth
        access=client.request('access_token').get('accesstoken')
        if not isinstance(access,str) or not access:raise MotilalError('Motilal access-token exchange failed.')
        client.credentials['MO_ACCESS_TOKEN']=access;profile=client.profile()
        if str(profile.get('clientcode') or '').upper()!=self.service.account['account_ref']:raise PermissionError('Authenticated broker profile differs from this account.')
        with self.service.lock:
            _atomic_private_write(self.service.session_path,json.dumps(dict(MO_AUTH_TOKEN=auth,MO_ACCESS_TOKEN=access,MO_SESSION_EXPIRES_AT=client.credentials['MO_SESSION_EXPIRES_AT'])))
            self.service.install(client)
            (self.folder/'motilal-reauthentication.json').unlink(missing_ok=True)
        return dict(authenticated=True,client_id=profile['clientcode'],message='Authenticated. No runner started and no order retried.')

    def disconnect_rechallenge(self,user,token):
        from .workspace_disconnect import idle_states,check_flat
        from .motilal_strategy_broker import account_lock
        from .file_lock import lock_file
        from contextlib import ExitStack
        if not self.vault.exists():raise ValueError('Save trading login first to request OTP automatically after broker logout.')
        with self.lock,account_lock(self.folder),ExitStack() as stack:
            for path in idle_states(self.folder/'source'):
                handle=stack.enter_context(open(path.with_suffix('.lock'),'a'))
                try:lock_file(handle.fileno(),blocking=False)
                except OSError:raise ValueError('Active runner ownership blocks broker logout.') from None
            idle_states(self.folder/'source')
            if not self.service.session_path.exists() and self.pending.exists():
                pending=self.read(self.pending)
                if pending['user_id']!=user['id'] or not secrets.compare_digest(pending['session'],self.digest(token)):raise PermissionError('Broker challenge belongs to another dashboard session.')
                # A prior API login may be broker-verified even when local OTP
                # handling did not persist it. Verify identity and flat exposure
                # using that owned authorization before actually logging it out.
                client=self.client(pending['auth'])
                access=client.request('access_token').get('accesstoken')
                if not isinstance(access,str) or not access:raise MotilalError('Broker session cannot be verified for logout.')
                client.credentials['MO_ACCESS_TOKEN']=access
                profile=client.profile()
                if str(profile.get('clientcode') or '').upper()!=self.service.account['account_ref']:raise PermissionError('Broker profile does not match this account.')
                self.service.install(client)
            check_flat(self.service,self.folder)
            # A confirmed broker logout is mandatory before discarding its token.
            self.service.client.request('logout',dict(userid=self.service.account['account_ref']))
            _atomic_private_write(self.folder/'motilal-reauthentication.json',json.dumps(dict(disconnected=True,reauthentication_required=True)))
            self.service.session_path.unlink(missing_ok=True)
            self.pending.unlink(missing_ok=True)
            (self.folder/'motilal-login-intent.json').unlink(missing_ok=True)
            if self.service.feed:self.service.feed.stop()
            self.service.client=None;self.service.loaded_session_mtime=None
            self.rate.unlink(missing_ok=True)
            try:result=self.start(user,token,require_otp=True)
            except Exception:
                raise ValueError('Broker session was logged out and local tokens cleared, but the fresh OTP request failed. Use Connect to request a new challenge. No trading action was taken.') from None
            return dict(result,disconnected=True,reauthentication_required=True)
