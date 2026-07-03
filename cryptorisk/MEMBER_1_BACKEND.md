# Member 1 — Core Simulation + Trading Engine

**Owns:** `backend/` folder (see `FILE_STRUCTURE.md`)
**Files:** `backend/price_engine.py`, `backend/trade_engine.py`, `backend/news_engine.py`

## Goal

Build the "market" that everything else reacts to — real prices in, boosted volatile prices out, and a trade engine that safely executes buys/sells against the DB.

> **Function signatures for everything below are locked in `INTERFACES.md`. Read it before writing code — it also covers failure/edge-case behavior (what to return when a coin is invalid, balance is insufficient, etc.), which this doc doesn't repeat.**

## Core Tasks

- [ ] **Price fetcher** — pull live BTC/ETH/SOL/DOGE prices from the CoinGecko API (`price_engine.py`)
  - Handle API failures/rate limits gracefully (don't crash the app if CoinGecko is slow)
  - **Throttle: 30 seconds per coin (locked).** Cache each coin's real price in a module-level variable; a call within 30 seconds of the last fetch for that coin reuses the cached value instead of calling CoinGecko again. This is a shared cache (same for every user hitting the app), not per-session — keeps you well under CoinGecko's free-tier rate limits even with multiple users open at once.
  - Implement both `get_live_price(coin)` (single) and `get_live_prices(coins)` (batch) per `INTERFACES.md` — the batch version is what keeps the dashboard from hitting CoinGecko 4x per rerun
- [ ] **Volatility amplification engine** — implement the boosted-price formula using NumPy
  - `boosted_change = (real_change * 5) + np.random.normal(0, 3) + apply_news_impact(coin)`
  - Note the news term: news events actively nudge the boosted price (confirmed with the team) — this isn't just flavor text on the news page. `get_boosted_price()` must call `apply_news_impact()` internally.
  - Keep it isolated in its own function so Member 3 can plot "real vs boosted" side by side
- [ ] **Price history buffer** — `get_boosted_price()` must also append each result to an in-memory history buffer per coin (cap it, e.g. last 200 points, so memory doesn't grow unbounded). Expose it via `get_price_history(coin, limit=50)` per `INTERFACES.md`. This is the only source of chart data for Member 3 — without it, none of the Plotly charts on the dashboard/news pages can render.
- [ ] **API-failure handling in `get_boosted_price()` (locked, see `INTERFACES.md`).** If `get_live_price(coin)` returns `None` (CoinGecko fetch failed), `get_boosted_price()` must also return `None` — don't compute a boosted value off a missing real price, and don't append that tick to the coin's history buffer. `execute_trade()` must check for this `None` **first**, before any balance/quantity validation, and fail cleanly with a "price temporarily unavailable" message.
- [ ] **News timer thread** — `news_engine.py` starts a background thread (using `threading`, allowed per the PRD) at import time that calls `generate_news_event()` automatically on a randomized interval (e.g. every 45–90 seconds), independent of trades or page views. Store generated events in an internal list that `get_news_feed()` reads from.
  - **Guard against double-start.** Python normally only imports a file once per run, so "starts at import time" is usually safe — but Streamlit's dev-mode file-watcher/auto-reload can occasionally re-import a module, which would start a second thread and cause duplicate news events. Guard against this with a simple module-level flag:
    ```python
    _thread_started = False

    def _start_news_thread():
        global _thread_started
        if _thread_started:
            return
        _thread_started = True
        # start the actual threading.Thread here
    ```
- [ ] **News impact decay** — when `generate_news_event()` fires for a coin, its `impact_pct` must stay active for exactly the **next 3 calls** to `get_boosted_price()` for that coin (via `apply_news_impact()`), then drop to `0.0`. If a new event fires for the same coin before those 3 calls are used up, it replaces the old impact and resets the counter to 3. This is now locked (not left to your own judgment) — see `INTERFACES.md`.
- [ ] **Buy logic** — validate balance, calculate cost **at the boosted price** (confirmed: trades execute at boosted price, not real price), call DB insert/update functions
- [ ] **Sell logic** — validate quantity owned, calculate proceeds **at the boosted price**, call DB update functions
- [ ] **Weighted average buy price** — when a user buys more of a coin they already hold, recalculate the average `buy_price` correctly (this is what makes the composite key in `portfolio` work). Signature locked as `calculate_weighted_avg_buy_price()` in `INTERFACES.md`.
- [ ] **Portfolio holdings update logic** — the glue that takes a trade result and turns it into a DB write via Member 2's functions. Note: `upsert_holding()` handles deleting a fully-sold-out row itself — you don't need a separate delete call, just pass the new total quantity (0 if fully sold).

## Deliverables / Definition of Done

- Live prices refresh correctly and reliably
- Volatility amplification visibly produces bigger, faster swings than real prices
- Price history accumulates correctly so charts have real data to plot within the first few minutes of the app running
- News events appear on their own timer without any frontend action — verify this by leaving the news page untouched and confirming new events still show up
- Buy/sell transactions execute correctly and reject invalid trades (insufficient balance, selling more than owned)
- Weighted average buy price is mathematically correct after multiple buys
- All functions match the signatures locked in `INTERFACES.md` so Member 3 can call them without asking you first

## Dependencies

- **Blocked on Member 2** for: `get_user()`, `update_balance()`, `get_portfolio()`, `upsert_holding()`, `insert_transaction()` — exact signatures and return shapes in `INTERFACES.md`
- Until those exist, build against **stub/mock functions** that return fake data matching the signatures in `INTERFACES.md` — don't wait idle.
- **You unblock Member 3** — your `get_live_price()`, `get_live_prices()`, `get_boosted_price()`, `get_price_history()`, `execute_trade()`, and `get_news_feed()` are what the UI calls directly.
- `get_boosted_price()` calls `apply_news_impact()` internally, but **don't let this block early progress.** Stub `apply_news_impact()` to just `return 0.0` while you build and test steps 1–4 of the Suggested Order of Attack below — the volatility formula still works correctly with a constant `0.0` news term, it just means no event is nudging prices yet. Build the real `news_engine.py` last (step 5), per the suggested order — swap the stub for the real function then. This mirrors the same stub-first approach used for the Member 2 DB dependency above.

## Suggested Order of Attack

1. Write CoinGecko fetcher + test it standalone (print prices to console, no Streamlit needed)
2. Implement volatility formula, sanity-check outputs against known real-change values
3. Stub out DB calls, build `execute_trade()` end-to-end logic
4. Swap stubs for Member 2's real DB functions once available
5. Wire in `news_engine.py` — fake events that nudge prices, feeding Member 3's news feed page