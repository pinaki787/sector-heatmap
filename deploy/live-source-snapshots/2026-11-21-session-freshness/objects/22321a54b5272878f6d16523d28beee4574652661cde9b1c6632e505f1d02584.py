"""Private Motilal account session, native data and reviewed execution service."""
import hashlib
import json
from pathlib import Path
import secrets
import socket
import threading
import time
from urllib.parse import urlencode
import uuid
import requests
from .config import _atomic_private_write
from .motilal_api import Client, MotilalError, session_deadline
from .motilal_feed import QuoteFeed
from .motilal_history import History
from .motilal_master import Master
from .motilal_execution import Tickets


def server_mac(local_ip):
    """Use the interface carrying broker traffic; uuid may generate a random MAC."""
    import sys
    if sys.platform.startswith('linux'):
        import fcntl
        import struct
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            for _,name in socket.if_nameindex():
                try:
                    address=socket.inet_ntoa(fcntl.ioctl(sock.fileno(),0x8915,struct.pack('256s',name.encode()[:15]))[20:24])
                    if address!=local_ip:continue
                    mac=(Path('/sys/class/net')/name/'address').read_text().strip().lower()
                    octets=mac.split(':')
                    if len(octets)==6 and all(len(v)==2 for v in octets) and not int(octets[0],16)&1 and int(''.join(octets),16):return mac
                except (OSError,ValueError):continue
        raise ValueError('The broker-facing server interface MAC could not be established.')
    node=uuid.getnode()
    if node & (1<<40):raise ValueError('Server MAC address could not be established.')
    return ':'.join(f'{(node>>shift)&255:02x}' for shift in range(40,-1,-8))


def network_identity():
    # No fabricated network headers. API keys/tokens are never sent here.
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.connect(('openapi.motilaloswal.com',443));local=sock.getsockname()[0]
    response=requests.get('https://api.ipify.org',timeout=(3,5),allow_redirects=False)
    response.raise_for_status()
    import ipaddress
    public=str(ipaddress.ip_address(response.text.strip()))
    mac=server_mac(local)
    return dict(MO_PUBLIC_IP=public,MO_LOCAL_IP=local,MO_MAC_ADDRESS=mac)


