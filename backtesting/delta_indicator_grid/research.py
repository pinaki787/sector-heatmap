"""Standalone public futures experiment. Never imports a broker/order client.

Existing RSI implementation is preserved. ATR/Supertrend/price EMA are research
implementations; their formulas and execution timing are independently tested.
"""
import json, math, threading, time
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
from sector_heatmap.delta_backtest import DeltaBacktest, INTERVALS, IST, plan, bollinger_features, adverse_fill
from sector_heatmap.delta_backtest_server import public_read, public_metadata
from sector_heatmap.delta_signals import delta_rsi_series

ROOT=Path(__file__).resolve().parent

def indicators(rows, period=14, multiplier=3, ema_length=50):
    """Wilder ATR seeded by period TRs; EMA seeded by length closes.
    Supertrend starts bearish at first valid ATR; changes on completed close.
    """
    result=[];trs=[];atr=None;ema=None;upper=lower=None;side=-1
    for i,r in enumerate(rows):
        tr=r['high']-r['low'] if not i else max(r['high']-r['low'],abs(r['high']-rows[i-1]['close']),abs(r['low']-rows[i-1]['close']))
        trs.append(tr)
        if i==period-1:atr=sum(trs)/period
        elif i>=period:atr=(atr*(period-1)+tr)/period
        if i==ema_length-1:ema=sum(x['close'] for x in rows[:ema_length])/ema_length
        elif i>=ema_length:ema+=2/(ema_length+1)*(r['close']-ema)
        if atr is not None:
            bu=(r['high']+r['low'])/2+multiplier*atr;bl=(r['high']+r['low'])/2-multiplier*atr
            if upper is None:upper,lower=bu,bl
            else:
                prev_upper,prev_lower=upper,lower
                upper=bu if bu<upper or rows[i-1]['close']>upper else upper
                lower=bl if bl>lower or rows[i-1]['close']<lower else lower
                if side<0 and r['close']>upper:side=1
                elif side>0 and r['close']<lower:side=-1
        result.append(dict(atr=atr,ema=ema,supertrend=side if atr is not None else None))
    return result

