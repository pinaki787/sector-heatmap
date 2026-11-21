"""Freeze the follow-up specification and assess the earlier archive year."""
from pathlib import Path
import followup as f
base=Path(__file__).parent
source=(base/'review.py').read_text()
for a,b in [('2025-09-01','2024-10-25'),('2025-10-25','2024-10-25'),('2026-10-23','2025-10-24'),('2026-04-25','2025-04-25'),('2026-07-25','2025-07-25')]:source=source.replace(a,b)
namespace=dict(__name__='prior_year_study',__file__=str(base/'review.py'))
exec(compile(source,str(base/'review.py'),'exec'),namespace)
out=base/'atr_rsi_prior_year';out.mkdir(exist_ok=True)
namespace.update(OUT=out,RULES=f.RULES,assess=f.assess)
namespace['main']()
