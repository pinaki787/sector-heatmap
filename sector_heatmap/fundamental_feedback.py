"""AI-selected, report-only financial context shared by Handoff and Holdings."""
from copy import deepcopy
INSTRUCTIONS=('Also return fundamental_feedback for each company using ONLY its supplied financial filing evidence. '
'Keep technical recommendation decisions based on technical evidence; fundamentals are separate report-only context, never a new order filter. '
'Address profitability/financial-health limits, growth, valuation, and key risks. Do not call technical momentum fundamentals. '
'Missing growth comparisons, cash flows, debt, or valuation MUST be called unavailable, never zero or healthy/cheap. '
'Use reporting period/as-of; stale or unavailable evidence requires INSUFFICIENT_EVIDENCE. '
'Choose SUPPORTS, CONFLICTS, MIXED or INSUFFICIENT_EVIDENCE relative to the stated technical/holding action. '
'Long-term company strength can conflict with a short-term bearish trade without invalidating it. '
'Keep the whole fundamental feedback under 140 words; do not invent metrics, forecasts, filings or links.')
FEEDBACK_SCHEMA=dict(type='object',properties={**{k:dict(type='string') for k in ('financial_health','growth','valuation','summary')},'key_risks':dict(type='array',items=dict(type='string')),'relationship':dict(type='string',enum=['SUPPORTS','CONFLICTS','MIXED','INSUFFICIENT_EVIDENCE'])},required=['financial_health','growth','valuation','summary','key_risks','relationship'],additionalProperties=False)
def schema(base):
 s=deepcopy(base);item=s['properties']['recommendations']['items'];item['properties']['fundamental_feedback']=deepcopy(FEEDBACK_SCHEMA);item['required'].append('fundamental_feedback');return s
def compact(e):return {k:e.get(k) for k in ('symbol','company_name','status','period_end','filing_at','as_of','scope','metrics','missing','reason','sources')}
def report(e,feedback=None):
 if e.get('status') not in ('PARTIAL','AVAILABLE') or not any(v is not None for v in (e.get('metrics') or {}).values()):
  feedback=dict(relationship='INSUFFICIENT_EVIDENCE',summary=e.get('reason') or 'Verified company financial evidence unavailable.',financial_health='Unavailable',growth='Unavailable',valuation='Unavailable',key_risks=['Financial feedback is unavailable; no fundamental conclusion inferred.'])
 elif not isinstance(feedback,dict):feedback=dict(relationship='INSUFFICIENT_EVIDENCE',summary='Filing evidence captured; selected AI commentary is unavailable.',financial_health='See reported profitability; solvency not established.',growth='Comparison unavailable',valuation='Unavailable',key_risks=e.get('missing',[]))
 return dict(evidence=e,feedback=feedback,report_only=True,horizon_note='Company fundamentals provide longer-term context; disagreement with a short-term trade does not automatically invalidate or change its execution policy.')

def holdings(result,payload,workspace):
 provider=payload.get('ai_provider') or 'RULES_ONLY'
 if provider not in ('RULES_ONLY','CODEX_CHATGPT'):raise ValueError('Choose Rule-based or Codex ChatGPT account analysis.')
 result['ai_provider']=provider
 if provider=='RULES_ONLY':return result
 from .company_fundamentals import Provider
 from .handoff_ai import HandoffAI
 from .persistent_jobs import checkpoint
 data=Provider(workspace);instruments=[];lookup={}
 for row in result.get('rows',[]):
  checkpoint('Reading public company filing evidence for AI holdings feedback.',result)
  symbol=row.get('symbol');e=data.evidence(symbol if row.get('kind')=='DELIVERY_EQUITY' else None);row['fundamentals']=report(e)
  if e.get('status')=='NOT_APPLICABLE' or row.get('kind')!='DELIVERY_EQUITY':continue
  # Explicit allowlist: never serialize quantities, cost basis, account id or P&L.
  public={k:v for k,v in (row.get('evidence') or {}).items() if k in ('close','ema20','ema50','atr14','rsi14','weekly_close','weekly_ema20','completed_session') and isinstance(v,(int,float,str))}
  item=dict(symbol=symbol,timeframes={'daily':public},holding_recommendation=row.get('action'),horizon='Completed Daily/Weekly holding review',fundamentals=compact(e))
  if symbol not in lookup:instruments.append(item);lookup[symbol]=[]
  lookup[symbol].append(row)
 result['ai_review']=dict(status='RUNNING',provider=provider,order_authority='NONE',recommendations=[])
 try:
  ai=HandoffAI.from_payload(workspace,payload)
  for offset in range(0,len(instruments),6):
   checkpoint('Reviewing public holdings evidence with the selected AI path.',result)
   value=ai.review({'instruments':instruments[offset:offset+6]})
   result['ai_review']['recommendations'].extend(value['recommendations'])
   for r in value['recommendations']:
    for row in lookup.get(r['symbol'],[]):
     row['ai_commentary']={k:r.get(k) for k in ('rationale','risks','confidence')};row['fundamentals']=report(row['fundamentals']['evidence'],r.get('fundamental_feedback'))
  result['ai_review']['status']='COMPLETED' if instruments else 'NO_COMPANY_EVIDENCE'
 except ValueError as error:result['ai_review'].update(status='UNAVAILABLE',message=str(error))
 return result
