"""Configurable FYERS symbols and constituent baskets for sector analysis."""
from dataclasses import dataclass


BENCHMARK_SYMBOL = "NSE:NIFTY50-INDEX"


@dataclass(frozen=True)
class SectorDefinition:
    sector_id: str
    name: str
    symbol: str
    constituents: tuple[tuple[str, float], ...] = ()


SECTOR_DEFINITIONS = (
    SectorDefinition("bank", "Bank", "NSE:NIFTYBANK-INDEX", (("HDFCBANK", 24), ("ICICIBANK", 22), ("SBIN", 17), ("KOTAKBANK", 13), ("AXISBANK", 13), ("INDUSINDBK", 11))),
    SectorDefinition("financial-services", "Financial Services", "NSE:FINNIFTY-INDEX", (("HDFCBANK", 24), ("ICICIBANK", 22), ("SBIN", 14), ("KOTAKBANK", 11), ("AXISBANK", 10), ("BAJFINANCE", 10), ("BAJAJFINSV", 9))),
    SectorDefinition("it", "IT", "NSE:NIFTYIT-INDEX", (("TCS", 30), ("INFY", 24), ("HCLTECH", 16), ("WIPRO", 11), ("TECHM", 10), ("MPHASIS", 9))),
    SectorDefinition("auto", "Auto", "NSE:NIFTYAUTO-INDEX", (("MARUTI", 24), ("M&M", 23), ("TVSMOTOR", 21), ("BAJAJ-AUTO", 14), ("EICHERMOT", 10), ("HEROMOTOCO", 8))),
    SectorDefinition("pharma", "Pharma", "NSE:NIFTYPHARMA-INDEX", (("SUNPHARMA", 28), ("CIPLA", 18), ("DRREDDY", 17), ("DIVISLAB", 14), ("LUPIN", 13), ("AUROPHARMA", 10))),
    SectorDefinition("healthcare", "Healthcare", "NSE:NIFTYHEALTHCARE-INDEX", (("SUNPHARMA", 24), ("APOLLOHOSP", 20), ("MAXHEALTH", 17), ("CIPLA", 15), ("DRREDDY", 14), ("LUPIN", 10))),
    SectorDefinition("fmcg", "FMCG", "NSE:NIFTYFMCG-INDEX", (("HINDUNILVR", 27), ("ITC", 24), ("NESTLEIND", 16), ("BRITANNIA", 13), ("TATACONSUM", 11), ("DABUR", 9))),
    SectorDefinition("metal", "Metal", "NSE:NIFTYMETAL-INDEX", (("TATASTEEL", 26), ("HINDALCO", 23), ("JSWSTEEL", 22), ("COALINDIA", 18), ("VEDL", 11))),
    SectorDefinition("realty", "Realty", "NSE:NIFTYREALTY-INDEX", (("DLF", 33), ("GODREJPROP", 23), ("OBEROIRLTY", 18), ("PRESTIGE", 15), ("PHOENIXLTD", 11))),
    SectorDefinition("energy", "Energy", "NSE:NIFTYENERGY-INDEX", (("RELIANCE", 45), ("ONGC", 15), ("POWERGRID", 13), ("NTPC", 12), ("COALINDIA", 8), ("BPCL", 7))),
    SectorDefinition("oil-gas", "Oil & Gas", "NSE:NIFTYOILANDGAS-INDEX", (("RELIANCE", 45), ("ONGC", 17), ("BPCL", 11), ("IOC", 10), ("GAIL", 9), ("OIL", 8))),
    SectorDefinition("psu-bank", "PSU Bank", "NSE:NIFTYPSUBANK-INDEX", (("SBIN", 34), ("BANKBARODA", 22), ("PNB", 18), ("CANBK", 15), ("UNIONBANK", 11))),
    SectorDefinition("consumer-durables", "Consumer Durables", "NSE:NIFTYCONSRDURBL-INDEX", (("TITAN", 28), ("ASIANPAINT", 20), ("HAVELLS", 17), ("DIXON", 14), ("VOLTAS", 11), ("CROMPTON", 10))),
    # Existing coverage retained alongside the requested minimum sector set.
    SectorDefinition("media", "Media", "NSE:NIFTYMEDIA-INDEX", (("SUNTV", 31), ("ZEEL", 25), ("PVRINOX", 20), ("NAZARA", 14), ("NETWORK18", 10))),
)

SECTOR_BY_ID = {sector.sector_id: sector for sector in SECTOR_DEFINITIONS}

# Backward-compatible views used by the live WebSocket snapshot.
SECTORS = [(sector.name, sector.symbol, 1.0) for sector in SECTOR_DEFINITIONS]
SECTOR_STOCKS = {sector.name: list(sector.constituents) for sector in SECTOR_DEFINITIONS}


def equity_symbol(ticker):
    return f"NSE:{ticker}-EQ"
