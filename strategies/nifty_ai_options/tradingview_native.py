"""Official TradingView read-only Pine transport. No chart, trading or cache writes."""
import json
from pathlib import Path
import requests

ENDPOINT='https://mcp.tradingview.com/mcp'
MAX_BYTES=2_000_000

class TradingViewError(RuntimeError):pass

def decode_reply(response,request_id):
    if response.status_code!=200:
        raise TradingViewError('TradingView HTTP '+str(response.status_code))
    raw=bytearray()
    for chunk in response.iter_content(8192):
        raw.extend(chunk)
        if len(raw)>MAX_BYTES:raise TradingViewError('TradingView response exceeds size limit')
    try:
        if 'text/event-stream' in response.headers.get('Content-Type',''):
            candidates=[]
            for event in raw.decode().replace('\r\n','\n').split('\n\n'):
                data='\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
                if data:candidates.append(json.loads(data))
            reply=next(item for item in candidates if item.get('id')==request_id)
        else:reply=json.loads(raw)
    except (ValueError,UnicodeError,StopIteration,AttributeError):
        raise TradingViewError('Invalid TradingView protocol response') from None
    if not isinstance(reply,dict) or reply.get('jsonrpc')!='2.0' or reply.get('id')!=request_id:
        raise TradingViewError('TradingView response identity mismatch')
    if 'error' in reply:raise TradingViewError('TradingView protocol error')
    result=reply.get('result')
    if not isinstance(result,dict):raise TradingViewError('Missing TradingView result')
    return result

class NativePineClient:
    def __init__(self,token_provider,session=None):
        self.token_provider=token_provider
        self.session=session or requests.Session()
        self.headers=None
        self.request_id=0

    def _post(self,payload):
        # Deliberately fixed destination and no redirects/retries: bearer tokens
        # cannot follow a redirect, and compile timeouts must never be retried.
        return self.session.post(ENDPOINT,json=payload,headers=self.headers,
            timeout=(5,40),allow_redirects=False,stream=True)

    def _rpc(self,method,params):
        self.request_id+=1
        with self._post(dict(jsonrpc='2.0',id=self.request_id,method=method,params=params)) as response:
            result=decode_reply(response,self.request_id)
            session_id=response.headers.get('Mcp-Session-Id')
            if session_id:self.headers['Mcp-Session-Id']=session_id
            return result

    def connect(self):
        token=self.token_provider()
        if not isinstance(token,str) or not token or any(c.isspace() for c in token):
            raise TradingViewError('TradingView authorization unavailable')
        self.headers={'Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream',
                      'Content-Type':'application/json'}
        result=self._rpc('initialize',dict(protocolVersion='2025-03-26',capabilities={},
            clientInfo=dict(name='Sector Pulse Native Reference',version='0.1')))
        protocol=result.get('protocolVersion')
        if protocol not in ('2025-03-26','2025-06-18'):
            raise TradingViewError('Unsupported TradingView protocol')
        self.headers['MCP-Protocol-Version']=protocol
        with self._post(dict(jsonrpc='2.0',method='notifications/initialized')) as response:
            if response.status_code not in (200,202,204):
                raise TradingViewError('TradingView initialization notification failed')

    def run_probe(self,symbol,*,timeframe='30m',return_bars=50,diagnostic=False,native_depth=300):
        if not isinstance(symbol,str) or ':' not in symbol or any(c.isspace() for c in symbol):
            raise ValueError('Exact TradingView exchange:ticker required')
        if timeframe not in ('1m','5m','30m'):raise ValueError('Choose supported host timeframe')
        if isinstance(return_bars,bool) or not isinstance(return_bars,int) or not 1<=return_bars<=1000:
            raise ValueError('Invalid return bar count')
        if type(diagnostic) is not bool and diagnostic not in ('lengths','bricks','frames','depth'):raise ValueError('Invalid diagnostic selection')
        variants={False:'native-reference-probe.pine',True:'native-reference-diagnostic.pine',
            'lengths':'native-reference-lengths-diagnostic.pine','bricks':'native-reference-bricks-diagnostic.pine',
            'frames':'native-reference-frames-diagnostic.pine','depth':'native-reference-depth-diagnostic.pine'}
        if type(native_depth) is not int or native_depth not in (2,20,300,3000,20000):raise ValueError('Invalid native history depth')
        if diagnostic!='depth' and native_depth!=300:raise ValueError('History depth is only supported by the depth control')
        source=Path(__file__).with_name(variants[diagnostic]).read_text()
        arguments=dict(code=source,symbol=symbol,timeframe=timeframe,calc_bars_count=300,
            return_bars=return_bars,format='rows')
        if diagnostic=='depth':arguments['inputs']={'in_0':native_depth}
        if self.headers is None:self.connect()
        return self._rpc('tools/call',dict(name='mcp-tv-run-pine-indicator',arguments=arguments))

    def close(self):
        self.session.close()
        self.headers=None
