import unittest
from sector_heatmap.notification_destinations import telegram_destination

class DestinationIsolationTest(unittest.TestCase):
    def setUp(self):
        self.config={"owner_username":"owner","telegram":{"chat_id":42,"token":"synthetic"},"telegram_destinations":{"enabled":True,"private_trades":{"enabled":True,"chat_id":-1001,"activated_at":100},"shared_market":{"enabled":True,"chat_id":-1002,"activated_at":100}}}
    def test_private_entries_and_exits_never_use_shared_channel(self):
        for action in ("ENTRY","EXIT"):
            result,error=telegram_destination(self.config,{"owner_username":"owner","action":action,"time":110},110)
            self.assertIsNone(error);self.assertEqual(result["telegram"]["chat_id"],-1001)
        self.assertEqual(self.config["telegram"]["chat_id"],42)
    def test_market_cards_use_shared_channel_only(self):
        for kind in ("SECTOR_CARD","HANDOFF_CARD"):
            result,error=telegram_destination(self.config,{"owner_username":"owner","kind":kind},110)
            self.assertIsNone(error);self.assertEqual(result["telegram"]["chat_id"],-1002)
    def test_other_users_and_missing_owner_never_reach_either_channel(self):
        for owner in (None,"other"):
            result,error=telegram_destination(self.config,{"owner_username":owner,"action":"ENTRY","time":110},110)
            self.assertIsNone(result);self.assertTrue(error)
    def test_no_old_trade_replay_and_no_shared_destination_collision(self):
        event={"owner_username":"owner","action":"ENTRY","time":99}
        self.assertTrue(telegram_destination(self.config,event,110)[1])
        self.config["telegram_destinations"]["shared_market"]["chat_id"]=-1001
        event["time"]=110
        self.assertTrue(telegram_destination(self.config,event,110)[1])
    def test_pending_shared_feed_keeps_market_cards_in_owner_private_chat(self):
        del self.config["telegram_destinations"]["shared_market"]
        result,error=telegram_destination(self.config,{"owner_username":"owner","kind":"SECTOR_CARD"},110)
        self.assertIsNone(error);self.assertEqual(result["telegram"]["chat_id"],42)
