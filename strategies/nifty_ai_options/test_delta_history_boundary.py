import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from strategies.nifty_ai_options.delta_live import history
class HistoryBoundary(unittest.TestCase):
 def test_fractional_clock_finishes_without_repeating_terminal_page(self):
  class Delta:
   def __init__(self):self.calls=[]
   def clock(self):return 1795629000.625
   def _get(self,path,params):
    self.calls.append(dict(params))
    if len(self.calls)>45:raise AssertionError('terminal page repeated')
    return dict(result=[])
  d=Delta()
  with tempfile.TemporaryDirectory() as folder:history(d,'ETHUSD',1,Path(folder))
  self.assertEqual(len(d.calls),41)
  self.assertEqual(d.calls[-1]['end'],1795629000)
  self.assertTrue(all(r['end']>r['start'] for r in d.calls))
if __name__=='__main__':unittest.main()
