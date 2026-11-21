from pathlib import Path
root=Path.cwd()
def edit(name,old,new):
 p=root/name;s=p.read_text();assert s.count(old)==1,(name,old[:80],s.count(old));p.write_text(s.replace(old,new,1))
edit('sector_heatmap/web.py',"""                    cached['retry_at'] = time.monotonic() + 30""","""                    attempts = cached.get('retry_attempts',0)+1
                    cached['retry_attempts'] = attempts
                    cached['retry_at'] = time.monotonic() + (min(30,2**min(attempts-1,5)) if force_refresh else 30)""")
edit('strategies/renko_supertrend/chart_history.py',"""    def __init__(self,path,min_interval=.35):
        self.path=Path(path);self.lock=threading.RLock();self.memory={}""","""    def __init__(self,path,min_interval=.35,tail_provider=None):
        self.path=Path(path);self.lock=threading.RLock();self.memory={}
        self.tail_provider=tail_provider""")
edit('strategies/renko_supertrend/chart_history.py',"""                        response=bounded_history(client,dict(symbol=symbol,resolution=str(seconds//60),date_format=1,range_from=str(cursor),range_to=str(stop),cont_flag=0,oi_flag=1))""","""                        if self.tail_provider and entry.get('complete') and cursor==last and last==datetime.fromtimestamp(now,IST).date():
                            shared=self.tail_provider(symbol,timeframe)
                            response={'s':'ok','candles':[[r['timestamp'],r['open'],r['high'],r['low'],r['close'],r.get('volume')] for r in shared if datetime.fromtimestamp(r['timestamp'],IST).date()==last]}
                        else:
                            response=bounded_history(client,dict(symbol=symbol,resolution=str(seconds//60),date_format=1,range_from=str(cursor),range_to=str(stop),cont_flag=0,oi_flag=1))""")
edit('sector_heatmap/web.py',"""    renko_chart_history = RenkoChartHistory(ROOT / ".private" / "renko-chart-history")""","""    def shared_renko_tail(symbol,timeframe):
        return renko_broker.candles({'underlying':symbol,'timeframe':timeframe})
    renko_chart_history = RenkoChartHistory(ROOT / ".private" / "renko-chart-history",tail_provider=shared_renko_tail)""")
edit('sector_heatmap/web.py',"""RenkoChartHistory(folder/'chart-history'),order_stream""","""RenkoChartHistory(folder/'chart-history',tail_provider=shared_renko_tail),order_stream""")
edit('renko-supertrend.js',"""  function lastKnownIndicator(point,fresh=true){""","""  function feedHealthSummary(data={},elapsed=0){
    const h=chartStreamHealth(data,elapsed),c=data.confirmed_indicators||data.runner?.confirmed_indicators;
    const prices=h.text.startsWith('Market closed')?'outside regular session':h.tickFresh?'live':'awaiting fresh ticks';
    const candles=data.candles?.error?'retrieval recovering':data.candles?.busy?'refreshing in background':data.candles?.latest_completed?'broker cache ready':'awaiting broker candles';
    return 'Prices: '+prices+' · Candles: '+candles+' · Indicators: '+(c?'confirmed '+new Date(c.last_at*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'}):'awaiting confirmed state')+' · Orders: '+(h.ordersConnected?'connected':h.restOrders?'API reconciliation':'reconciliation / stream unavailable');
  }
  function lastKnownIndicator(point,fresh=true){""")
edit('renko-supertrend.js',"""    el('chart-toolbar').append(basisLabel,basisNote);""","""    const healthNote=document.createElement('div');healthNote.id='renko-feed-health';healthNote.setAttribute('role','status');healthNote.style.cssText='flex-basis:100%;font-size:12px;color:#a9bbcd;padding:6px 0';
    el('chart-toolbar').append(basisLabel,basisNote,healthNote);""")
edit('renko-supertrend.js',"""paintUnderlyingPrice(health);el('stream-status').textContent""","""paintUnderlyingPrice(health);if(el('feed-health'))el('feed-health').textContent=feedHealthSummary(statusFrame||{},statusReceived?(performance.now()-statusReceived)/1000:Infinity);el('stream-status').textContent""")
edit('renko-supertrend.js',"""priceFresh?'Live':nativeCashSessionClosed()?'Market closed · native capture resumes next session':'Last known · feed delayed'""","""priceFresh?'Live':health.text.startsWith('Market closed')?'Outside regular session':nativeCashSessionClosed()?'Market closed · native capture resumes next session':'Last known · feed delayed'""")
edit('renko-supertrend.js',"""feedPresentation,lastKnownIndicator""","""feedPresentation,feedHealthSummary,lastKnownIndicator""")
print('Background shared tail and separate health wired.')
