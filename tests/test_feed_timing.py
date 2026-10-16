import os
import unittest
from unittest.mock import patch

from sector_heatmap.market_data import FyersLiveFeed


class ImmediateThread:
    def __init__(self, target, **kwargs):
        self.target = target

    def start(self):
        self.target()


class FakeSocket:
    def __init__(self, **kwargs):
        self.callbacks = kwargs

    def connect(self):
        self.callbacks['on_connect']()
        self.callbacks['on_message']({'symbol': 'NSE:NIFTY50-INDEX', 'ltp': 100})

    def subscribe(self, *args, **kwargs):
        pass


class FeedTimingTests(unittest.TestCase):
    def test_callback_pipeline_and_no_credentials_in_trace(self):
        with patch.dict(os.environ, {'FYERS_FEED_TIMING': '1'}), \
             patch('sector_heatmap.market_data.data_ws.FyersDataSocket', FakeSocket), \
             patch('sector_heatmap.market_data.Thread', ImmediateThread), \
             patch('sector_heatmap.market_data.configure_websocket_ca_bundle'):
            feed = FyersLiveFeed('secret-test-token')
            feed.start()
            result = feed.snapshot()
            self.assertTrue(result['connected'])
            timing = feed.timing.snapshot()
            self.assertNotIn('feed_timing', result)
            stages = [e['stage'] for e in timing['events']]
            self.assertLess(stages.index('subscription_return'), stages.index('first_tick_stored'))
            self.assertIn('first_snapshot_complete', stages)
            self.assertNotIn('secret-test-token', str(timing))
            feed.snapshot()
            self.assertEqual(sum(e['stage'] == 'first_snapshot_complete' for e in feed.timing.snapshot()['events']), 1)

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {'FYERS_FEED_TIMING': '0'}):
            self.assertNotIn('feed_timing', FyersLiveFeed('unused').snapshot())


if __name__ == '__main__':
    unittest.main()
