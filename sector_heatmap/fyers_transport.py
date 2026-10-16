"""Per-client IPv4 transport for the synchronous FYERS SDK; no global network patches."""
from types import FunctionType, MethodType
import requests
from fyers_apiv3 import fyersModel

class IPv4Adapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        kwargs['source_address']=('0.0.0.0',0)
        return super().init_poolmanager(connections,maxsize,block=block,**kwargs)

def client(*args,**kwargs):
    if kwargs.get('is_async') or (args and args[0]):
        raise ValueError('FYERS IPv4 transport requires synchronous SDK.')
    result=fyersModel.FyersModel(*args,**kwargs)
    session=requests.Session()
    # SDK exception handlers refer to requests.HTTPError on this transport.
    session.HTTPError=requests.HTTPError
    # Proxies could bypass the bound source address. Use direct verified TLS.
    session.trust_env=False
    session.mount('https://',IPv4Adapter())
    service=result.service
    # The SDK hardcodes module-level requests calls. Bind copies of its methods
    # to this private session, preserving SDK response/error semantics.
    for name in ('get_call','post_call','delete_call','patch_call'):
        method=getattr(service,name)
        fn=method.__func__
        if 'requests' not in fn.__globals__:
            raise RuntimeError('Unsupported FYERS SDK request transport.')
        scope=dict(fn.__globals__,requests=session)
        bound=FunctionType(fn.__code__,scope,fn.__name__,fn.__defaults__,fn.__closure__)
        bound.__kwdefaults__=fn.__kwdefaults__
        setattr(service,name,MethodType(bound,service))
    result._sector_pulse_ipv4_session=session
    return result
