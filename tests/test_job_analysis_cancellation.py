import tempfile,time,unittest
from pathlib import Path
from sector_heatmap.persistent_jobs import JobStore,CURRENT_JOB
from sector_heatmap.sector_service import SectorAnalysisService


class AnalysisCancellationTests(unittest.TestCase):
    def test_stop_after_first_history_response_prevents_remaining_timeframes(self):
        with tempfile.TemporaryDirectory() as folder:
            store=JobStore(Path(folder)/'jobs.sqlite3');self.addCleanup(store.close)
            calls=[]
            class Provider:
                def get(self,symbol,timeframe):
                    calls.append((symbol,timeframe))
                    context=CURRENT_JOB.get()
                    store.cancel(context.owner,context.job_id)
                    return []
            service=object.__new__(SectorAnalysisService);service.provider=Provider()
            job=store.submit('owner:account','ANALYSIS','handoff','History',{},lambda context:service._timeframe_candles('NSE:TEST-EQ'),'cancel-history')
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                value=store.get('owner:account',job['job_id'])
                if value['terminal']:break
                time.sleep(.01)
            self.assertEqual(value['status'],'CANCELLED')
            self.assertEqual(calls,[('NSE:TEST-EQ','15m')])