def run_sim(rows, signals, bb, ind, cfg, settings, units, tick, lo, hi, detail=False):
    """Entry/opposite-cross fills next open; stops intrabar against prior stop.
    Trailing stop is updated at completed close for the NEXT candle only.
    Stop gaps fill at worse open; no same-candle reentry; no targets.
    """
    cash=settings['capital'];qty=settings['contracts']*units;position=None;pending=None
    trades=[];curve=[];peak=cash;dd=0.;fees=0.;funding=0.;skips=0
    indices=[i for i,r in enumerate(rows) if lo<=r['timestamp']<hi]
    interval=INTERVALS[cfg['resolution']]
    def close(raw,stamp,reason):
        nonlocal cash,position,fees,funding
        p=position;fill=adverse_fill(raw,-p['side'],settings,tick)
        fee=fill*qty*settings['fee_bps']/10000
        drag=p['fill']*qty*settings['funding_bps_day']/10000*max(0,stamp-p['time'])/86400
        gross=(fill-p['fill'])*qty*p['side'];net=gross-p['fee']-fee-drag
        cash+=gross-fee-drag;fees+=fee;funding+=drag
        trades.append(dict(entry_time=p['time'],exit_time=stamp,side=p['side'],entry=p['fill'],exit=fill,net_pnl=net,exit_reason=reason))
        position=None
    for offset,i in enumerate(indices):
        r=rows[i];stamp=r['timestamp'];exited=False
        if pending:
            action,side,a=pending
            if action=='EXIT' and position:close(r['open'],stamp,'OPPOSITE_CROSSOVER');exited=True
            elif action=='ENTRY' and not position:
                fill=adverse_fill(r['open'],side,settings,tick);fee=fill*qty*settings['fee_bps']/10000
                if fill*qty+fee<=cash:
                    cash-=fee;fees+=fee
                    stop=fill-side*cfg['atr_exit']*a if cfg['atr_exit'] else None
                    position=dict(side=side,fill=fill,time=stamp,fee=fee,stop=stop)
                else:skips+=1
            pending=None
        if position and position['stop'] is not None:
            p=position;s=p['stop'];hit=r['low']<=s if p['side']>0 else r['high']>=s
            if hit:
                raw=min(r['open'],s) if p['side']>0 else max(r['open'],s)
                # Exact intrabar timestamp is unknown; use candle close conservatively for funding.
                close(raw,stamp+interval,'ATR_STOP');exited=True
        held=position is not None
        if offset<len(indices)-1:
            if rows[indices[offset+1]]['timestamp']!=stamp+interval:raise ValueError('Missing execution candle')
            cross=signals[i]['cross_direction']
            if held:
                if cross==('BEARISH' if position['side']>0 else 'BULLISH'):pending=('EXIT',0,0)
                if cfg['atr_exit'] and ind[i]['atr'] is not None:
                    candidate=r['close']-position['side']*cfg['atr_exit']*ind[i]['atr']
                    position['stop']=max(position['stop'],candidate) if position['side']>0 else min(position['stop'],candidate)
            elif not exited:
                direction=signals[i]['entry_direction'] if cfg['entry_rule']=='CURRENT' else cross
                side=1 if direction=='BULLISH' else -1 if direction=='BEARISH' else 0
                gate=cfg['bb']=='BASELINE' or bb[i]['expanding'] if cfg['bb']!='SQUEEZE_RELEASE' else bb[i]['release']
                trend=cfg['trend'];ema=ind[i]['ema']
                trend_ok=trend=='NONE' or trend=='EMA50' and ema is not None and (r['close']-ema)*side>0 or trend=='SUPERTREND' and ind[i]['supertrend']==side
                if side and gate and trend_ok and ind[i]['atr'] is not None:pending=('ENTRY',side,ind[i]['atr'])
        mark=cash
        if position:
            drag=position['fill']*qty*settings['funding_bps_day']/10000*(stamp+interval-position['time'])/86400
            mark+=(r['close']-position['fill'])*qty*position['side']-drag
        if offset==len(indices)-1 and position:close(r['close'],stamp+interval,'PERIOD_END');mark=cash
        peak=max(peak,mark);dd=max(dd,100*(peak-mark)/peak)
        if detail:curve.append(dict(time=stamp+interval,equity=mark))
    positive=sum(max(0,t['net_pnl']) for t in trades);negative=-sum(min(0,t['net_pnl']) for t in trades)
    metrics=dict(trades=len(trades),net_pnl=cash-settings['capital'],return_percent=100*(cash/settings['capital']-1),max_drawdown_percent=dd,profit_factor=positive/negative if negative else None,win_rate=100*sum(t['net_pnl']>0 for t in trades)/len(trades) if trades else None,fees=fees,funding_drag=funding,skipped_capital=skips)
    return dict(metrics=metrics,**(dict(trades=trades,equity=curve) if detail else {}))

