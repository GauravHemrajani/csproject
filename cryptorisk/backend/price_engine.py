"""
price_engine.py — live prices + volatility engine (Member 1)
============================================================

This file does two jobs:

  1. Fetch REAL cryptocurrency prices from the CoinGecko API
     (throttled so we never spam the API — one fetch per coin per 30 s).

  2. Run the VOLATILITY ENGINE — the signature feature of the project.
     It amplifies real price changes so users experience big, fast swings
     (and therefore emotional trading mistakes) far quicker than in the
     real market:

         boosted_change_pct = (real_change_pct * 5)      # amplify reality 5x
                              + np.random.normal(0, 3)    # add random noise
                              + apply_news_impact(coin)   # fake news nudges it
         boosted_price      = real_price * (1 + boosted_change_pct / 100)

All function signatures here are LOCKED in INTERFACES.md — the frontend
(Member 3) calls them directly, so their names/parameters/return shapes
must not change without telling the whole team.
"""

from datetime import datetime

import numpy as np
import requests

# config.py reads these from the local .env file (with sensible defaults),
# so no secrets are hard-coded here.
from config import API_BASE_URL, API_KEY
# The volatility formula pulls in the current news impact for a coin. During
# early development apply_news_impact() can be stubbed to return 0.0; here we
# use the real one from news_engine.py.
from backend.news_engine import apply_news_impact
# COIN_ID_MAP / SUPPORTED_COINS live in backend/constants.py now (single source
# of truth) so price_engine.py and news_engine.py can't drift out of sync.
# Re-imported into this namespace so existing callers that do
# `from backend.price_engine import SUPPORTED_COINS` (e.g. trade_engine.py) keep
# working unchanged.
from backend.constants import COIN_ID_MAP, SUPPORTED_COINS

# Locked throttle: we only ask CoinGecko for a fresh price once every 30 s per
# coin. This keeps us well under the free tier's rate limit no matter how many
# users or Streamlit page-refreshes are hitting the app at once.
CACHE_SECONDS = 30

# The boosted price is recomputed at most once per BOOSTED_TICK_SECONDS per coin
# (see _boosted_cache below). Within a tick every caller — the dashboard AND
# execute_trade — gets the SAME boosted snapshot, so a user always trades at the
# price they were shown.
BOOSTED_TICK_SECONDS = 3

# Floor on the amplified % change so the boosted price can crash hard but never
# to zero or negative. A -95% swing is already brutal; this just stops the 5x
# amplification (plus bad news) from driving boosted_price <= 0, which would let
# a BUY pass the balance check and ADD cash.
BOOSTED_CHANGE_FLOOR = -95.0

# ---------------------------------------------------------------------------
# Shared module-level state.
# These are plain module variables (NOT st.session_state) because the whole
# app simulates ONE common market shared by every user — backend/ never
# imports streamlit. This state resets every time the app restarts, which is
# expected and fine.
# ---------------------------------------------------------------------------
_price_cache = {}       # coin -> {"price": float, "timestamp": datetime}  (30s cache)
# Baseline for the real % change: the real price the current change is measured
# FROM. It only advances when the real price ACTUALLY moves (a fresh fetch
# returns a new value) — not on every call. Cached reads within a 30s window all
# see the same real price, so without this the change would spuriously read 0.0
# on every frame except the single one right after a fetch.
_baseline_real_price = {}  # coin -> real price the current change is measured from
_last_real_change = {}     # coin -> last computed real_change_pct (persists across a window)
_price_history = {}     # coin -> list of {"real_price", "boosted_price", "timestamp"}
_MAX_HISTORY = 200      # cap history per coin so memory can't grow forever
_boosted_cache = {}     # coin -> last boosted snapshot (one shared tick per coin)


def _is_cache_fresh(coin):
    """True if we fetched this coin's price less than CACHE_SECONDS ago."""
    if coin not in _price_cache:
        return False
    age = (datetime.now() - _price_cache[coin]["timestamp"]).total_seconds()
    return age < CACHE_SECONDS


