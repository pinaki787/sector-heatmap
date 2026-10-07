"""Bounded, cached OpenAI experiment reviews. Never price/decision/order calls."""
from datetime import datetime
from pathlib import Path
import hashlib,json,os,re,shlex,threading,time
import requests
from .delta_backtest import IST

INSTRUCTIONS=('You review a futures research experiment, not live trades. Use only supplied aggregate evidence. '
 'Explain uncertainty, small samples, costs, regime mismatch and lack of prospective/final holdout proof. '
 'Never claim validation, profit guarantees or authorize execution. Propose at most two bounded RSI/MA/Bollinger '
 'parameter variants to test later. Output JSON with review (string) and experiments (array of objects with '
 'rsi_length (2..100), ma_length (2..100), ma_type (EMA or SMA), filter (BASELINE, EXPANDING or SQUEEZE_RELEASE), '
 'reason (string)). Keep review under 80 words and each experiment reason under 20 words. No code, tools or external actions.')


def existing_key(workspace):
    key=os.environ.get('OPENAI_API_KEY','').strip()
    if key:return key
    path=Path(workspace)/'.env.local'
    if path.is_file():
        for line in path.read_text().splitlines():
            match=re.match(r'^\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*(.*?)\s*$',line)
            if match:
                try:return shlex.split(match[1],comments=True)[0]
                except (ValueError,IndexError):return ''
    return ''


class ResearchAI:
    def __init__(self,path,workspace,clock=time.time,sender=None,key_reader=None):
        self.path=Path(path);self.workspace=workspace;self.clock=clock;self.lock=threading.RLock()
        self.sender=sender or self._send;self.key_reader=key_reader or (lambda:existing_key(workspace))
        self.data={'days':{},'cache':{},'status':'NOT_CHECKED','last_error':None}
        if self.path.exists():self.data=json.loads(self.path.read_text())
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,allow_nan=False));tmp.chmod(0o600);tmp.replace(self.path)
    def day(self):return datetime.fromtimestamp(self.clock(),IST).strftime('%Y-%m-%d')
    def status(self,limits):
        with self.lock:
            usage=self.data['days'].get(self.day(),dict(calls=0,charged_tokens=0,reported_tokens=0))
            return dict(provider='OpenAI',model=limits['model'],key_present=bool(self.key_reader()),enabled=limits['enabled'],state=self.data['status'],last_error=self.data['last_error'],day_ist=self.day(),usage=usage,limits=limits,cache_entries=len(self.data['cache']),budget_basis='UTF-8 input bytes + 256 framing reserve + maximum output tokens; failures retain the full reservation. Actual provider usage is recorded separately.')
    def _send(self,key,model,input_text,max_output):
        try:
            response=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json=dict(model=model,instructions=INSTRUCTIONS,input=input_text,max_output_tokens=max_output,store=False,text={'format':{'type':'json_object'}}),timeout=45,allow_redirects=False)
        except requests.RequestException:raise ValueError('OpenAI review connection failed; reservation retained, no automatic retry.') from None
        if response.status_code!=200:
            code='';detail=''
            try:
                error=response.json().get('error',{});code=str(error.get('code') or '');detail=str(error.get('message') or '')[:300]
                detail=detail.replace(key,'[redacted]');detail=re.sub(r'sk-[A-Za-z0-9_-]+','[redacted]',detail)
            except (ValueError,AttributeError):pass
            code=code if re.fullmatch(r'[a-zA-Z0-9_]{0,80}',code) else ''
            raise ValueError(f'OpenAI review failed (HTTP {response.status_code}{", "+code if code else ""}); {detail or 'provider rejected the bounded request'}; no automatic retry.')
        raw=response.json();text=''.join(c.get('text','') for item in raw.get('output',[]) if item.get('type')=='message' for c in item.get('content',[]) if c.get('type')=='output_text')
        if raw.get('status')!='completed':raise ValueError('OpenAI review incomplete; reservation retained.')
        return text,raw.get('usage',{}).get('total_tokens')
    def review(self,evidence,limits):
        with self.lock:
            if not limits['enabled']:return dict(state='DISABLED',review='AI reviews are disabled. Deterministic research remains available.',experiments=[])
            key=self.key_reader()
            if not key:self.data.update(status='UNAVAILABLE',last_error='Existing OPENAI_API_KEY unavailable; deterministic research continues.');self.save();return dict(state='UNAVAILABLE',review=self.data['last_error'],experiments=[])
            text='Research evidence JSON:\n'+json.dumps(evidence,sort_keys=True,separators=(',',':'),allow_nan=False)
            reservation=len(text.encode())+len(INSTRUCTIONS.encode())+256+limits['max_output_tokens']
            digest=hashlib.sha256((limits['model']+INSTRUCTIONS+text).encode()).hexdigest()
            if digest in self.data['cache']:return dict(self.data['cache'][digest],state='CACHED')
            if len(text.encode())>4000:return dict(state='INPUT_LIMIT',review='Compact evidence exceeds the 4,000-byte input cap; no call made.',experiments=[])
            usage=self.data['days'].setdefault(self.day(),dict(calls=0,charged_tokens=0,reported_tokens=0))
            if usage['calls']>=limits['calls_per_day'] or usage['charged_tokens']+reservation>limits['tokens_per_day']:
                self.data.update(status='BUDGET_LIMIT',last_error=None);self.save();return dict(state='BUDGET_LIMIT',review='Daily AI call or conservative token budget exhausted.',experiments=[])
            usage['calls']+=1;usage['charged_tokens']+=reservation;self.data.update(status='CALLING',last_error=None);self.save()
        try:
            response,actual=self.sender(key,limits['model'],text,limits['max_output_tokens'])
            decoded=json.loads(response);review=decoded['review']
            if not isinstance(review,str) or not isinstance(decoded.get('experiments',[]),list):raise ValueError('Invalid review schema.')
            proposals=[]
            for item in decoded.get('experiments',[])[:2]:
                if not isinstance(item,dict):continue
                if any(isinstance(item.get(k),bool) or not isinstance(item.get(k),int) or not 2<=item[k]<=100 for k in ('rsi_length','ma_length')):continue
                if item.get('ma_type') not in ('SMA','EMA') or item.get('filter') not in ('BASELINE','EXPANDING','SQUEEZE_RELEASE'):continue
                proposals.append({k:item[k] for k in ('rsi_length','ma_length','ma_type','filter')}|{'reason':str(item.get('reason',''))[:300]})
            result=dict(state='COMPLETE',review=review[:2000],experiments=proposals,reported_tokens=actual,reserved_tokens=reservation,at=self.clock())
            with self.lock:
                if isinstance(actual,int) and actual>=0:usage['reported_tokens']+=actual
                # Charge reservations, not estimates/refunds: guarantees a conservative app cap.
                self.data.update(status='VERIFIED',last_error=None);self.data['cache'][digest]=result
                if len(self.data['cache'])>100:self.data['cache'].pop(next(iter(self.data['cache'])))
                self.save()
            return result
        except Exception as error:
            message=str(error) if isinstance(error,ValueError) and str(error).startswith('OpenAI ') else 'OpenAI review output was unavailable or invalid; reservation retained.'
            with self.lock:self.data.update(status='ERROR',last_error=message);self.save()
            return dict(state='ERROR',review=message,experiments=[])
