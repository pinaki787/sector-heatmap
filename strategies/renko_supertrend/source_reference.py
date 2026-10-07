"""Test-only evaluator of the arithmetic statements in the supplied Pine source.

This checks the port against source text, not a TradingView runtime export.
"""
import math
from pathlib import Path
from types import SimpleNamespace


def ternary(expression):
    expression=expression.strip();depth=0;commas=[]
    for i,ch in enumerate(expression):
        if ch=='(':depth+=1
        elif ch==')':depth-=1
        elif depth==0 and ch==',':commas.append(i)
    if commas:
        positions=[-1]+commas+[len(expression)]
        return ', '.join(ternary(expression[a+1:b]) for a,b in zip(positions,positions[1:]))
    depth=0;question=None;nest=0
    for i,ch in enumerate(expression):
        if ch=='(':depth+=1
        elif ch==')':depth-=1
        elif depth==0 and ch=='?':
            if question is None:question=i
            else:nest+=1
        elif depth==0 and ch==':' and question is not None:
            if nest:nest-=1
            else:return f'({ternary(expression[question+1:i])} if {ternary(expression[:question])} else {ternary(expression[i+1:])})'
    result='';i=0
    while i<len(expression):
        if expression[i]!='(':
            result+=expression[i];i+=1;continue
        start=i;depth=1;i+=1
        while depth:
            if expression[i]=='(':depth+=1
            elif expression[i]==')':depth-=1
            i+=1
        result+='('+ternary(expression[start+1:i-1])+')'
    return result.replace('true','True').replace('false','False')


def rma(values,length):
    result=[];seed=[];value=math.nan
    for x in values:
        if not math.isnan(x):
            if math.isnan(value):
                seed.append(x)
                if len(seed)==length:value=sum(seed)/length
            else:value=(x/length)+((1-1/length)*value)
        result.append(value)
    return result


def reference(candles,config,tick=.05):
    source=(Path(__file__).with_name('source.pine')).read_text()
    lines=source[source.index('float hostTr ='):source.index('bullPlot =')].splitlines()
    tr=[max(c['high']-c['low'],abs(c['high']-candles[i-1]['close']),abs(c['low']-candles[i-1]['close'])) if i else c['high']-c['low'] for i,c in enumerate(candles)]
    atrs={length:rma(tr,length) for length in {config['atr_length'],9,15}}
    def pine_max(*xs):return math.nan if any(math.isnan(x) for x in xs) else max(xs)
    env=dict(autoLength=config['atr_length'],stLength=config['atr_length'],factor=config['factor'],brickMode=config['brick_mode'],manualBrick=config['manual_brick'],
             syminfo=SimpleNamespace(mintick=tick),na=lambda x:math.isnan(x),
             math=SimpleNamespace(max=pine_max,min=lambda *xs:-pine_max(*[-x for x in xs]),floor=math.floor,abs=abs,sign=lambda x:1 if x>0 else -1 if x<0 else 0),int=int)
    def evaluate(expr):
        if expr.strip()=='na':return math.nan
        return eval(ternary(expr),{'__builtins__':{}},env)
    def execute(block):
        i=0
        while i<len(block):
            text=block[i].strip()
            if not text:i+=1;continue
            if text.startswith('if '):
                branches=[]
                while i<len(block):
                    head=block[i].strip()
                    condition=head[3:] if head.startswith('if ') else head[8:] if head.startswith('else if ') else None
                    i+=1;body=[]
                    while i<len(block) and (not block[i].strip() or block[i].startswith('    ')):
                        body.append(block[i][4:]);i+=1
                    branches.append((condition,body))
                    if i==len(block) or not block[i].strip().startswith('else'):break
                for condition,body in branches:
                    if condition is None or evaluate(condition):execute(body);break
                continue
            is_var=text.startswith('var ')
            if is_var:text=text[4:]
            for prefix in ('float ','int '):
                if text.startswith(prefix):text=text[len(prefix):]
            op=next(op for op in (':=','+=','=') if op in text)
            key,expr=text.split(op,1);key=key.strip()
            if not is_var or key not in env:
                value=evaluate(expr)
                env[key]=env[key]+value if op=='+=' else value
            i+=1
    result=[]
    for i,c in enumerate(candles):
        env.update(close=c['close'],ta=SimpleNamespace(tr=lambda _:tr[i],atr=lambda length:atrs[length][i]))
        previous_direction=env.get('direction',1)
        execute(lines)
        names=['hostAtr','regimeAtr','lowAtr','volatilityRatio','effectiveFactor','autoBox','box','rc','ro','syntheticAtr','upper','lower','st','direction']
        row={key:None if isinstance(env[key],float) and math.isnan(env[key]) else env[key] for key in names}
        row.update(buy=env['direction']<0 and previous_direction>0,sell=env['direction']>0 and previous_direction<0)
        result.append(row)
    return result
