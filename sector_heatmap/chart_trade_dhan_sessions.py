"""Contract-aware Dhan entry session gate; independent of chart history access.

Calendar sources: existing market_calendar.py (NSE CM 2026) and dhan_mcx.py
(MCX verified non-agricultural contracts). Unknown segments/years fail closed
until their distinct calendars and session rules have been verified.
"""
from datetime import datetime, date, time
import re
from .dhan_execution import IST
from .dhan_protection import number

# NSE/FAOP/71777 annual list and NSE/FAOP/72262 election supplement.
# Budget session: normal 09:15–15:30, 1 February 2026; currency excluded.
NSE_FNO_HOLIDAYS = {date.fromisoformat("2026-"+day) for day in (
    "01-15","01-26","03-03","03-26","03-31","04-03","04-14","05-01",
    "05-28","06-26","09-14","10-02","10-20","11-10","11-24","12-25")}
NSE_FNO_SPECIAL = {date(2026,2,1)}
# BSE notice 20251212-8 (exchange notice PDF mirrored by Steel City);
# 15 January election closure and 1 February Budget session are supplements.
BSE_EQUITY_HOLIDAYS = {date.fromisoformat("2026-"+day) for day in (
    "01-15","01-26","03-03","03-26","03-31","04-03","04-14","05-01",
    "05-28","06-26","09-14","10-02","10-20","11-10","11-24","12-25")}
BSE_SPECIAL = {date(2026,2,1)}
# NSE/CD/71962 plus 15 January election closure. No Budget-day currency session.
NSE_CURRENCY_HOLIDAYS = {date.fromisoformat("2026-"+day) for day in (
    "01-15","01-26","02-19","03-03","03-19","03-26","03-31","04-01","04-03",
    "04-14","05-01","05-28","06-26","08-26","09-14","10-02","10-20","11-10","11-24","12-25")}



def validate_session(contract, now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("A timezone-aware Dhan session time is required.")
    now = now.astimezone(IST)
    if now.year != 2026:
        raise ValueError("The Dhan chart execution calendar needs an update for this year.")
    segment = contract.get("exchange_segment")
    expiry = contract.get("expiry")
    if segment == "NSE_EQ":
        from .market_calendar import market_session
        if market_session(now)["status"] != "OPEN":
            raise ValueError("The selected Dhan equity contract is outside its verified NSE session.")
    elif segment == "BSE_EQ":
        day = now.date()
        trading_day = day in BSE_SPECIAL or (now.weekday()<5 and day not in BSE_EQUITY_HOLIDAYS)
        if not trading_day or not time(9,15)<=now.time().replace(tzinfo=None)<time(15,30):
            raise ValueError("The selected Dhan equity contract is outside its verified BSE session.")
    elif segment in {"NSE_FNO","BSE_FNO"}:
        family = contract.get("instrument_name")
        if family not in {"FUTIDX","OPTIDX","FUTSTK","OPTSTK"}:
            raise ValueError("Native Dhan derivative instrument classification is required.")
        day = now.date()
        holidays = NSE_FNO_HOLIDAYS if segment == "NSE_FNO" else BSE_EQUITY_HOLIDAYS
        specials = NSE_FNO_SPECIAL if segment == "NSE_FNO" else BSE_SPECIAL
        trading_day = day in specials or (now.weekday()<5 and day not in holidays)
        if not trading_day or not time(9,15)<=now.time().replace(tzinfo=None)<time(15,30):
            raise ValueError("The selected Dhan derivative is outside its verified exchange F&O session.")
        if family == "OPTSTK":
            from .stock_expiry_policy import require_options_allowed
            expiries = contract.get("stock_option_expiries")
            if not isinstance(expiries,list) or not expiry or str(expiry)[:10] not in expiries:
                raise ValueError("Current listed stock-option expiry evidence is required.")
            require_options_allowed(expiries,now)
    elif segment == "NSE_CURRENCY":
        if contract.get("instrument_name") not in {"FUTCUR","OPTCUR"}:
            raise ValueError("Native Dhan currency instrument classification is required.")
        if not re.match(r"^(USDINR|EURINR|GBPINR|JPYINR)(?:[- ]|[0-9])",str(contract.get("native_symbol") or "")):
            raise ValueError("This currency pair needs its verified contract-specific trading hours.")
        if now.weekday()>4 or now.date() in NSE_CURRENCY_HOLIDAYS or not time(9)<=now.time().replace(tzinfo=None)<time(17):
            raise ValueError("The selected Dhan currency contract is outside its verified NSE currency session.")
    elif segment == "MCX_COMM":
        from .dhan_mcx import session_open
        if contract.get("valuation_revision") != "DHAN_MCX_2026_10":
            raise ValueError("A verified Dhan MCX contract valuation and session family is required.")
        if not session_open(now.timestamp()):
            raise ValueError("The selected Dhan MCX contract is outside its verified session.")
        cutoff = number(contract.get("entry_cutoff"))
        expiry_epoch = number(contract.get("expiry_epoch"))
        if cutoff <= now.timestamp() or expiry_epoch <= now.timestamp():
            raise ValueError("Dhan MCX pre-expiry protection blocks a new chart entry.")
    else:
        raise ValueError("This Dhan contract needs its verified exchange/segment session calendar before chart execution.")
    if expiry:
        try:
            day = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("The Dhan contract expiry date is invalid.") from None
        if day < now.date():
            raise ValueError("The selected Dhan contract has expired.")
        if segment=="NSE_CURRENCY" and day==now.date():
            # Currency expiry-day trading can end before the regular session.
            # Do not infer a last-trade cutoff from its calendar date alone.
            cutoff=number(contract.get("currency_entry_cutoff"))
            if cutoff<=now.timestamp():
                raise ValueError("The native Dhan currency expiry cutoff blocks a new entry.")
    elif segment not in {"NSE_EQ","BSE_EQ"}:
        raise ValueError("The selected Dhan derivative has no verified expiry.")
    return True


def conditional_expiry(plan,preflight,now):
    """Server-selected current-session deadline, never a request-supplied date."""
    if plan.broker!="DHAN" or not isinstance(preflight,dict):
        raise ValueError("A current Dhan conditional preflight is required.")
    contract=preflight.get("contract")
    if not isinstance(contract,dict) or contract.get("symbol")!=plan.symbol:
        raise ValueError("Conditional expiry requires the exact reviewed Dhan contract.")
    moment=datetime.fromtimestamp(float(now),IST)
    validate_session(contract,moment)
    segment=contract["exchange_segment"]
    if segment in {"NSE_EQ","BSE_EQ","NSE_FNO","BSE_FNO"}:
        deadline=moment.replace(hour=15,minute=30,second=0,microsecond=0).timestamp()
    elif segment=="NSE_CURRENCY":
        deadline=moment.replace(hour=17,minute=0,second=0,microsecond=0).timestamp()
        if contract.get("currency_entry_cutoff") is not None:
            deadline=min(deadline,float(number(contract["currency_entry_cutoff"])))
    elif segment=="MCX_COMM":
        from .dhan_mcx import trading_bounds
        _,closing=trading_bounds(float(now))
        deadline=moment.replace(hour=closing//60,minute=closing%60,second=0,microsecond=0).timestamp()
        deadline=min(deadline,float(number(contract["entry_cutoff"])),float(number(contract["expiry_epoch"])))
    else:
        raise ValueError("A verified Dhan conditional session deadline is unavailable.")
    if deadline<=float(now):
        raise ValueError("The Dhan conditional entry window has ended.")
    return deadline