def main():
    report=dict(created_at=time.time(),method=dict(capital=10000,initial_exposure_percent=25,fee_bps=5.9,slippage_bps=2,half_spread_bps=1,funding_bps_day=1,selection='Training return minus twice training drawdown; minimum 20 training trades. Top three frozen before final 30% evaluation.',limitations='Underlying futures only; no options, leverage, liquidation or actual funding. Current contract specs. Finite grid, not all possible strategies. Close-mark drawdown; stop gaps may slip beyond assumed fills.'),datasets=[],failures=[])
    for symbol,res in product(('BTCUSD','ETHUSD'),('1m','5m','15m','30m','1h','6h','1d')):
        days=14 if res=='1m' else 75 if res=='5m' else 180 if res in ('15m','30m','1h') else 365
        end=datetime.now(IST).date()-timedelta(days=1);start=end-timedelta(days=days-1)
        payload=dict(symbol=symbol,resolutions=[res],start_date=str(start),end_date=str(end),rsi_lengths=[14],ma_lengths=[14],ma_types=['EMA'],filters=['BASELINE'])
        print(f'FETCH {symbol} {res} {start} through {end}',flush=True)
        try:
            config=plan(payload);bounds=config['ranges'][res]
            svc=DeltaBacktest(ROOT/'cache',public_read,public_metadata)
            svc.job=dict(plan=config,downloaded_windows=0,cached_windows=0,coverage={})
            meta=public_metadata(symbol)
            if not(meta['contract_type']=='perpetual_futures' and meta['notional_type']=='vanilla' and meta['is_quanto'] is False and meta['quoting_currency']==meta['settlement_currency']=='USD' and meta['contract_unit_currency']==meta['underlying']):raise ValueError('Contract identity invalid')
            rows=svc._fetch(symbol,res,bounds,threading.Event());units=float(meta['contract_value']);tick=float(meta['tick_size'])
            contracts=max(1,int(2500/(rows[config['warmup']]['close']*units)))
            settings=dict(capital=10000,contracts=contracts,fee_bps=5.9,slippage_bps=2,half_spread_bps=1,funding_bps_day=1)
            ind=indicators(rows);bbcfg=dict(bb_length=20,bb_deviation=2,squeeze_lookback=100,squeeze_percentile=20,release_bars=3)
            bb=bollinger_features(rows,bbcfg);split=bounds['start']+int(bounds['expected']*.7)*bounds['interval']
            signals={(r,m):delta_rsi_series(rows,r,m,'EMA') for r,m in product((10,14,21),(9,14,21))}
            candidates=[]
            for r,m,entry,b,trend,stop in product((10,14,21),(9,14,21),('CURRENT','CROSS_ONLY'),('BASELINE','EXPANDING','SQUEEZE_RELEASE'),('NONE','EMA50','SUPERTREND'),(0,2,3)):
                cfg=dict(resolution=res,rsi=r,rsi_ema=m,entry_rule=entry,bb=b,trend=trend,atr_exit=stop)
                train=run_sim(rows,signals[r,m],bb,ind,cfg,settings,units,tick,bounds['start'],split)['metrics']
                score=train['return_percent']-2*train['max_drawdown_percent'] if train['trades']>=20 else None
                candidates.append(dict(config=cfg,train=train,score=score))
            eligible=sorted((c for c in candidates if c['score'] is not None),key=lambda c:c['score'],reverse=True)
            frozen=eligible[:3]
            baseline=dict(resolution=res,rsi=14,rsi_ema=14,entry_rule='CURRENT',bb='BASELINE',trend='NONE',atr_exit=0)
            summaries=[]
            for c in frozen:
                cfg=c['config'];sig=signals[cfg['rsi'],cfg['rsi_ema']]
                c['held_out']=run_sim(rows,sig,bb,ind,cfg,settings,units,tick,split,bounds['end'],True)
                c['cost_stress']=run_sim(rows,sig,bb,ind,cfg,settings|dict(slippage_bps=5,half_spread_bps=2,funding_bps_day=3),units,tick,split,bounds['end'])['metrics']
                width=(split-bounds['start'])//(3*bounds['interval'])*bounds['interval']
                c['train_subperiods']=[run_sim(rows,sig,bb,ind,cfg,settings,units,tick,bounds['start']+j*width,split if j==2 else bounds['start']+(j+1)*width)['metrics'] for j in range(3)]
                summaries.append(c)
            base={segment:run_sim(rows,signals[14,14],bb,ind,baseline,settings,units,tick,lo,hi,True) for segment,lo,hi in [('train',bounds['start'],split),('held_out',split,bounds['end'])]}
            first=next(r['open'] for r in rows if r['timestamp']>=split);last=rows[-1]['close'];qty=contracts*units
            benchmark=qty*(last-first)-(first+last)*qty*(5.9+3)/10000-first*qty*(bounds['end']-split)/86400/10000
            dataset=dict(symbol=symbol,resolution=res,start_date=str(start),end_date=str(end),split=split,coverage=svc.job['coverage'],product=meta,settings=settings,combinations=len(candidates),eligible=len(eligible),selected=summaries,baseline=base,buy_hold_held_out_net_pnl=benchmark,training_grid=candidates)
            report['datasets'].append(dataset)
            print(f'DONE {symbol} {res}: {len(candidates)} combinations; eligible {len(eligible)}; selected held-out '+str([round(c['held_out']['metrics']['net_pnl'],2) for c in summaries]),flush=True)
        except Exception as exc:
            report['failures'].append(dict(symbol=symbol,resolution=res,error=str(exc)));print(f'BLOCKED {symbol} {res}: {exc}',flush=True)
        (ROOT/'results.json').write_text(json.dumps(report,allow_nan=False))
    print('COMPLETE',flush=True)

if __name__=='__main__':main()
