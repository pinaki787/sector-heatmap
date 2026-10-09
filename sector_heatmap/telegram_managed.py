"""New Telegram recommendations -> trigger watch -> owned Renko option entry.

No spot trades. No adoption gap: the Renko runner owns durable order intent,
partial fills, reconciliation and exits from the initial submission onward.
"""
import hashlib,json,os,re,threading,time
from pathlib import Path
from copy import deepcopy
from .telegram_options import recommendation_plan,resolve_at_trigger,trigger_satisfied

class OptionTickets:
 """Explicit user-click Paper/Live tickets, using the Renko owner from entry."""
 def __init__(self,delta,parse,runner_factory,template,clock=time.time,polling=None):
  self.delta=delta;self.parse=parse;self.runner_factory=runner_factory;self.template=template;self.clock=clock;self.polling=polling;self.tickets={};self.lock=threading.RLock()
 def preview(self,p):
  import secrets
  text=str(p.get('text') or '')
  if p.get('queue_id') and self.polling:text=self.polling.snapshot(p['queue_id'],p.get('revision'))['text']
  symbols=set(re.findall(r'\b(?:BTCUSD|ETHUSD|XAUUSD|XAUTUSD)\b',text.upper()))
  if len(symbols)!=1:raise ValueError('Use one supported BTCUSD, ETHUSD, XAUTUSD or explicitly mapped XAUUSD recommendation.')
  original=next(iter(symbols));proxy=original=='XAUUSD'
  if proxy and p.get('gold_proxy') is not True:raise ValueError('Select the disclosed XAUUSD→XAUT option proxy for this ticket.')
  symbol='XAUTUSD' if proxy else original;plan=recommendation_plan(self.parse(text),symbol)
  route=self.delta.chart_option(symbol,'BUY' if plan['direction']=='BULLISH' else 'SELL')
  from strategies.renko_supertrend.delta_contracts import option_contract
  meta=option_contract(route['product'],self.clock());q=route['quote']
  if route['signal_symbol']!=symbol or meta['option_type']!=plan['option_type'] or route.get('side')!='buy' or meta['expiry_epoch']-self.clock()<=60:raise ValueError('Exact long ATM option route unavailable or inside expiry protection.')
  if q['symbol']!=meta['symbol'] or not 0<=self.clock()-q['exchange_at']<=15 or not 0<q['bid']<=q['ask']:raise ValueError('Fresh exact option quote required.')
  cfg=deepcopy(self.template());cfg.update(underlying=symbol,execution_route='OPTIONS',broker='DELTA_INDIA',price_source='PERPETUAL_LAST_TRADE',order_terms='MARKETABLE_LIMIT_IOC')
  # Price recommendations stay references. No gold level or premium substitution.
  cfg.update(spot_target=None,spot_stop=None)
  fees=None
  try:
   from strategies.renko_supertrend.delta_costs import MODEL
   index=float(route['underlying_price']);rate=float(route['product']['taker_commission_rate']);units=meta['quantity_multiplier']
   commission=min(units*index*rate,units*q['ask']*MODEL['premium_cap'])
   fees=dict(entry_commission_usd_per_contract=commission,entry_gst_usd_per_contract=commission*MODEL['gst'],entry_total_usd_per_contract=commission*(1+MODEL['gst']),basis='Entry estimate from fresh route index/product taker rate; estimated GST. No exit costs, discounts or invoice claims.')
  except (KeyError,TypeError,ValueError):pass
  conversion=self.delta._inr_conversion() if hasattr(self.delta,'_inr_conversion') else None
  if not isinstance(conversion,dict):conversion=None
  token=secrets.token_urlsafe(24);ticket=dict(ticket_id=token,text=text,plan=plan,original_underlying=original,gold_proxy=proxy,contract=meta,quote=q,renko_settings=cfg,expires_at=self.clock()+120,time_to_expiry_seconds=meta['expiry_epoch']-self.clock(),entry_policy='EXPLICIT_NOW_OPTION_IOC',trigger_policy='USER_CONFIRMS_NOW; underlying recommendation levels are references, not pending triggers',stop_target_policy='Selected Renko exits; recommendation stop/targets are references only',state='PREVIEW',quantity=None,fees=fees,inr_conversion=conversion,queue_id=p.get('queue_id'),revision=p.get('revision'),connection_route=getattr(self.polling,'route',None))
  with self.lock:self.tickets[token]=deepcopy(ticket)
  return ticket
 def submit(self,p):
  with self.lock:
   t=self.tickets.get(p.get('ticket_id'))
   if not t or self.clock()>t['expires_at']:raise ValueError('Reparse a fresh option ticket.')
   if t['state']!='PREVIEW':return deepcopy(t.get('result') or dict(state=t['state'],message='Ticket consumed; reconcile its Renko owner. Never resubmit.'))
   if p.get('text')!=t['text']:raise ValueError('Recommendation changed. Reparse.')
   if t.get('queue_id') and self.polling:
    if getattr(self.polling,'route',None)!=t['connection_route']:raise ValueError('Connection changed; reparse.')
    self.polling.snapshot(t['queue_id'],t['revision'])
   mode=p.get('mode');qty=p.get('quantity')
   if mode not in ('PAPER','LIVE') or isinstance(qty,bool) or not str(qty).isdigit() or not 1<=int(qty)<=100000:raise ValueError('Choose Paper/Live and explicitly enter whole option contracts.')
   if p.get('entry_confirmed') is not True:raise ValueError('Confirm immediate option entry and displayed Renko exit settings; underlying levels are references.')
   cfg=deepcopy(t['renko_settings']);cfg.update(mode=mode,lots=int(qty))
   cfg.update(timeframe=p.get('timeframe'),ema_exit_enabled=p.get('ema_exit_enabled'),ema_exit_length=p.get('ema_exit_length'),supertrend_exit_enabled=p.get('supertrend_exit_enabled'))
   from strategies.renko_supertrend.delta_contracts import configuration
   cfg=configuration(cfg)
   if not (cfg.get('ema_exit_enabled') or cfg.get('supertrend_exit_enabled') or cfg.get('trailing_enabled')):raise ValueError('Select at least one Renko exit.')
   # Re-resolve to reject ATM/expiry changes before consuming the reviewed ticket.
   route=self.delta.chart_option(cfg['underlying'],'BUY' if t['plan']['direction']=='BULLISH' else 'SELL')
   if route['symbol']!=t['contract']['symbol']:raise ValueError('ATM contract changed; reparse and review the new option.')
   runner=self.runner_factory(cfg['underlying'])
   if runner.state.get('running') or runner.state.get('position') or runner.state.get('pending'):raise ValueError('This Renko instance is active or holds exposure. No competing owner or adoption.')
   t['state']='CONSUMED';t['request_id']='TG'+hashlib.sha256(t['ticket_id'].encode()).hexdigest()[:30]
   if t.get('queue_id') and self.polling:self.polling.reserve(t['queue_id'],t['revision'],t['request_id'])
   try:
    result=runner.telegram_entry(dict(cfg,configuration_revision=runner.runtime_revision,direction=t['plan']['direction'],request_id=t['request_id'],expected_contract=t['contract']['symbol'],telegram_trigger=p.get('telegram_trigger'),telegram_valid_until=p.get('telegram_valid_until')))
    t['result']=dict(broker='DELTA_INDIA',mode=mode,management_owner='RENKO_SUPERTREND',run_id=result.get('run_id'),status='RENKO_PENDING_RECONCILIATION' if result.get('pending') else 'RENKO_CONFIRMED_POSITION' if result.get('position') else 'NO_CONFIRMED_FILL',position=deepcopy(result.get('position')),pending=deepcopy(result.get('pending')),message=result.get('message'))
   except Exception:t['state']='UNCERTAIN_OR_BLOCKED';raise
   return deepcopy(t['result'])
