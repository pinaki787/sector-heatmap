"""Durable jobs around existing authenticated analysis and runner workflows.

No order prepare/submit/override/cancel route is eligible for asynchronous replay.
Interrupted requests are never restarted automatically.
"""
from copy import copy,deepcopy
from io import BytesIO
import json
import re
import time
from urllib.parse import urlsplit,parse_qs
from .persistent_jobs import JobStore,JobCancelled,JobInterrupted
from .section_permissions import allowed


def operation(path):
    route=urlsplit(path).path
    if not route.startswith('/api/'):return None
    if any(term in route for term in ('trade-ticket','submit','override','squareoff','login','auth/','diagnostic')):return None
    if route.endswith(('/analyze','/analyze-options','/analyze-market','/analysis','/ai-review','/ai-analysis','/backtest')):
        feature='screener' if 'chartink' in route else 'holdings' if 'holding' in route else 'handoff' if 'handoff' in route else 'trade-parser'
        return ('ANALYSIS',feature)
    if route.endswith(('/start','/runner-start','/form-runner-start','/start-selected','/start-paper')) and re.match(r'^/api/(renko|ema-|band-|kama|nifty-straddle|sensex-straddle|straddle|delta-india)',route):
        feature='renko-engine' if 'renko-engine' in route else 'renko-supertrend' if 'renko' in route else 'ema-band' if 'band' in route else 'ema-cross' if 'crossover' in route or 'ema-dhan' in route else 'kama' if 'kama' in route else 'straddles' if 'straddle' in route else 'delta-india'
        return ('RUNNER',feature)
    return None


def runner_routes(path):
    parsed=urlsplit(path);route=parsed.path;query=('?'+parsed.query) if parsed.query else ''
    if route.endswith('/form-runner-start'):return route[:-len('form-runner-start')]+'form-runner'+query,route[:-len('form-runner-start')]+'form-runner-stop'+query
    if route.endswith('/runner/start'):return route[:-len('/start')]+query,route[:-len('/start')]+'/stop'+query
    if route.endswith('/runner-start'):return route[:-len('/runner-start')]+'/status'+query,route[:-len('/runner-start')]+'/runner-stop'+query
    if route.endswith('/start-paper'):return route[:-len('/start-paper')]+query,route[:-len('/start-paper')]+'/stop'+query
    if route.endswith('/start'):
        base=route[:-len('/start')]
        return base+('' if 'straddle' in base else '/runner')+query,base+'/stop'+query
    return None