def _fetch_from_coingecko(coins):
    """
    Make ONE HTTP request to CoinGecko for the given list of coins.
    Returns {coin: price} for whatever came back, or {} if the call failed.
    This is the only function in the whole project that talks to the internet.
    """
    # Build a comma-separated list of CoinGecko ids, e.g. "bitcoin,ethereum".
    ids = ",".join(COIN_ID_MAP[c] for c in coins)
    params = {"ids": ids, "vs_currencies": "usd"}
    # The free public endpoint needs no key. If a demo key is set in .env we
    # attach it, but it's optional.
    if API_KEY:
        params["x_cg_demo_api_key"] = API_KEY

    try:
        # timeout=5 so a slow API can't freeze the whole app.
        response = requests.get(f"{API_BASE_URL}/simple/price", params=params, timeout=5)
        response.raise_for_status()          # raise if status is 4xx/5xx
        data = response.json()               # parse the JSON body
    except (requests.exceptions.RequestException, ValueError) as e:
        # Network error, timeout, bad status, or unparseable JSON all land
        # here. We print the real cause (helps debugging) and return {} so
        # callers can fall back gracefully instead of crashing.
        print("CoinGecko fetch failed:", e)
        return {}

    # CoinGecko replies like {"bitcoin": {"usd": 64000}, ...}. Pull out the
    # usd price for each coin we asked about.
    prices = {}
    for coin in coins:
        coin_id = COIN_ID_MAP[coin]
        if coin_id in data and "usd" in data[coin_id]:
            prices[coin] = float(data[coin_id]["usd"])
    return prices


def get_live_price(coin):
    """
    Current REAL USD price for a single coin.
    Returns None if the coin is invalid or the API call fails.
    Uses the 30-second cache so repeated calls don't re-hit the API.
    """
    if coin not in COIN_ID_MAP:
        return None
    # Serve from cache if it's still fresh.
    if _is_cache_fresh(coin):
        return _price_cache[coin]["price"]

    # Otherwise fetch a fresh price and cache it.
    fetched = _fetch_from_coingecko([coin])
    if coin not in fetched:
        return None                          # API failed for this coin
    _price_cache[coin] = {"price": fetched[coin], "timestamp": datetime.now()}
    return fetched[coin]


def get_live_prices(coins=None):
    """
    Batch version of get_live_price() — fetches every stale coin in ONE
    request instead of one request per coin. This is what the dashboard uses
    so a page refresh costs at most a single API call, not four.
    Returns {coin: price or None}. Same 30-second-per-coin throttle applies.
    """
    if coins is None:
        coins = SUPPORTED_COINS

    result = {}
    stale = []          # coins whose cache has expired and need a fresh fetch
    for coin in coins:
        if coin not in COIN_ID_MAP:
            result[coin] = None              # invalid coin
        elif _is_cache_fresh(coin):
            result[coin] = _price_cache[coin]["price"]   # serve from cache
        else:
            stale.append(coin)

    # One combined request for all the stale coins.
    if stale:
        fetched = _fetch_from_coingecko(stale)
        now = datetime.now()
        for coin in stale:
            if coin in fetched:
                _price_cache[coin] = {"price": fetched[coin], "timestamp": now}
                result[coin] = fetched[coin]
            else:
                result[coin] = None          # this coin failed to fetch
    return result


