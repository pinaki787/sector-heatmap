"""Bounded, account-scoped Motilal Oswal Open API transport.

Endpoints and units follow the official MO API documentation. Mutations are
never retried, and broker text/headers are never included in public errors.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import ipaddress
import math
import re
import threading
import time
from zoneinfo import ZoneInfo
import requests

BROKER='MOTILAL_OSWAL'
ORIGIN='https://openapi.motilaloswal.com'
EXCHANGES={'NSE','BSE','NSEFO','BSEFO','NSECD','MCX'}
READS={
 'profile':'/rest/login/v5/getprofile',
 'positions':'/rest/book/v4/getposition',
 'position_detail':'/rest/book/v4/getpositiondetail',
 'holdings':'/rest/report/v3/getdpholding',
 'orders':'/rest/book/v5/getorderbook',
 'trades':'/rest/book/v4/gettradebook',
 'margin':'/rest/report/v3/getreportmarginsummary',
 'margin_detail':'/rest/report/v3/getreportmargindetail',
 'quote':'/rest/report/v3/getltpdata',
 'instruments':'/rest/report/v3/getscripsbyexchangename',
 'index_master':'/rest/report/v3/getindexdatabyexchangename',
 'eod':'/rest/report/v3/geteoddatabyexchangename',
 'order_detail':'/rest/book/v5/getorderdetailbyuniqueorderid',
 'trade_detail':'/rest/book/v4/gettradedetailbyuniqueorderid',
 'access_token':'/rest/login/v1/getaccesstoken',
}
MUTATIONS={
 'place':'/rest/trans/v2/placeorder',
 'cancel':'/rest/trans/v2/cancelorder',
 'modify':'/rest/trans/v5/modifyorder',
}


class MotilalError(RuntimeError):
    def __init__(self, message, *, uncertain=False, auth_required=False, code=None):
        super().__init__(message)
        self.uncertain=uncertain
        self.auth_required=auth_required
        self.code=code


def positive(value, label):
    if isinstance(value,bool):raise ValueError(label+' must be a positive finite number.')
    try:result=Decimal(str(value))
    except Exception:raise ValueError(label+' must be a positive finite number.') from None
    if not result.is_finite() or result<=0:raise ValueError(label+' must be a positive finite number.')
    return result


def session_deadline(now):
    local=datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata'))
    cutoff=local.replace(hour=6,minute=0,second=0,microsecond=0)
    if cutoff<=local:cutoff+=timedelta(days=1)
    return cutoff.timestamp()


class Client:
    def __init__(self, credentials, *, requester=None, live_enabled=False, clock=time.time):
        self.credentials=dict(credentials)
        self.client_id=str(credentials.get('MO_CLIENT_ID') or '').strip().upper()
        if not re.fullmatch(r'[A-Z0-9_-]{2,15}',self.client_id):raise ValueError('A valid Motilal client code is required.')
        self.requester=requester or requests.Session()
        self.live_enabled=live_enabled
        self.clock=clock
        self.lock=threading.Lock()
        self.identity_verified=False
        self.last_mutation=0

    def headers(self, *, access_token_call=False):
        c=self.credentials
        for key in ['MO_API_KEY','MO_API_SECRET','MO_AUTH_TOKEN']:
            if not c.get(key):raise MotilalError('Motilal login is required.',auth_required=True)
        if not access_token_call and not c.get('MO_ACCESS_TOKEN'):
            raise MotilalError('Motilal access-token validation is required.',auth_required=True)
        expires=c.get('MO_SESSION_EXPIRES_AT')
        if expires is not None and self.clock()>=float(expires):raise MotilalError('Motilal session expired; sign in again.',auth_required=True)
        for key in ['MO_PUBLIC_IP','MO_LOCAL_IP']:
            try:ipaddress.ip_address(c[key])
            except (ValueError,KeyError):raise ValueError('Configure the actual server public and local IP addresses.') from None
        mac=str(c.get('MO_MAC_ADDRESS') or '')
        if not re.fullmatch(r'[0-9a-fA-F]{2}([:-][0-9a-fA-F]{2}){5}',mac):raise ValueError('Configure the actual server MAC address.')
        result={'Content-Type':'application/json','Accept':'application/json','User-Agent':'MOSL/V.1.1.0',
                'Authorization':c['MO_AUTH_TOKEN'],'ApiKey':c['MO_API_KEY'],'apisecretkey':c['MO_API_SECRET'],
                'accesstoken':c.get('MO_ACCESS_TOKEN',''),'ClientLocalIp':c['MO_LOCAL_IP'],'ClientPublicIp':c['MO_PUBLIC_IP'],
                'MacAddress':mac,'SourceId':'WEB','vendorinfo':self.client_id,'osname':'Linux','osversion':'server',
                'devicemodel':'Sector Pulse server','manufacturer':'Server','productname':'Sector Pulse','productversion':'1.0',
                'browsername':'Sector Pulse','browserversion':'1.0'}
        if any(any(ch in str(value) for ch in '\r\n\x00') for value in result.values()):raise ValueError('Invalid authentication header value.')
        return result

    def request(self, operation, payload=None):
        mutation=operation in MUTATIONS
        if operation not in READS and not mutation:raise ValueError('Unsupported Motilal operation.')
        if mutation:
            if not self.live_enabled:raise PermissionError('Motilal Live submission is disabled for this account.')
            if not self.identity_verified:raise PermissionError('Verify this Motilal account before requesting an order action.')
        path=(MUTATIONS if mutation else READS)[operation]
        body=dict(payload or {})
        if body.get('clientcode') and str(body['clientcode']).upper()!=self.client_id:raise PermissionError('Broker request belongs to a different client code.')
        headers=self.headers(access_token_call=operation=='access_token')
        started=self.clock()
        try:
            if mutation:
                with self.lock:
                    if self.clock()-self.last_mutation<.11:raise MotilalError('Order rate limit reached; no request sent.')
                    self.last_mutation=self.clock()
            response=self.requester.post(ORIGIN+path,headers=headers,json=None if operation=='access_token' else body,timeout=(3,10),allow_redirects=False)
            if response.status_code in {401,403}:raise MotilalError('Motilal authentication was rejected; sign in again.',auth_required=True,uncertain=False)
            if response.status_code!=200:raise MotilalError('Motilal request failed; reconcile broker status before retrying.' if mutation else 'Motilal account request failed.',uncertain=mutation,code=response.status_code)
            result=response.json()
        except MotilalError:raise
        except Exception:raise MotilalError('Motilal response unavailable; reconcile the orderbook before retrying.' if mutation else 'Motilal response is unavailable.',uncertain=mutation) from None
        if not isinstance(result,dict):raise MotilalError('Motilal returned an invalid response.',uncertain=mutation)
        code=str(result.get('errorcode') or '')
        if str(result.get('status')).upper()!='SUCCESS':
            safe_code=code if re.fullmatch(r'[A-Za-z0-9_-]{1,24}',code) else None
            definitive=safe_code in {'MO1050','MO1051','MO1052','MO1053','MO1054','MO1055','MO1056','MO1057','MO1058','MO1059','MO1060','MO1061','MO1062','MO1063','MO1064','MO1070','MO1071','MO1072','MO1073','MO1074','MO1075','MO1076','MO1077','MO1078','MO1079','MO1080','MO1081','MO1082','MO1083','MO1084','MO1085','MO1086','MO1087','MO1088','MO1089','MO1090','MO1091','MO1092','MO1093','MO1094','MO1095','MO1096','MO1097','MO1098','MO1099','MO1100','MO1101','MO1102','MO1103','MO1104'}
            raise MotilalError('Motilal rejected the request'+(' ('+safe_code+')' if safe_code else '')+'.',code=safe_code,uncertain=mutation and not definitive)
        return {**result,'_timing':dict(started_at=started,received_at=self.clock(),elapsed=self.clock()-started)}

    def profile(self):
        result=self.request('profile')
        data=result.get('data')
        if not isinstance(data,dict) or str(data.get('clientcode') or '').upper()!=self.client_id:
            raise PermissionError('Authenticated Motilal profile differs from this workspace account.')
        self.identity_verified=True
        return data

    def quote(self, exchange, token):
        if exchange not in EXCHANGES:raise ValueError('Select a supported Motilal exchange.')
        result=self.request('quote',dict(exchange=exchange,scripcode=int(token)))
        data=result.get('data') or {};timing=result['_timing']
        if str(data.get('exchange') or '').upper()!=exchange or int(data.get('scripcode',-1))!=int(token):raise ValueError('Motilal quote identity differs from the selected instrument.')
        if not 0<=timing['elapsed']<=15:raise ValueError('Motilal quote snapshot is delayed.')
        # Official REST documentation specifies paisa for OHLC/LTP. Depth units
        # are not specified there, so REST bid/ask never authorizes execution.
        ltp=float(positive(data.get('ltp'),'LTP')/100)
        return dict(exchange=exchange,token=int(token),ltp=ltp,received_at=timing['received_at'],
                    provider_timestamp=None,source='MOTILAL_REST_LTP',depth_eligible=False,
                    message='Live execution requires separately timestamped market-depth evidence.')