class Service:
    def __init__(self,folder,account,*,client_factory=Client,feed_factory=QuoteFeed,clock=time.time,execution_allowed=lambda:True):
        self.folder=Path(folder);self.account=account;self.clock=clock
        self.execution_allowed=execution_allowed
        self.client_factory,self.feed_factory=client_factory,feed_factory
        self.lock=threading.RLock();self.client=None;self.feed=None;self.master=None;self.tickets=None
        self.history=History(self.folder/'motilal-candles.sqlite3',clock=clock)
        self.session_path=self.folder/'motilal-session.json'
        self.loaded_session_mtime=None;self.install_revision=0

    def credentials(self):
        values=json.loads((self.folder/'credentials.json').read_text())
        if str(values.get('MO_CLIENT_ID') or '').upper()!=self.account['account_ref']:
            raise PermissionError('Motilal client code must match this workspace account.')
        return values

    def login_start(self,user,session_token):
        credentials=self.credentials()
        intent=dict(user_id=user['id'],session_digest=hashlib.sha256(session_token.encode()).hexdigest(),expires_at=self.clock()+600)
        _atomic_private_write(self.folder/'motilal-login-intent.json',json.dumps(intent))
        return dict(url='https://invest.motilaloswal.com/OpenAPI/Login.aspx?'+urlencode({'apikey':credentials['MO_API_KEY']}),expires_at=intent['expires_at'])

    def login_complete(self,user,session_token,auth_token):
        if not isinstance(auth_token,str) or not 1<=len(auth_token)<=4096 or any(c in auth_token for c in '\r\n\x00'):
            raise ValueError('Invalid Motilal authorization response.')
        with self.lock:
            path=self.folder/'motilal-login-intent.json'
            intent=json.loads(path.read_text()) if path.exists() else {}
            if intent.get('user_id')!=user['id'] or not secrets.compare_digest(intent.get('session_digest',''),hashlib.sha256(session_token.encode()).hexdigest()) or self.clock()>=intent.get('expires_at',0):
                raise PermissionError('Login intent expired or belongs to another dashboard session. Connect again.')
            path.unlink() # consume before any network exchange
            values=self.credentials()
            values.update(MO_AUTH_TOKEN=auth_token,MO_SESSION_EXPIRES_AT=session_deadline(self.clock()))
            client=self.client_factory(values,live_enabled=bool(self.account['live_enabled']),clock=self.clock)
            reply=client.request('access_token')
            access=reply.get('accesstoken')
            if not isinstance(access,str) or not access:raise MotilalError('Motilal access-token exchange did not complete.',auth_required=True)
            values['MO_ACCESS_TOKEN']=access;client.credentials=values
            profile=client.profile() # exact native client binding before saving
            _atomic_private_write(self.session_path,json.dumps({k:values[k] for k in ['MO_AUTH_TOKEN','MO_ACCESS_TOKEN','MO_SESSION_EXPIRES_AT']}))
            self.install(client)
            return dict(authenticated=True,client_id=profile['clientcode'],expires_at=values['MO_SESSION_EXPIRES_AT'])

    def install(self,client):
        if self.feed:self.feed.stop()
        self.client=client
        self.install_revision+=1
        self.loaded_session_mtime=self.session_path.stat().st_mtime_ns if self.session_path.exists() else None
        self.feed=self.feed_factory(client,clock=self.clock,on_tick=lambda tick:self.history.ingest(tick,tick.get('coverage_since',self.clock())),on_disconnect=self.history.invalidate)
        self.master=Master(self.folder/'motilal-master',client,clock=self.clock)
        self.tickets=Tickets(self.folder,client,self.master,self.feed,self.account['id'],clock=self.clock)

    def ready(self):
        with self.lock:
            if (self.folder/'disconnected.json').exists():raise PermissionError('Motilal account is disconnected.')
            mtime=self.session_path.stat().st_mtime_ns if self.session_path.exists() else None
            if self.client and mtime==self.loaded_session_mtime:
                self.client.headers() # Check expiry without another profile network request.
                return
            values=self.credentials()
            if not self.session_path.exists():raise MotilalError('Connect to Motilal Oswal to authorize this account.',auth_required=True)
            values.update(json.loads(self.session_path.read_text()))
            client=self.client_factory(values,live_enabled=bool(self.account['live_enabled']),clock=self.clock)
            client.profile();self.install(client)

    def status(self):
        self.ready();profile=self.client.profile()
        return dict(authenticated=True,broker='MOTILAL_OSWAL',client_id=profile['clientcode'],exchanges=profile.get('exchanges',[]),products=profile.get('products',[]),
                    live_enabled=self.client.live_enabled,feed_connected=self.feed.connected,feed_error=self.feed.error,
                    session_expires_at=self.client.credentials.get('MO_SESSION_EXPIRES_AT'))

    def quote(self,symbol):
        self.ready();contract=self.master.exact(symbol)
        self.feed.subscribe(contract['exchange'],contract['token']);self.feed.start()
        snapshot=self.client.quote(contract['exchange'],contract['token'])
        try:depth=self.feed.quote(contract['exchange'],contract['token'])
        except ValueError as error:return dict(contract=contract,snapshot=snapshot,depth=None,message=str(error))
        return dict(contract=contract,snapshot=snapshot,depth=depth)

    def book(self,operation):
        if operation not in {'positions','holdings','orders','trades','margin','margin_detail'}:raise ValueError('Unsupported account report.')
        self.ready();reply=self.client.request(operation)
        identity_field={'positions':'clientcode','holdings':'clientcode','orders':'clientid','trades':'clientid'}.get(operation)
        if identity_field:
            rows=reply.get('data')
            if not isinstance(rows,list) or any(not isinstance(row,dict) or str(row.get(identity_field,'')).upper()!=self.account['account_ref'] for row in rows):
                raise PermissionError('Native Motilal report has missing or mixed account ownership.')
        # Return native report data and provenance, never token-bearing transport metadata.
        return dict(broker='MOTILAL_OSWAL',account_id=self.account['id'],data=reply.get('data'),timing=reply['_timing'],units='Native Motilal report fields; order input is lots. Acceptance is not a fill.')