def get_boosted_price(coin):
    """
    THE VOLATILITY ENGINE. Returns one snapshot of the simulated market for a
    coin: the real price, the boosted (amplified) price, and both % changes.

    Returns None if the coin is invalid OR the real price is unavailable — we
    never invent a boosted value from a missing real price, and nothing is
    added to the history buffer in that case.

    Return shape (locked):
        {"coin", "real_price", "real_change_pct",
         "boosted_price", "boosted_change_pct", "timestamp"}
    """
    if coin not in COIN_ID_MAP:
        return None

    # Serve the current tick if it's still fresh: within BOOSTED_TICK_SECONDS every
    # caller sees the SAME boosted price. This is why the dashboard and a trade fired
    # moments later agree — get_boosted_price no longer re-rolls the random noise (or
    # re-consumes the news impact) on every single call.
    cached = _boosted_cache.get(coin)
    if cached is not None and (datetime.now() - cached["timestamp"]).total_seconds() < BOOSTED_TICK_SECONDS:
        return dict(cached)                  # copy so callers can't mutate the cache

    real_price = get_live_price(coin)
    if real_price is None:
        return None                          # CoinGecko down — bail out cleanly

    # How much did the REAL price move since it last actually changed?
    # The real price only refreshes every 30s (the CoinGecko cache), so within a
    # window every call sees the SAME real price. We therefore advance the
    # baseline only when the price genuinely moves, and reuse the last computed
    # change on the cached frames in between. That keeps the 5x amplification
    # term active across the whole window instead of firing for a single frame
    # and then reading 0.0 on every frame until the next fetch.
    baseline = _baseline_real_price.get(coin)
    if baseline is None:
        real_change_pct = 0.0                     # very first call for this coin
        _baseline_real_price[coin] = real_price
    elif real_price != baseline and baseline != 0:
        real_change_pct = ((real_price - baseline) / baseline) * 100
        _baseline_real_price[coin] = real_price   # advance baseline to the new price
    else:
        real_change_pct = _last_real_change.get(coin, 0.0)   # cached frame — reuse
    _last_real_change[coin] = real_change_pct

    # The locked formula: amplify the real change 5x, add random noise, and
    # let any active fake-news event nudge it up or down.
    boosted_change_pct = (
        (real_change_pct * 5)
        + np.random.normal(0, 3)             # NumPy: random number, mean 0, sd 3
        + apply_news_impact(coin)            # 0.0 if no active news
    )
    # Floor the amplified move so the price stays strictly positive. Without this,
    # a big real crash (x5) plus bad news can push boosted_change_pct below -100%,
    # making boosted_price negative — which lets a BUY slip past the balance check
    # and hand the user free cash.
    boosted_change_pct = max(boosted_change_pct, BOOSTED_CHANGE_FLOOR)
    # Boosted price is ALWAYS computed off the CURRENT real price, never off
    # the previous boosted price. That keeps the simulation anchored to
    # reality — one wild tick can't permanently drag the series away.
    boosted_price = real_price * (1 + boosted_change_pct / 100)

    timestamp = datetime.now()

    # Append this tick to the coin's history buffer (this is the ONLY source
    # of chart data for Member 3). Trim the oldest point if we're over the cap.
    history = _price_history.setdefault(coin, [])
    history.append({
        "real_price": real_price,
        "boosted_price": boosted_price,
        "timestamp": timestamp,
    })
    if len(history) > _MAX_HISTORY:
        history.pop(0)

    snapshot = {
        "coin": coin,
        "real_price": real_price,
        "real_change_pct": real_change_pct,
        "boosted_price": boosted_price,
        "boosted_change_pct": boosted_change_pct,
        "timestamp": timestamp,
    }
    # Remember this tick so callers within BOOSTED_TICK_SECONDS reuse it. Note we
    # only reach here (and only append to history) when computing a FRESH tick, so
    # the chart never fills with duplicated cached points.
    _boosted_cache[coin] = snapshot
    return dict(snapshot)                     # copy so callers can't mutate the cache


def get_price_history(coin, limit=50):
    """
    The last `limit` price snapshots for a coin, ordered oldest -> newest
    (the natural order for a line chart). Returns [] if no history yet.
    Member 3 calls this to draw the real-vs-boosted and volatility charts.
    """
    history = _price_history.get(coin, [])
    # Return copies of each point so the frontend can't mutate our buffer.
    return [dict(point) for point in history[-limit:]]   # last `limit`, in order


# ---------------------------------------------------------------------------
# Standalone smoke test. Run with:  python -m backend.price_engine
# Prints live prices and boosted snapshots to the console — no Streamlit,
# no database needed.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Live prices (batch):", get_live_prices())
    print("Live BTC (should hit 30s cache):", get_live_price("BTC"))
    print("Invalid coin:", get_live_price("XRP"))

    print("\nBoosted snapshots:")
    for c in SUPPORTED_COINS:
        snap = get_boosted_price(c)
        if snap is None:
            print(f"  {c}: price unavailable")
        else:
            print(
                f"  {c}: real ${snap['real_price']:,.4f} "
                f"({snap['real_change_pct']:+.2f}%) -> "
                f"boosted ${snap['boosted_price']:,.4f} "
                f"({snap['boosted_change_pct']:+.2f}%)"
            )

    print("\nBTC history so far:", get_price_history("BTC"))
