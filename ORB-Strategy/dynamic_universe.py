from AlgorithmImports import *

# Expanded watchlist — 30 symbols to test (original 10 + 20 new)
SCAN_UNIVERSE = [
    # Original core
    "NVO","COHR","B","WDC","CRDO","IAG","UEC","LITE","AXTI","SGML",
    # New additions
    "TSLA","AMD","NVDA","BA","NCLH","RCL","PYPL","SQ","COIN","HOOD",
    "MRNA","RIVN","LCID","ENPH","FSLR","OXY","DVN","PLTR","RGTI","IONQ",
]

def get_scan_universe():
    """Return deduplicated list of tickers."""
    return list(dict.fromkeys(SCAN_UNIVERSE))
