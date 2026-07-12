"""
news_engine.py — fake market news generator (Member 1)
======================================================

Generates fake crypto "news" (e.g. "Exchange hacked!", "ETF approval rumor")
to demonstrate how emotional, panic-driven trading happens. Two important
design points, both locked with the team:

  1. News is NOT cosmetic. Each event actively nudges the boosted price via
     apply_news_impact(), which price_engine.get_boosted_price() calls.

  2. News is NOT triggered by the user or by trades. A background timer thread
     generates a new event on its own every 45-90 seconds. The thread starts
     automatically the first time this module is imported.

All signatures here are locked in INTERFACES.md.
"""

import random
import threading
import time
from datetime import datetime

# Single source of truth (shared with price_engine.py) so the two files can't
# drift out of sync. backend/constants.py imports nothing from backend/, so
# there's no circular-import risk here.
from backend.constants import SUPPORTED_COINS

# The pool of possible events. Each entry is:
#   (headline template with {coin} placeholder, min impact %, max impact %)
# Negative ranges are bad news (price drops), positive ranges are good news.
_EVENT_TEMPLATES = [
    ("Major exchange holding {coin} reserves hacked!", -30.0, -18.0),
    ("Whale dumps massive {coin} position on the open market", -20.0, -10.0),
    ("Government announces ban on {coin} exchanges", -28.0, -15.0),
    ("Regulators open investigation into {coin} trading platforms", -15.0, -6.0),
    ("Rumors of {coin} network outage spook traders", -12.0, -5.0),
    ("{coin} ETF approval rumor sends traders into a frenzy", 8.0, 20.0),
    ("Major payment company announces {coin} support", 10.0, 22.0),
    ("Celebrity billionaire tweets support for {coin}", 5.0, 15.0),
    ("Institutional fund discloses large {coin} purchase", 8.0, 18.0),
    ("Analysts predict {coin} rally after strong adoption numbers", 4.0, 12.0),
]

# The feed of generated events, newest first. get_news_feed() reads this.
_news_feed = []
_MAX_FEED_SIZE = 50                          # cap so it can't grow forever

# Currently-active price impacts, one per coin:
#   coin -> {"impact_pct": float, "remaining_calls": int}
# Decay rule (locked): an event applies at FULL strength for the next 3 calls
# to get_boosted_price() for that coin, then hard-drops to 0.0.
_active_impacts = {}


def generate_news_event():
    """
    Randomly build ONE fake event. Pure function — it just returns the event
    dict, it does NOT store it or activate its impact (that's _record_event).

    Return shape (locked):
        {"headline": str, "coin": str, "impact_pct": float, "timestamp": datetime}
    """
    headline_template, min_impact, max_impact = random.choice(_EVENT_TEMPLATES)
    coin = random.choice(SUPPORTED_COINS)
    return {
        "headline": headline_template.format(coin=coin),
        "coin": coin,
        # A random signed % somewhere in this event type's range.
        "impact_pct": round(random.uniform(min_impact, max_impact), 2),
        "timestamp": datetime.now(),
    }


def get_news_feed(limit=10):
    """The `limit` most recent events, newest first. [] if none yet."""
    # Copy each event so the frontend can't mutate our internal feed.
    return [dict(event) for event in _news_feed[:limit]]


def apply_news_impact(coin):
    """
    Return the price impact % currently active for a coin (0.0 if none).
    Called internally by get_boosted_price(). Every call USES UP one of the
    event's 3 allowed calls; after the third the impact expires.
    """
    if coin not in _active_impacts:
        return 0.0
    entry = _active_impacts[coin]
    impact = entry["impact_pct"]
    entry["remaining_calls"] -= 1
    # Hard cutoff once the 3 calls are used up.
    if entry["remaining_calls"] <= 0:
        del _active_impacts[coin]
    return impact


def _record_event(event):
    """
    Store a freshly generated event in the feed AND activate its price impact.
    A new event for a coin replaces any older active impact and resets the
    counter back to 3 calls.
    """
    _news_feed.insert(0, event)              # newest goes to the front
    if len(_news_feed) > _MAX_FEED_SIZE:
        _news_feed.pop()                     # drop the oldest
    _active_impacts[event["coin"]] = {
        "impact_pct": event["impact_pct"],
        "remaining_calls": 3,
    }


def _news_loop():
    """The background worker: wait a random 45-90 s, then fire one event. Forever."""
    while True:
        time.sleep(random.randint(45, 90))
        _record_event(generate_news_event())


# ---------------------------------------------------------------------------
# Start the background thread ONCE, at import time.
# The _thread_started flag guards against Streamlit's auto-reload re-importing
# this module and accidentally starting a second thread (which would produce
# duplicate news events).
# ---------------------------------------------------------------------------
_thread_started = False
_NEWS_THREAD_NAME = "cryptorisk-news-thread"


def _start_news_thread():
    global _thread_started
    if _thread_started:
        return
    # Extra guard: Streamlit's auto-reload can re-import this module into a fresh
    # namespace, which resets _thread_started back to False and would otherwise
    # start a SECOND timer (duplicate news events). So also check whether a news
    # thread is already alive (by name) before starting one.
    for t in threading.enumerate():
        if t.name == _NEWS_THREAD_NAME:
            _thread_started = True
            return
    _thread_started = True
    # daemon=True so the thread dies automatically when the app exits.
    thread = threading.Thread(target=_news_loop, name=_NEWS_THREAD_NAME, daemon=True)
    thread.start()


_start_news_thread()


# ---------------------------------------------------------------------------
# Standalone smoke test. Run with:  python -m backend.news_engine
# Shows sample events and proves the 3-call decay works. (The background
# thread's 45-90 s timer is too slow to watch here, so we call _record_event
# directly to demonstrate the decay.)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Generating 3 sample events:")
    for _ in range(3):
        event = generate_news_event()
        print(" ", event["headline"], "->", event["impact_pct"], "%")

    print("\nTesting 3-call decay:")
    test_event = generate_news_event()
    _record_event(test_event)
    coin = test_event["coin"]
    print(f"  Event: {test_event['headline']} ({test_event['impact_pct']}% on {coin})")
    for i in range(5):
        print(f"  call {i + 1}: apply_news_impact({coin}) = {apply_news_impact(coin)}")

    print("\nFeed (newest first):", [e["headline"] for e in get_news_feed()])
