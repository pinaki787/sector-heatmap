"""One ranking rule for analysis, option budget, allocation and entry order."""
from decimal import Decimal,InvalidOperation

def priority_key(row):
 card=row.get("report_card") or row
 candidate=card.get("candidate") or row.get("candidate") or {}
 analysis=card.get("analysis") or {}
 c=row.get("conviction") or analysis.get("conviction") or candidate.get("screening_conviction") or {}
 try:
  a,b=Decimal(str(c.get("score",0))),Decimal(str(c.get("maximum_score",1)))
  score=a/b if a.is_finite() and b.is_finite() and b>0 and 0<=a<=b else Decimal(0)
 except (InvalidOperation,ValueError,ZeroDivisionError):score=Decimal(0)
 rank=row.get("source_rank",candidate.get("source_rank"))
 rank=rank if type(rank) is int and rank>0 else 10**9
 kind=row.get("kind") or analysis.get("kind")
 return (-score,rank,str(row.get("underlying") or candidate.get("symbol") or ""),0 if kind=="LONG_OPTION" else 1,str(row.get("symbol") or ""))
