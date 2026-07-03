# CryptoRisk — INTERFACES.md

**Status: LOCKED.** This is the single contract for every function that crosses a module boundary (one person calls it, another person implements it). Build against these signatures with stub/mock functions from day one — don't wait for the real implementation.

**Ground rule:** once locked, nobody changes a function's name, parameters, or return type without telling the whole group immediately. A silent change here is the #1 way this project breaks during integration in week 3–4.

Seven decisions were confirmed with the team lead and are baked into the signatures below:
1. **Login** — frontend calls `get_user(username)`, then compares the password itself in Python. There is no separate `login_user()` function.
2. **Trade execution price** — `execute_trade()` always executes at the **boosted** (simulated) price, never the real price.
3. **News coupling** — fake news events actively nudge the boosted price via `apply_news_impact()`, feeding into `get_boosted_price()`. News is not purely cosmetic.
4. **Chart history** — `get_boosted_price()` only returns one snapshot, which isn't enough to plot a line chart. The backend keeps its own in-memory history and exposes it via `get_price_history()`. Frontend never builds history itself — it just calls this function and plots what comes back.
5. **News timing** — news events are **not** triggered by the frontend or by trades. The backend auto-generates a new event on its own timer (a background thread, independent of user actions). `get_news_feed()` just reads whatever has accumulated so far.
6. **ID generation is manual — no `AUTO_INCREMENT`.** `userid` and `transid` are declared plain `INT PRIMARY KEY` in `schema.sql`. `create_user()` and `insert_transaction()` each compute the next ID themselves with `SELECT COALESCE(MAX(...), 0) + 1` immediately before their `INSERT`, then insert explicitly with that value and return it. No other layer needs to think about ID generation — but Member 2 should keep the compute-then-insert as tight as possible within the function so nothing else can insert in between.
7. **Signup is a dedicated page.** `frontend/signup_page.py` calls `create_user()` directly. It's a separate flow from `login_page.py`, not a mode/toggle inside it.

---

## Database Layer (owned by Member 2)

