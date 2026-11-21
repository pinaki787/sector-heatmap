"""Wait for a read-only report worker without abandoning it on elapsed time."""
import subprocess,time

def wait_for_report(process,progress,interval=15,notify_after=60,notify_every=300,clock=time.monotonic):
 started=clock();next_notice=notify_after
 while True:
  try:
   code=process.wait(timeout=interval)
   if code:raise RuntimeError("Read-only analysis worker exited unsuccessfully.")
   return code
  except subprocess.TimeoutExpired:
   elapsed=clock()-started
   if elapsed>=next_notice:
    progress(elapsed)
    next_notice=elapsed+notify_every
