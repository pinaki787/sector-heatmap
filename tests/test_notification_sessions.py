from datetime import datetime
from sector_heatmap.market_calendar import IST
from sector_heatmap.notification_sessions import gate
def stamp(day,hour,minute=0):
    return datetime(2026,10,day,hour,minute,tzinfo=IST).timestamp()
def test_equity_closed_and_open():
    e={'symbol':'NSE:PASHUPATI-EQ'}
    assert gate(e,stamp(26,10),stamp(26,10))==(None,None)
    assert gate(e,stamp(26,10),stamp(26,18))[0]=='SKIPPED'
def test_bse_weekend():
    assert gate({'symbol':'BSE:ABC'},stamp(25,10),stamp(25,10))[0]=='SKIPPED'
def test_mcx_evening_and_midnight():
    e={'symbol':'MCX:NATURALGAS26NOV235PE'}
    assert gate(e,stamp(26,20),stamp(26,20))==(None,None)
    assert gate(e,stamp(26,20),stamp(27,0))[0]=='SKIPPED'
def test_crypto_continues():
    assert gate({'broker':'DELTA','symbol':'BTCUSD'},stamp(25,0),stamp(27,0))==(None,None)
def test_closed_creation_not_replayed():
    assert gate({'symbol':'NSE:ABC'},stamp(26,20),stamp(27,10))[0]=='SKIPPED'
def test_old_session_not_replayed():
    assert gate({'symbol':'NSE:ABC'},stamp(26,10),stamp(27,10))[0]=='SKIPPED'
def test_unknown_fail_closed():
    assert gate({'symbol':'UNKNOWN'},stamp(26,10),stamp(26,10))[0]=='SKIPPED'
def test_mixed_closed_summary_suppressed():
    e={'kind':'POSITION_SUMMARY','broker':'FYERS','positions':[{'symbol':'NSE:ABC'},{'symbol':'MCX:GOLD26NOVFUT'}]}
    assert gate(e,stamp(26,20),stamp(26,20))[0]=='SKIPPED'
def test_combined_is_equity_session():
    assert gate({'kind':'COMBINED_CARD'},stamp(26,10),stamp(26,20))[0]=='SKIPPED'

import unittest
class NotificationSessionsTest(unittest.TestCase):
    pass
for _name,_fn in list(globals().items()):
    if _name.startswith("test_"):
        setattr(NotificationSessionsTest,_name,lambda self,fn=_fn:fn())
