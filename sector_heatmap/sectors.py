# Fyers symbols verified against the SDK's sector-index symbol map.
SECTORS = [
    ("Financials", "NSE:FINNIFTY-INDEX", 36.8), ("IT", "NSE:NIFTYIT-INDEX", 14.3),
    ("Energy", "NSE:NIFTYENERGY-INDEX", 12.1), ("FMCG", "NSE:NIFTYFMCG-INDEX", 9.0),
    ("Auto", "NSE:NIFTYAUTO-INDEX", 7.4), ("Metals", "NSE:NIFTYMETAL-INDEX", 5.2),
    ("Pharma", "NSE:NIFTYPHARMA-INDEX", 4.9), ("Realty", "NSE:NIFTYREALTY-INDEX", 3.1),
    ("Media", "NSE:NIFTYMEDIA-INDEX", 1.5), ("PSU Bank", "NSE:NIFTYPSUBANK-INDEX", 2.8),
]

# Large, liquid constituents used to explain each sector's intraday move.
# Weights are relative explanatory weights for the displayed basket.
SECTOR_STOCKS = {
    "Financials": [("HDFCBANK", 28), ("ICICIBANK", 25), ("SBIN", 16), ("KOTAKBANK", 12), ("AXISBANK", 11), ("BAJFINANCE", 8)],
    "IT": [("TCS", 30), ("INFY", 24), ("HCLTECH", 16), ("WIPRO", 11), ("TECHM", 10), ("MPHASIS", 9)],
    "Energy": [("RELIANCE", 52), ("ONGC", 16), ("POWERGRID", 13), ("NTPC", 11), ("BPCL", 8)],
    "FMCG": [("HINDUNILVR", 27), ("ITC", 24), ("NESTLEIND", 16), ("BRITANNIA", 13), ("TATACONSUM", 11), ("DABUR", 9)],
    "Auto": [("MARUTI", 24), ("M&M", 23), ("TVSMOTOR", 21), ("BAJAJ-AUTO", 14), ("EICHERMOT", 10), ("HEROMOTOCO", 8)],
    "Metals": [("TATASTEEL", 26), ("HINDALCO", 23), ("JSWSTEEL", 22), ("COALINDIA", 18), ("VEDL", 11)],
    "Pharma": [("SUNPHARMA", 28), ("CIPLA", 18), ("DRREDDY", 17), ("DIVISLAB", 14), ("APOLLOHOSP", 13), ("LUPIN", 10)],
    "Realty": [("DLF", 33), ("GODREJPROP", 23), ("OBEROIRLTY", 18), ("PRESTIGE", 15), ("PHOENIXLTD", 11)],
    "Media": [("SUNTV", 31), ("ZEEL", 25), ("PVRINOX", 20), ("NAZARA", 14), ("NETWORK18", 10)],
    "PSU Bank": [("SBIN", 34), ("BANKBARODA", 22), ("PNB", 18), ("CANBK", 15), ("UNIONBANK", 11)],
}

def equity_symbol(ticker):
    return f"NSE:{ticker}-EQ"
