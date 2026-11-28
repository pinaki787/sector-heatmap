"""Optional daily strategy/account loss admission. Never submits or closes orders."""
import math,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from strategies.nifty_ai_options import trade_journal

def optional_amount(value):
 if value in (None,''):return None
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
  raise ValueError('Daily maximum loss must be a positive amount, or blank to disable')
 return value

def evaluate(config,rows,*,now=None,latched=False):
 limit=optional_amount(config.get('daily_max_loss'))
 if limit is None:return dict(enabled=False,blocked=False)
 now=time.time() if now is None else now
 day=datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata')).replace(hour=0,minute=0,second=0,microsecond=0)
 start=day.timestamp();end=(day+timedelta(days=1)).timestamp()
 selected=[r for r in rows if r.get('account')==config['account'] and r.get('broker')==config['broker'] and r.get('mode')==config['execution_mode'] and r.get('status')=='CLOSED' and isinstance(r.get('exit_time'),(int,float)) and start<=r['exit_time']<end]
 currencies={r.get('currency') for r in selected}
 values=[trade_journal.calculated(r,now)['gross_profit'] for r in selected]
 ready=all(v is not None and math.isfinite(v) for v in values) and len(currencies)<=1 and None not in currencies
 pnl=sum(values) if ready else None
 hit=latched or (ready and pnl<=-limit)
 return dict(enabled=True,blocked=bool(hit or not ready),limit=limit,realized_gross=pnl,
  currency=next(iter(currencies),None),day=day.date().isoformat(),closed_trades=len(selected),
  basis='TODAY_STRATEGY_ACCOUNT_REALIZED_GROSS',fees_included=False,
  reason='DAILY_LOSS_LIMIT_REACHED' if hit else 'DAILY_LOSS_EVIDENCE_UNAVAILABLE' if not ready else 'WITHIN_DAILY_LOSS_LIMIT',
  exits_continue=True)

def check(executor):
 config=getattr(executor,'runner_config',{})
 if config.get('daily_max_loss') in (None,''):return dict(enabled=False,blocked=False)
 data=executor.runner_data;owner=config['account']
 # Incremental journal ingestion is performed only at entry admission, never on ticks.
 trade_journal.sync_account(owner,data)
 db=trade_journal.connect(data,owner)
 try:rows=[dict(r) for r in db.execute("SELECT * FROM trades WHERE account=? AND broker=? AND mode=? AND status='CLOSED'",(owner,config['broker'],config['execution_mode']))]
 finally:db.close()
 from pathlib import Path
 from strategies.nifty_ai_options.run import atomic
 latch=Path(data)/'risk-limits'/owner/(config['broker']+'-'+config['execution_mode']+'.json')
 previous=__import__('json').loads(latch.read_text()) if latch.exists() else {}
 today=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
 result=evaluate(config,rows,latched=previous.get('day')==today and previous.get('reason')=='DAILY_LOSS_LIMIT_REACHED')
 if result['reason']=='DAILY_LOSS_LIMIT_REACHED':atomic(latch,result)
 executor.state['daily_loss_filter']=result;executor.save()
 return result
