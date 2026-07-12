"""
constants.py — shared backend constants (Member 1)
==================================================

Single source of truth for the supported coin list and the CoinGecko id map.
Both price_engine.py and news_engine.py import from here so the two files can
never drift out of sync (e.g. someone adding a coin to one list but not the
other).

This module imports NOTHING from the rest of backend/, so it can be safely
imported by any backend file without causing a circular import.
"""

# CoinGecko identifies coins by full id ("bitcoin"), NOT ticker ("BTC").
# This map translates the tickers the rest of the app uses into CoinGecko ids.
COIN_ID_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
}

# The tickers the rest of the app uses, derived from the map above so the two
# can't disagree. -> ["BTC", "ETH", "SOL", "DOGE"]
SUPPORTED_COINS = list(COIN_ID_MAP)