### `get_connection() -> mysql.connector.connection.MySQLConnection | None`
Opens a connection to the local MySQL server using credentials from `config.py` (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`), i.e. `mysql.connector.connect(host=..., user=..., password=..., database="cryptorisk")`.
Returns `None` if the connection fails — every function below must handle that gracefully (catch, don't crash Streamlit).

**Error-logging convention (locked):** every function in `db/` returns the same `None`/`False`/`[]` whether the real cause is "not found" or "connection/query failed" — the return value itself doesn't distinguish them, and that's not changing. Instead, whenever a `try/except` catches a real connection or query error anywhere in `db/`, `print()` the actual exception before returning. This costs no extra code on Member 1's or Member 3's side and doesn't change any signature — it just means a genuine DB failure shows up in the terminal instead of silently looking identical to "username not found."

### `create_user(username: str, password: str) -> dict`
Called from `frontend/signup_page.py` (the dedicated signup page — not part of `login_page.py`).
Checks username uniqueness internally before inserting.
**ID generation is manual:** this function runs `SELECT COALESCE(MAX(userid), 0) + 1 FROM users` to compute the next `userid`, then inserts explicitly with that value and includes it in the return dict.
**Returns:**
```python
{"success": bool, "userid": int | None, "message": str}
```
- Duplicate username → `{"success": False, "userid": None, "message": "Username already exists"}`
- New user starts with `balance = 10000.0` (per PRD).

### `get_user(username: str) -> dict | None`
**Returns:**
```python
{"userid": int, "username": str, "password": str, "balance": float}
```
Returns `None` if username not found.
**This is also the login function.** Frontend calls this, then compares `result["password"] == entered_password` itself (plaintext, per PRD — no hashing).

### `update_balance(userid: int, new_balance: float) -> bool`
Sets balance to the given absolute value (not a delta — caller computes the new balance first).
Returns `True` on success, `False` if `userid` doesn't exist or the update fails.

### `get_portfolio(userid: int) -> list[dict]`
**Returns:**
```python
[{"coin": str, "quantity": float, "buy_price": float}, ...]
```
Returns `[]` if the user holds nothing. One row per coin (composite key `(userid, coin)`).

### `upsert_holding(userid: int, coin: str, quantity: float, buy_price: float) -> bool`
`quantity` is the **new total** quantity after the trade (not a delta). `buy_price` is the recalculated weighted average (for buys) or the unchanged existing average (for sells) — Member 1 computes this before calling.
**Built-in rule:** if `quantity <= 0` (full sell), this function **deletes** the row rather than leaving a zero-quantity row behind. Backend never needs a separate delete call.
Returns `True` on success, `False` on failure.

### `insert_transaction(userid: int, coin: str, action: str, quantity: float, price: float, trade_date: date) -> int | None`
`action` is `"BUY"` or `"SELL"`.
**ID generation is manual:** this function runs `SELECT COALESCE(MAX(transid), 0) + 1 FROM transactions` to compute the next `transid`, then inserts explicitly with that value and returns it.
**Date handling:** callers always pass a real `date` object. `schema.sql` declares `trade_date` as a native `DATE` column, so `mysql.connector` handles the conversion automatically — no manual string formatting needed on either side.
Returns the new `transid` on success, `None` on failure.

### `get_transaction_history(userid: int) -> list[dict]`
**Returns:**
```python
[{"transid": int, "coin": str, "action": str, "quantity": float, "price": float, "trade_date": date}, ...]
```
Ordered `ORDER BY trade_date DESC, transid DESC` (transid as tiebreaker, since `trade_date` is `DATE` not `DATETIME` — same-day trades would otherwise sort arbitrarily). Returns `[]` if none.
**Date handling:** `trade_date` is a native MySQL `DATE` column; `mysql.connector` returns it as a Python `date` object automatically when fetched — no manual conversion needed, the dict just uses the value as returned by the cursor.

---

## Backend Layer (owned by Member 1)

### `get_live_price(coin: str) -> float | None`
`coin` ∈ `{"BTC", "ETH", "SOL", "DOGE"}`. Returns the current real USD price from CoinGecko.
**Throttle: 30 seconds per coin.** Each coin's real price is cached internally (module-level variable in `price_engine.py`) for 30 seconds — any call within that window returns the cached value instead of hitting the CoinGecko API again. This applies regardless of how many users or Streamlit reruns are asking.
Returns `None` if the API call fails or `coin` is invalid — caller must handle this (e.g. show last-known price, not a crash).

### `get_live_prices(coins: list[str] = ["BTC", "ETH", "SOL", "DOGE"]) -> dict[str, float | None]`
Batch version — one throttled call instead of Member 3 calling `get_live_price()` four times per Streamlit rerun. Same 30-second-per-coin throttle as `get_live_price()` applies here.
**Returns:** `{"BTC": 43250.12, "ETH": 2400.5, ...}`. Any coin that failed to fetch maps to `None`.

### `get_boosted_price(coin: str) -> dict | None`
**Returns:**
```python
{
  "coin": str,
  "real_price": float,
  "real_change_pct": float,
  "boosted_price": float,
  "boosted_change_pct": float,
  "timestamp": datetime
}
```
`real_change_pct` is computed against the previous fetch (baseline cached internally in `price_engine.py` — a plain module-level variable, **not** `st.session_state`; `backend/` never imports `streamlit`. This baseline is shared across all users, since the whole app simulates one common market, not a separate market per user); on the very first call after the app starts it's `0.0`. **This cache does not persist across app restarts** — restarting the app resets `real_change_pct` to `0.0` on the next call and the price history buffer (see below) starts empty again; this is expected and requires no extra handling.
`boosted_change_pct = (real_change_pct * 5) + np.random.normal(0, 3) + apply_news_impact(coin)`.

**`boosted_price` formula (locked):**
```
boosted_price = real_price * (1 + boosted_change_pct / 100)
```
`boosted_price` is always computed fresh off the **current** `real_price` on every call — it is never compounded off the previous call's `boosted_price`. This keeps the boosted price anchored to reality: a single extreme swing (from a big news hit or a high `np.random.normal` draw) affects that one tick's displayed price but cannot permanently drag the series away from where real prices actually are.

**Returns `None` in two cases (locked):** (1) `coin` is invalid, or (2) the underlying `get_live_price(coin)` call itself returned `None` (CoinGecko fetch failed/timed out) — `get_boosted_price()` must not attempt to compute a boosted value off a missing real price. There is no way for a caller to tell these two cases apart from the return value alone (same "bare `None`, don't crash" convention used everywhere else in this doc) — Member 3 and `execute_trade()` both just need to treat any `None` here as "price unavailable right now, show/handle accordingly."
This is the function Member 3 uses to plot "real vs boosted" side by side.
**No batch version, and that's fine (confirmed):** unlike `get_live_price()`, this function doesn't call CoinGecko directly — it reads the already-throttled, already-cached real price from `get_live_price()` internally and does cheap in-memory math (the volatility formula + a news-impact lookup). So Member 3 calling `get_boosted_price()` once per coin (4x per Streamlit rerun) is 4 cheap function calls, not 4 API calls — the 30-second CoinGecko throttle is already handled one layer down. No batch equivalent is needed.
**Side effect:** every *successful* call appends `{"real_price", "boosted_price", "timestamp"}` for this coin to an internal history buffer (capped, e.g. last 200 points) — this is what powers `get_price_history()` below. Member 3 doesn't need to do anything to make this happen; it's automatic. **If the call returns `None` (see above), nothing is appended for that tick** — a gap in the buffer during a CoinGecko outage is expected and fine, not a bug.

### `get_price_history(coin: str, limit: int = 50) -> list[dict]`
**Returns:**
```python
[{"real_price": float, "boosted_price": float, "timestamp": datetime}, ...]
```
Ordered oldest → newest (natural order for a time-series line chart). Returns `[]` if no history has accumulated yet for that coin (e.g. app just started). This is the function Member 3 uses for all three chart types: real-vs-boosted price movement, and volatility-spike visualization. `limit` caps how many recent points come back — Member 3 can request more or fewer depending on how zoomed-in the chart should be.

### `execute_trade(userid: int, coin: str, action: str, quantity: float) -> dict`
`action` ∈ `{"BUY", "SELL"}`. **Always executes at the boosted price** (`get_boosted_price(coin)["boosted_price"]`) — not the real price.
**Returns:**
```python
{"success": bool, "message": str, "executed_price": float | None, "new_balance": float | None}
```
Failure cases (`success: False`, `executed_price`/`new_balance`: `None`): `get_boosted_price(coin)` returned `None` (price temporarily unavailable, e.g. CoinGecko fetch failed — **check this first**, before any balance/quantity math, since there's no price to validate a trade against), insufficient balance (BUY), insufficient quantity owned (SELL), invalid coin, `quantity <= 0`. `message` says which.
Internally: fetches boosted price → calls `db.get_user()` for current balance and `db.get_portfolio()` for current holdings/avg price → validates → computes weighted avg buy price (see below, for BUYs) → calls `db.update_balance()`, `db.upsert_holding()`, `db.insert_transaction()`.

### `calculate_weighted_avg_buy_price(existing_qty: float, existing_avg_price: float, new_qty: float, new_price: float) -> float`
Internal helper — not called across the module boundary, but documented since Member 3 may want to reproduce the math for P/L tooltips on the portfolio page.
```
= ((existing_qty * existing_avg_price) + (new_qty * new_price)) / (existing_qty + new_qty)
```

### `generate_news_event() -> dict`
Randomly generates one fake market event.
**Returns:**
```python
{"headline": str, "coin": str, "impact_pct": float, "timestamp": datetime}
```
`impact_pct` is signed (e.g. `-15.0` for "Exchange hacked", `+8.0` for "ETF approval rumor"), roughly in the `-30` to `+30` range depending on event severity.
**Not called by Member 3, and not tied to trades.** `news_engine.py` runs a background thread (using the `threading` library, allowed per the PRD) that calls this automatically on a randomized interval (e.g. every 45–90 seconds), independent of any user action. The thread starts automatically when `news_engine.py` is first imported — no setup call needed from `app.py` or the frontend. This function is documented here because Member 1 will still want to unit-test it standalone.

### `get_news_feed(limit: int = 10) -> list[dict]`
Returns the most recent generated events, same shape as `generate_news_event()`, newest first. Returns `[]` if none generated yet. This is what Member 3's news page displays.

### `apply_news_impact(coin: str) -> float`
Returns the currently active `impact_pct` for a coin (`0.0` if no active news), consumed internally by `get_boosted_price()`. Not typically called directly by Member 3 — it's the coupling point between the news engine and the price engine.
**Decay rule (locked):** when a news event fires for a coin, its `impact_pct` applies at full strength for the next **3 calls** to `get_boosted_price()` for that coin, then drops to `0.0` (a hard cutoff, not a gradual fade). If a new event fires for the same coin before the previous one's 3 calls are used up, the new event's impact simply replaces the old one and resets the counter to 3.