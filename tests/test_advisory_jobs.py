import threading
import unittest
from sector_heatmap.advisory_jobs import AdvisoryJobs

class AdvisoryJobTests(unittest.TestCase):
    def test_slow_analysis_returns_handle_and_poll_does_not_repeat_work(self):
        jobs=AdvisoryJobs()
        release=threading.Event()
        calls=[]
        def calculate(payload):
            calls.append(payload)
            release.wait(2)
            return {"status":"READY","analyzed":12}
        try:
            first=jobs.request({"symbols":["ABC"]},calculate)
            self.assertEqual(first["status"],"ANALYZING")
            second=jobs.request({"analysis_job":first["analysis_job"]},calculate)
            self.assertEqual(second["analysis_job"],first["analysis_job"])
            release.set()
            jobs.pool.shutdown(wait=True)
            result=jobs.request({"analysis_job":first["analysis_job"]},calculate)
            self.assertEqual(result["analyzed"],12)
            self.assertEqual(len(calls),1)
        finally:
            release.set()
            jobs.pool.shutdown(wait=True)

    def test_other_workspace_cannot_read_job(self):
        a,b=AdvisoryJobs(),AdvisoryJobs()
        release=threading.Event()
        try:
            result=a.request({},lambda p:release.wait(2))
            with self.assertRaisesRegex(ValueError,"another workspace"):
                b.request({"analysis_job":result["analysis_job"]},lambda p:None)
        finally:
            release.set();a.pool.shutdown();b.pool.shutdown()

    def test_queue_is_bounded(self):
        jobs=AdvisoryJobs(capacity=1)
        release=threading.Event()
        try:
            jobs.request({},lambda p:release.wait(2))
            with self.assertRaisesRegex(ValueError,"already has analysis"):
                jobs.request({},lambda p:None)
        finally:
            release.set();jobs.pool.shutdown()
