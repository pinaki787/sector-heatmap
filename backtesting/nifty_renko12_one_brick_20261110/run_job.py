import os,runpy,traceback
from pathlib import Path
import job_runtime as job
try:
 runpy.run_path(str(Path(__file__).with_name('backtest.py')),run_name='__main__')
 job.progress('replay_complete',status='REPLAY_COMPLETE')
except BaseException as exc:
 job.progress('failed',status='FAILED',error_type=type(exc).__name__,error=str(exc))
 traceback.print_exc()
 raise
finally:
 job.stop.set();job.write()
