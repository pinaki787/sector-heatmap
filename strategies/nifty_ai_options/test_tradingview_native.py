import json,unittest
from tradingview_native import NativePineClient,decode_reply,TradingViewError

class Reply:
    def __init__(self,value,status=200,kind='application/json'):
        self.raw=value.encode() if isinstance(value,str) else json.dumps(value).encode()
        self.status_code=status;self.headers={'Content-Type':kind};self.closed=False
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def iter_content(self,size):
        for i in range(0,len(self.raw),size):yield self.raw[i:i+size]
class Session:
    def __init__(self,replies):self.replies=list(replies);self.calls=[];self.closed=False
    def post(self,url,**kw):
        self.calls.append((url,kw))
        return self.replies.pop(0)
    def close(self):self.closed=True
def rpc(ident,result):return {'jsonrpc':'2.0','id':ident,'result':result}

class NativeTransportTests(unittest.TestCase):
    def test_only_read_only_probe_is_requested_and_redirects_disabled(self):
        session=Session([Reply(rpc(1,{'protocolVersion':'2025-03-26'})),Reply('',202),
                         Reply(rpc(2,{'isError':False,'structuredContent':{'success':True}}))])
        client=NativePineClient(lambda:'fake-test-token',session)
        result=client.run_probe('NSE:NIFTY')
        self.assertFalse(result['isError'])
        self.assertEqual([c[1]['json']['method'] for c in session.calls],['initialize','notifications/initialized','tools/call'])
        call=session.calls[-1][1]['json']['params']
        self.assertEqual(call['name'],'mcp-tv-run-pine-indicator')
        self.assertEqual(call['arguments']['symbol'],'NSE:NIFTY')
        self.assertIn('ticker.renko',call['arguments']['code'])
        for url,kw in session.calls:
            self.assertEqual(url,'https://mcp.tradingview.com/mcp')
            self.assertIs(kw['allow_redirects'],False)
            self.assertTrue(kw['stream'])
            self.assertEqual(kw['headers']['Authorization'],'Bearer fake-test-token')
        client.close();self.assertTrue(session.closed);self.assertIsNone(client.headers)

    def test_auth_error_does_not_retry_or_expose_body(self):
        session=Session([Reply('private-server-error-token',401)])
        with self.assertRaisesRegex(TradingViewError,'TradingView HTTP 401'):
            NativePineClient(lambda:'fake-test-token',session).run_probe('NSE:NIFTY')
        self.assertEqual(len(session.calls),1)

    def test_invalid_identity_and_oversize_fail_closed(self):
        for response in [Reply(rpc(99,{})),Reply('not json'),Reply('x'*2_000_001),
                         Reply({'jsonrpc':'2.0','id':1,'error':{'message':'secret'}})]:
            with self.assertRaises(TradingViewError):decode_reply(response,1)

    def test_sse_accepts_matching_reply_and_ignores_notifications(self):
        wire='event: message\ndata: {"jsonrpc":"2.0","method":"ping"}\n\nevent: message\ndata: '+json.dumps(rpc(7,{'ok':True}))+'\n\n'
        self.assertEqual(decode_reply(Reply(wire,kind='text/event-stream'),7),{'ok':True})

    def test_invalid_symbol_or_frame_sends_no_request(self):
        session=Session([])
        client=NativePineClient(lambda:'fake-test-token',session)
        for symbol in ('NIFTY','','NSE:NIF TY'):
            with self.assertRaises(ValueError):client.run_probe(symbol)
        with self.assertRaises(ValueError):client.run_probe('NSE:NIFTY',timeframe='6h')
        self.assertEqual(session.calls,[])

    def test_unknown_diagnostic_cannot_read_credentials_or_send_requests(self):
        session=Session([])
        def unavailable():raise AssertionError('Must validate diagnostic before credentials')
        client=NativePineClient(unavailable,session)
        for diagnostic in ('../../private-script','unknown',None,{},3):
            with self.assertRaises(ValueError):client.run_probe('NSE:NIFTY',diagnostic=diagnostic)
        self.assertEqual(session.calls,[])
