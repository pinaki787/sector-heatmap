import unittest
from unittest.mock import patch
from .session_auto import apply_observation

class SessionGapTests(unittest.TestCase):
 def test_resized_session_keeps_absolute_brick_close_and_direction(self):
  state={'count':5,'session_auto':{'session_start':100},'brick_box':10,
         'brick_level':34,'brick_direction':1,
         'price_renko':{'level':35,'direction':-1,'run_id':'same'}}
  ref={'session_start':200,'box':7}
  with patch('strategies.renko_supertrend.session_auto.for_observation',return_value=ref):
   self.assertEqual(apply_observation(state,{},201,.05),ref)
  self.assertAlmostEqual(state['brick_level']*7,340)
  self.assertAlmostEqual(state['price_renko']['level']*7,350)
  self.assertEqual(state['brick_direction'],1)
  self.assertEqual(state['price_renko']['direction'],-1)
  self.assertEqual(state['price_renko']['run_id'],'same')
 def test_first_session_does_not_invent_a_previous_anchor(self):
  state={}
  with patch('strategies.renko_supertrend.session_auto.for_observation',return_value={'session_start':200,'box':7}):
   apply_observation(state,{},201,.05)
  self.assertNotIn('brick_level',state)
