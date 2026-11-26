"""Bounded, authenticated-session-scoped transport cache for runner-list reads."""
from collections import OrderedDict
import hashlib
import re
import threading
import time
from urllib.parse import urlsplit,parse_qs
from .stream_delta import StateDelta,wire

_CLIENT=re.compile(r'[a-f0-9-]{36}')
_PATH=re.compile(r'(?:/broker-workspace/[a-f0-9]{32})?/api/renko-instances|/api/renko-(?:dhan|motilal)/[a-f0-9]{32}/instances')


class SnapshotCache:
    def __init__(self, *, budget=256*1024*1024, ttl=120, clock=time.monotonic):
        self.budget,self.ttl,self.clock=budget,ttl,clock
        self.entries=OrderedDict();self.lock=threading.Lock();self.size=0

    def encode(self,key,value):
        # Budget includes a conservative allowance for decoded values and array caches.
        cost=len(wire(value).encode())*5
        with self.lock:
            now=self.clock()
            for old in list(self.entries):
                if now-self.entries[old][1]>self.ttl:
                    _,_,size=self.entries.pop(old);self.size-=size
            entry=self.entries.pop(key,None)
            if entry:
                encoder,_,size=entry;self.size-=size
            else:encoder=StateDelta(take_ownership=True)
            result=encoder.payload(value)
            if cost<=self.budget:
                while self.entries and self.size+cost>self.budget:
                    _,(_,_,size)=self.entries.popitem(last=False);self.size-=size
                self.entries[key]=(encoder,now,cost);self.size+=cost
            return result


CACHE=SnapshotCache()


def encode_snapshot(path,headers,value, *, cache=CACHE):
    parsed=urlsplit(path);query=parse_qs(parsed.query)
    client=(query.get('state_client') or [''])[0]
    if query.get('compact_state')!=['1'] or not _CLIENT.fullmatch(client) or not _PATH.fullmatch(parsed.path):
        return value,False
    session=hashlib.sha256(headers.get('Cookie','').encode()).hexdigest()
    # Existing route authorization executes before this helper. Never share baselines
    # between sessions, accounts, query selections, or browser subscriptions.
    selection=tuple(sorted((k,tuple(v)) for k,v in query.items() if k not in ('compact_state','state_client')))
    key=(session,parsed.path,selection,client)
    return cache.encode(key,value),True
