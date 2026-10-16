import unittest
from sector_heatmap.section_permissions import FEATURES,allowed
class FeatureRegistryTests(unittest.TestCase):
 def test_new_cards_assignable(self):
  self.assertIn("renko-engine",FEATURES)
  self.assertIn("broker-connection",FEATURES)
 def test_engine_independent(self):
  self.assertFalse(allowed({"features":["renko-supertrend"]},"/api/renko-engine/status"))
  self.assertTrue(allowed({"features":["renko-engine"]},"/api/renko-engine/status"))
 def test_engine_does_not_grant_supertrend(self):
  self.assertFalse(allowed({"features":["renko-engine"]},"/api/renko-supertrend/runner"))
