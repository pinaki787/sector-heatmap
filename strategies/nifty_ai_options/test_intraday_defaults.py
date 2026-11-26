import unittest
from unittest.mock import patch
import ui_bridge as ui
from test_ui_bridge import PAYLOAD
class IntradayDefaults(unittest.TestCase):
 def test_direct_defaults_intraday_and_preserves_explicit_product(self):
  for product,expected in [(None,'INTRADAY'),('','INTRADAY'),('MARGIN','MARGIN'),('CNC','CNC')]:
   with patch.object(ui,'owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',return_value=None):
    c=ui.configuration(dict(PAYLOAD,ai_execution_route='DIRECT',ai_product=product),'owner')
    self.assertEqual(c['product'],expected)
if __name__=='__main__':unittest.main()
