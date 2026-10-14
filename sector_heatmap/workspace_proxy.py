"""Same-origin transport to an authenticated user's loopback-only workspace."""
import http.client
import logging
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,unquote
import re

PREFIX='/broker-workspace/'
RESERVED=('/api/workspaces/','/accounts','/user-master','/auth/','/api/dashboard-auth/')


def bootstrap(prefix):
    # A page remains bound to its account path. No global selected-account cookie.
    return """;(function(){
const prefix=PREFIX_VALUE,originalFetch=window.fetch.bind(window),OriginalSource=window.EventSource;
function scoped(value){const url=new URL(value,location.href);
if(url.origin===location.origin&&url.pathname.startsWith('/api/')&&!['/api/workspaces/','/api/renko-engine/','/api/dhan/','/api/renko-dhan/','/api/ema-dhan/','/api/band-dhan/','/api/kama-dhan/'].some(path=>url.pathname.startsWith(path)))url.pathname=prefix+url.pathname;
return url.href;}
window.fetch=function(input,options){if(input instanceof Request)return originalFetch(new Request(scoped(input.url),input),options);return originalFetch(scoped(input),options);};
window.EventSource=class extends OriginalSource{constructor(url,options){super(scoped(url),options);}};
})();\n""".replace('PREFIX_VALUE',repr(prefix))


def proxy(auth,handler,mutation=False):
    parsed=urlsplit(handler.path)
    if not parsed.path.startswith(PREFIX):return False
    response_started=False
    try:
        user=auth.authorize(handler.headers,mutation)
        rest=parsed.path[len(PREFIX):]
        aid,separator,tail=rest.partition('/')
        if not re.fullmatch(r'[a-f0-9]{32}',aid):raise PermissionError('Invalid broker workspace.')
        account=auth.store.account(user,aid)  # Every request checks current ownership/session.
        if (auth.store.folder(account)/'disconnected.json').exists():raise PermissionError('Broker account disconnected. Reconnect from Accounts.')
        if any(part in ('.','..') for part in unquote(tail).split('/')):raise PermissionError('Invalid workspace path.')
        prefix=PREFIX+aid
        if not separator:
            handler.send_response(303);handler.send_header('Location',prefix+'/');handler.send_header('Content-Length','0');handler.end_headers();return True
        from .workspaces import WorkspaceRuntime
        if not hasattr(auth,'runtime'):auth.runtime=WorkspaceRuntime(auth.store,auth.root,auth.port)
        if not auth.runtime.running(aid):
            result=auth.runtime.start(user,aid)
            if result['status']!='READY':raise ValueError('Account workspace is starting; refresh shortly.')
        target=urlunsplit(('','', '/'+tail,parsed.query,''))
        if any(('/'+tail).startswith(value) for value in RESERVED):
            handler.send_response(303);handler.send_header('Location','/'+tail+('?' + parsed.query if parsed.query else ''));handler.send_header('Content-Length','0');handler.end_headers();return True
        host='127.0.0.1:'+str(account['port'])
        headers={k:v for k,v in handler.headers.items() if k.lower() not in
                 ('host','connection','content-length','transfer-encoding','origin','referer','authorization','proxy-authorization')}
        headers['Host']=host
        if mutation:headers['Origin']='http://'+host
        size=int(handler.headers.get('Content-Length','0'))
        if size<0 or size>1024*1024:raise ValueError('Workspace request too large.')
        body=handler.rfile.read(size) if size else None
        connection=http.client.HTTPConnection('127.0.0.1',account['port'],timeout=35)
        try:
            connection.request(handler.command,target,body,headers)
            response=connection.getresponse()
            kind=response.getheader('Content-Type','')
            streaming=kind.startswith('text/event-stream')
            stream_json=kind.startswith('application/json') and ('/'+tail)!='/api/workspace-context'
            compress_json=stream_json and 'gzip' in handler.headers.get('Accept-Encoding','') and not response.getheader('Content-Encoding')
            content=None if streaming or stream_json else response.read(16*1024*1024+1)
            if content is not None and len(content)>16*1024*1024:raise ValueError('Workspace response too large.')
            if content is not None and kind.startswith('text/html'):
                text=content.decode('utf-8')
                # Bind bootstrap and application document navigation to this account.
                text=text.replace('src="/workspace-bootstrap.js','src="'+prefix+'/workspace-bootstrap.js')
                content=text.encode()
            if content is not None and ('/'+tail)=='/workspace-bootstrap.js':
                content=bootstrap(prefix).encode()+content+b'\nif(window.SectorPulseWorkspace)window.SectorPulseWorkspace.portal_url="/accounts";'
            if content is not None and ('/'+tail)=='/api/workspace-context':
                import json
                value=json.loads(content);value['portal_url']='/accounts'
                content=json.dumps(value).encode()
            response_started=True
            handler.send_response(response.status)
            for key,value in response.getheaders():
                lower=key.lower()
                if lower in ('connection','content-length','transfer-encoding','set-cookie'):continue
                if lower=='location':
                    if value.startswith('http://'+host):value=prefix+value[len('http://'+host):]
                    elif value.startswith('/') and not any(value.startswith(p) for p in RESERVED):value=prefix+value
                handler.send_header(key,value)
            handler.send_header('Cache-Control','no-store')
            if streaming:handler.send_header('X-Accel-Buffering','no')
            if compress_json:
                handler.send_header('Content-Encoding','gzip');handler.send_header('Vary','Accept-Encoding')
            if content is not None:handler.send_header('Content-Length',str(len(content)))
            else:handler.send_header('Connection','close')
            handler.end_headers()
            if stream_json:
                handler.close_connection=True
                import zlib
                compressor=zlib.compressobj(1,zlib.DEFLATED,31) if compress_json else None
                while True:
                    chunk=response.read1(65536)
                    if not chunk:break
                    output=compressor.compress(chunk) if compressor else chunk
                    if output:handler.wfile.write(output)
                if compressor:handler.wfile.write(compressor.flush())
                handler.wfile.flush()
            elif streaming:
                handler.close_connection=True
                while True:
                    # readline preserves SSE promptly; response.read(n) can wait for n bytes.
                    line=response.readline()
                    if not line:break
                    handler.wfile.write(line);handler.wfile.flush()
            else:handler.wfile.write(content)
        finally:connection.close()
    except PermissionError as error:auth.json(handler,403,dict(error=str(error)))
    except (BrokenPipeError,ConnectionResetError):pass
    except TimeoutError:
        logging.getLogger(__name__).warning('Workspace request timed out: %s %s',handler.command,parsed.path)
        if not response_started:
            auth.json(handler,504,dict(error='Broker workspace request timed out. Analysis or market data is taking too long; this does not establish a login failure.',code='WORKSPACE_TIMEOUT'))
        else:handler.close_connection=True
    except Exception:
        logging.getLogger(__name__).exception('Workspace transport failed: %s %s',handler.command,parsed.path)
        if not response_started:auth.json(handler,502,dict(error='Broker workspace could not complete this request. Check workspace status; authentication failure has not been established.',code='WORKSPACE_UNAVAILABLE'))
        else:handler.close_connection=True
    return True
