"""Admin-assigned dashboard sections, enforced before account API dispatch."""
FEATURES={'sectors':'Sector rotation','handoff':'Analysis handoff','straddles':'Long Straddles','broker':'Live feed & positions','screener':'Screener','settings':'Risk Guardrails','ema-band':'EMA Band','renko-supertrend':'Renko Supertrend','ema-cross':'RSI based SMA','kama':'KAMA Strategy','delta-india':'Delta India','trade-parser':'FYERS Trade Parser','telegram-parser':'Telegram Trade Parser'}
COMMON={'/api/auth/status','/api/auth/start','/api/workspace-context','/api/paper-capital/status'}
PREFIXES=[('/api/renko-',{'renko-supertrend'}),('/api/ema-crossover/',{'ema-cross'}),('/api/ema-band/',{'ema-band'}),('/api/kama/',{'kama'}),('/api/delta-india/',{'delta-india'}),('/api/analysis-handoff/',{'handoff'}),('/api/trade-ticket/',{'handoff'}),('/api/chartink/',{'screener'}),('/api/automation/',{'settings'}),('/api/trade-recommendation/',{'trade-parser','telegram-parser'}),('/api/telegram/',{'telegram-parser'}),('/api/whatsapp/',{'trade-parser'}),('/api/sector-analysis',{'sectors'}),('/api/heatmap',{'sectors'}),('/api/rsi-table',{'ema-cross','sectors'}),('/api/account',{'broker'}),('/api/live-pnl',{'broker'}),('/api/realized-pnl',{'broker'})]
def allowed(user,path):
 if user.get('admin') or not path.startswith('/api/'):return True
 if path in COMMON:return True
 assigned=set(user.get('features',[]))
 if path in {'/api/ema-band/underlying-search','/api/ema-band/master-search','/api/ema-band/master-status','/api/ema-band/atm-option'}:
  return bool(assigned & {'ema-band','renko-supertrend','kama','ema-cross','handoff'})
 if any(path.startswith(p) for p in ['/api/nifty-straddle','/api/sensex-straddle','/api/straddle-squareoff/']):return 'straddles' in assigned
 for prefix,features in PREFIXES:
  if path.startswith(prefix):return bool(assigned & features)
 return False