def install(handler_class,root,local_auth=None,workspace_guard=None,analysis_runs=None,market_factory=None,runner_factory=None):
    store=JobStore(root/'.private/persistent-jobs.sqlite3')
    original_get,original_post=handler_class.do_GET,handler_class.do_POST

    def identity(handler,mutation=False):
        if workspace_guard:
            if not workspace_guard.check(handler,mutation=mutation):return None
            user,account=handler.workspace_identity
        elif local_auth:
            if not local_auth.check(handler,mutation=mutation):return None
            user=local_auth.authorize(handler.headers,mutation)
            account=None
        else:
            host=handler.headers.get('Host','').split(':')[0]
            if host not in ('127.0.0.1','localhost'):raise PermissionError('Authenticated workspace required for jobs.')
            user={'id':'local','admin':True};account=None
        return user,account

    def owner_for(handler,user,account,path=None,payload=None):
        aid=account['id'] if account else 'dashboard'
        candidate=(payload or {}).get('account_id') or (parse_qs(urlsplit(path or handler.path).query).get('account_id') or [None])[0]
        match=re.search(r'/api/(?:renko-motilal|renko-dhan|ema-dhan|band-dhan|kama-dhan|renko-engine)/([a-f0-9]{32})/',path or handler.path)
        if match:candidate=match.group(1)
        if candidate:
            if account and candidate!=aid:raise PermissionError('Job differs from this broker account.')
            if local_auth:local_auth.store.account(user,candidate)
            aid=candidate
        return str(user.get('id',user.get('username')))+':'+aid

    def replay(handler,path,payload=None):
        clone=object.__new__(handler_class);clone.__dict__=copy(handler.__dict__)
        clone.path=path;clone.command='POST' if payload is not None else 'GET';clone._persistent_job_internal=True
        clone.headers=deepcopy(handler.headers)
        content=json.dumps(payload).encode() if payload is not None else b''
        clone.headers.replace_header('Content-Length',str(len(content))) if clone.headers.get('Content-Length') else clone.headers.__setitem__('Content-Length',str(len(content)))
        clone.rfile=BytesIO(content);clone.wfile=BytesIO();captured={}
        if path.split('?',1)[0].endswith('/analysis-handoff/analyze-market'):
            if not market_factory:raise ValueError('This broker market analysis adapter is unavailable.')
            from .market_handoff import analyze
            from .handoff_ai import HandoffAI
            broker,name,aid=market_factory(clone,payload)
            return analyze(payload,broker,HandoffAI(root),name,aid)
        def send_json(status,value):captured.update(status=status,value=value)
        clone.send_json=send_json
        (original_post if payload is not None else original_get)(clone)
        if 'value' not in captured:raise ValueError('Workflow did not return a JSON job result.')
        if captured['status']>=400:raise ValueError(str(captured['value'].get('error','Workflow failed.')))
        return captured['value']

    def restore(owner,payload):
        if analysis_runs is None or not payload.get('analysis_id') or payload['analysis_id'] in analysis_runs:return
        for job in store.list(owner,200):
            value=job.get('output')
            if isinstance(value,dict) and value.get('analysis_id')==payload['analysis_id']:
                aid=owner.split(':',1)[1]
                analysis_runs[payload['analysis_id']]=dict(created_at=value.get('created_at',time.time()),
                    cards={card['card_id']:card for card in value.get('cards',[])},policy=value.get('risk_policy',{}),provider=None,
                    account_id=aid if aid!='dashboard' and job['request']['path'].startswith(('/api/dhan/','/api/motilal/')) else None)
                return

    def post(handler):
        if getattr(handler,'_persistent_job_internal',False):return original_post(handler)
        path=urlsplit(handler.path).path
        # The portal proxies first; its owning account worker handles this job.
        if path.startswith('/broker-workspace/'):return original_post(handler)
        selected=operation(handler.path)
        if not selected and not path.startswith('/api/jobs/') and not path.endswith('/analysis-handoff/size'):return original_post(handler)
        try:
            authenticated=identity(handler,True)
            if not authenticated:return
            user,account=authenticated
            payload=handler.read_json();owner=owner_for(handler,user,account,payload=payload)
            if path.endswith('/analysis-handoff/size'):
                restore(owner,payload)
                return handler.send_json(200,replay(handler,handler.path,payload))
            if path=='/api/jobs/cancel':
                job=store.get(owner,str(payload.get('job_id','')))
                if not allowed(user,job['request']['path']):raise PermissionError('Job section is not assigned.')
                return handler.send_json(200,store.cancel(owner,job['job_id']))
            if not selected:return handler.send_json(404,{'error':'Unknown job operation.'})
            if workspace_guard:workspace_guard.validate_action(account,path,payload)
            kind,feature=selected
            key=handler.headers.get('X-Job-Request-ID') or payload.pop('_job_request_id',None)
            if not key:
                import secrets
                key=secrets.token_hex(16)
            # The legacy ephemeral queue must not sit inside the durable queue.
            payload.pop('async_analysis',None);payload.pop('analysis_job',None)
            request=dict(path=handler.path,payload=payload,account_id=owner.split(':',1)[1])
            def work(context):
                context.checkpoint('Validating the submitted workflow.')
                result=replay(handler,request['path'],payload)
                if request['path'].split('?',1)[0].endswith('/chartink/analyze') and isinstance(result.get('results'),list):
                    combined=list(result['results']);offset=int(payload.get('offset',0))+int(result.get('analyzed',0))
                    while result.get('has_more'):
                        context.checkpoint('Screener batch saved; collecting remaining submitted symbols.',{**result,'results':combined,'analyzed':len(combined)})
                        next_result=replay(handler,request['path'],{**payload,'offset':offset})
                        count=int(next_result.get('analyzed',0))
                        if count<=0:raise ValueError('Screener pagination made no progress; partial output is saved.')
                        combined.extend(next_result.get('results',[]));offset+=count;result=next_result
                    result={**result,'results':combined,'analyzed':len(combined),'has_more':False}
                if kind=='RUNNER':store._update(context.job_id,output=result,message='Runner activation output saved.')
                else:context.checkpoint('Workflow output saved.',result)
                handles=runner_factory(handler,request['path'],payload,result) if kind=='RUNNER' and runner_factory else None
                if handles is not None:
                    def run_identity(value):return value.get('run_id') or value.get('run_started_at') or value.get('started_at')
                    # Bind to activation output, never whichever run happens to
                    # exist when the background monitor first obtains a snapshot.
                    activation_identity=run_identity(result.get('runner',result))
                    owned=[dict(snapshot=handle[0],stop=handle[1],identity=handle[2] if len(handle)>2 else activation_identity,stopped=False) for handle in handles]
                    while owned:
                        if store.shutdown.is_set():raise JobInterrupted()
                        live=[];snapshots=[]
                        for handle in owned:
                            value=handle['snapshot']()
                            if handle['identity'] and run_identity(value)!=handle['identity']:continue
                            snapshots.append(value)
                            if not (value.get('running') or value.get('position') or value.get('pending')):continue
                            if context.cancelled() and not handle['stopped']:
                                handle['stop']();handle['stopped']=True
                            live.append(handle)
                        result={**result,'runner_outputs':snapshots} if len(handles)!=1 else (snapshots[0] if snapshots else result)
                        store._update(context.job_id,output=result,message='Runner output and journal saved.')
                        owned=live
                        if owned:time.sleep(1)
                    return result
                routes=runner_routes(request['path']) if kind=='RUNNER' else None
                if not routes:return result
                current=result.get('runner',result)
                expected=current.get('run_id') or current.get('started_at')
                stop_sent=False
                while current.get('running') or current.get('position') or current.get('pending'):
                    if store.shutdown.is_set():raise JobInterrupted()
                    if context.cancelled() and not stop_sent:
                        # Stop applies only to the submitted run, never a newer run.
                        fresh=replay(handler,routes[0]);fresh=fresh.get('runner',fresh)
                        if expected and (fresh.get('run_id') or fresh.get('started_at'))!=expected:raise JobCancelled()
                        replay(handler,routes[1],{'run_id':expected});stop_sent=True
                    time.sleep(1)
                    result=replay(handler,routes[0]);current=result.get('runner',result)
                    if expected and (current.get('run_id') or current.get('started_at'))!=expected:break
                    store._update(context.job_id,output=result,message='Runner stopping; reconciliation remains active.' if stop_sent else 'Runner active; output and journal saved.')
                return result
            label=(payload.get('underlying') or payload.get('symbol') or feature)+' · '+kind.lower()
            job=store.submit(owner,kind,feature,label,request,work,key)
            return handler.send_json(202,dict(status='QUEUED',job_id=job['job_id'],job=job,jobs_url='/api/jobs',account_id=owner.split(':',1)[1]))
        except PermissionError as error:return handler.send_json(403,{'error':str(error)})
        except ValueError as error:return handler.send_json(409,{'error':str(error)})

    def get(handler):
        if getattr(handler,'_persistent_job_internal',False):return original_get(handler)
        parsed=urlsplit(handler.path)
        is_catalog=parsed.path.endswith('/analysis-handoff/market-catalog')
        if parsed.path!='/api/jobs' and not is_catalog:return original_get(handler)
        try:
            authenticated=identity(handler)
            if not authenticated:return
            user,account=authenticated;owner=owner_for(handler,user,account)
            if is_catalog:
                if not market_factory:raise ValueError('Broker market catalog unavailable.')
                from .market_handoff import catalog
                broker,name,aid=market_factory(handler,{})
                try:return handler.send_json(200,dict(catalog(broker,name),account_id=aid))
                finally:broker.stop()
            job_id=(parse_qs(parsed.query).get('job_id') or [None])[0]
            if job_id:
                job=store.get(owner,job_id)
                if not allowed(user,job['request']['path']):raise PermissionError('Job section is not assigned.')
                return handler.send_json(200,job)
            jobs=[job for job in store.list(owner) if allowed(user,job['request']['path'])]
            return handler.send_json(200,dict(jobs=jobs,account_id=owner.split(':',1)[1]))
        except PermissionError as error:return handler.send_json(403,{'error':str(error)})
        except ValueError as error:return handler.send_json(400,{'error':str(error)})

    handler_class.do_GET=get;handler_class.do_POST=post
    return store
