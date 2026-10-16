"""Isolated, cancellable Codex account analysis of public broker evidence only."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from .file_lock import lock_file,unlock_file
from .persistent_jobs import checkpoint


def settings(workspace):
    for folder in (Path(workspace).resolve(),*Path(workspace).resolve().parents):
        path=folder/'.private/analysis-providers.json'
        if path.exists():
            data=json.loads(path.read_text())
            return {k:data[k] for k in ('codex_bin','codex_home') if k in data}
    return {}


def failure_reason(event):
    item=event.get('item') or {};message=str(item.get('message') or item.get('text') or item.get('error') or event.get('message') or event.get('error') or '').lower()
    categories=[(('usage','quota','rate limit','credits'),'Codex account usage limit reached.'),
                (('refresh','unauthorized','authentication','sign in','login','token'),'Codex ChatGPT sign-in needs renewal on the server.'),
                (('schema','json schema'),'Codex rejected the structured-output schema.'),
                (('model','not supported'),'The default Codex model is unavailable for this account.'),
                (('network','connect','timeout'),'Codex could not connect to its account service.')]
    for needles,reason in categories:
        if any(value in message for value in needles):return reason
    return 'Codex account analysis returned an error; no API-key fallback was used.'


def check_event(event):
    item=event.get('item') or {};kind=item.get('type')
    if kind=='error':
        message=str(item.get('message') or '')
        if message.startswith('Under-development features enabled:'):return
        raise ValueError(failure_reason(event))
    if kind not in (None,'agent_message','reasoning'):
        raise ValueError('Codex attempted to use a tool; analysis was stopped.')


def review(workspace,evidence,instructions,schema,timeout=120):
    config=settings(workspace)
    binary=config.get('codex_bin') or shutil.which('codex')
    home=Path(config.get('codex_home') or os.environ.get('CODEX_HOME') or Path.home()/'.codex').resolve()
    if not binary:raise ValueError('Codex account provider is not installed on this server.')
    auth=home/'auth.json'
    try:state=json.loads(auth.read_text())
    except (OSError,ValueError):raise ValueError('Sign into Codex with ChatGPT on the server before selecting account analysis.') from None
    if state.get('auth_mode')!='chatgpt' or not state.get('tokens'):
        raise ValueError('Codex must use a ChatGPT sign-in; API-key authentication is not allowed on this path.')
    # All analysis jobs sharing this sign-in serialize refresh/use of its cache.
    with open(home/'handoff-analysis.lock','a') as guard:
        deadline=time.monotonic()+timeout
        while True:
            checkpoint('Waiting for the ChatGPT-authenticated Codex analysis worker.')
            try:lock_file(guard.fileno(),blocking=False);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise ValueError('Codex analysis worker is busy; no provider was substituted.')
                time.sleep(.1)
        process=None
        try:
            with tempfile.TemporaryDirectory(prefix='sector-pulse-ai-') as temporary:
                folder=Path(temporary);schema_path=folder/'schema.json';output=folder/'analysis.json'
                schema_path.write_text(json.dumps(schema))
                # Ignore user/project tools and hooks. No broker credentials or API
                # keys enter this child environment; no order/execution tools exist.
                env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR')}
                env['CODEX_HOME']=str(home)
                command=[str(binary),'exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check',
                         '--sandbox','read-only','--cd',str(folder),'--color','never','--json',
                         '--config','forced_login_method="chatgpt"','--config','web_search="disabled"',
                         '--config','suppress_unstable_features_warning=true','--config','model_reasoning_effort="low"','--enable','skip_host_skill_discovery',
                         '--output-schema',str(schema_path),'--output-last-message',str(output)]
                for feature in ('shell_tool','unified_exec','apps','plugins','hooks','browser_use','browser_use_external',
                                'computer_use','image_generation','view_image','multi_agent','goals','sleep_tool','tool_suggest','skill_search','daemon_auto_start'):
                    command+=['--disable',feature]
                command+=['-']
                prompt=instructions+'\nUse only the following public market evidence. Do not use tools or read files.\n'+json.dumps(evidence,allow_nan=False)
                with open(folder/'events.jsonl','w+') as events,open(folder/'diagnostics.log','w+') as diagnostics:
                    checkpoint('Reviewing public broker evidence with your Codex account.')
                    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=events,stderr=diagnostics,env=env,
                                             text=True,start_new_session=os.name!='nt')
                    process.stdin.write(prompt);process.stdin.close()
                    while process.poll() is None:
                        checkpoint('Codex account analysis is running; this job can be stopped.')
                        if time.monotonic()>=deadline:raise ValueError('Codex account analysis timed out; no provider was substituted.')
                        if events.tell()>2_000_000 or diagnostics.tell()>2_000_000:raise ValueError('Codex output exceeded its bounded size.')
                        for line in (folder/'events.jsonl').read_text().splitlines():
                            try:event=json.loads(line)
                            except ValueError:continue
                            check_event(event)
                        time.sleep(.2)
                    if process.returncode!=0 or not output.exists():
                        raise ValueError('Codex account analysis failed. Check its ChatGPT sign-in and account limits; no API-key fallback was used.')
                    if output.stat().st_size>100000:raise ValueError('Codex structured output exceeds its bounded size.')
                    try:value=json.loads(output.read_text())
                    except (ValueError,OSError):raise ValueError('Codex returned invalid structured analysis.') from None
                    events.seek(0);usage={}
                    for line in events:
                        try:event=json.loads(line)
                        except ValueError:continue
                        check_event(event)
                        if event.get('type')=='turn.completed':usage=event.get('usage',{})
                    return value,usage
        finally:
            if process is not None and process.poll() is None:
                if os.name!='nt':os.killpg(process.pid,signal.SIGTERM)
                else:process.terminate()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name!='nt':os.killpg(process.pid,signal.SIGKILL)
                    else:process.kill()
                    process.wait(timeout=3)
            unlock_file(guard.fileno())
