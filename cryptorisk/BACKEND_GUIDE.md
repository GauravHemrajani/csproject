# CryptoRisk — Backend Navigation Guide

A simple map of the code for **Member 1 (Backend)**. It explains what each file
does, how they connect, and how information moves through the app — all in plain
words.

Read this next to `INTERFACES.md`. Quick difference:
- **This guide** explains *how* the backend works and why.
- **`INTERFACES.md`** is the strict rulebook for the *exact* function names,
  what you pass in, and what comes back. If the two ever seem to disagree,
  `INTERFACES.md` wins.

---

## 1. The big picture

CryptoRisk has 3 layers. Each teammate owns one:

```
   frontend/  (Member 3)   →   the screens the user clicks on (Streamlit)
        │ calls
        ▼
   backend/   (Member 1)   →   YOU: prices, volatility, trades, news
        │ calls
        ▼
   db/        (Member 2)   →   the MySQL database (users, portfolio, transactions)
```

The frontend never talks to the database directly. It always goes through your
backend. Think of your backend as the **"brain"** in the middle: it grabs real
prices, blows them up into a wild fake market, runs the trades, and produces the
fake news.

---

## 2. What exists right now

Only the **backend** is built so far (that's your job — teammates add their
folders later). Here's the current layout.
✅ = built and tested by you · ⏳ = a teammate's file that doesn't exist yet.

```
cryptorisk/
├── config.py            ✅ shared settings — reads .env, hands out constants
├── requirements.txt     ✅ the exact library versions everyone installs
│
├── backend/             ← YOUR folder
│   ├── __init__.py      ✅ tells Python "backend/ is a package you can import"
│   ├── constants.py     ✅ the one master coin list (BTC/ETH/SOL/DOGE) + id map
│   ├── price_engine.py  ✅ live prices + the volatility engine
│   ├── trade_engine.py  ✅ buy/sell logic
│   └── news_engine.py   ✅ fake news generator (runs on its own timer)
│
├── db/                  ✅ Member 2 — the real MySQL layer
├── frontend/            ⏳ Member 3 — the Streamlit screens (not built yet)
└── app.py              ⏳ Member 3 — the app's starting point (not built yet)
```

---

## 3. File-by-file walkthrough (backend)

### `config.py` (shared, sits at the project root)
Reads your personal `.env` file using plain Python (no extra library) and hands
out simple settings the whole app can import: `DB_HOST`, `DB_USER`,
`DB_PASSWORD`, `DB_NAME` (for the database) and `API_BASE_URL`, `API_KEY` (for
CoinGecko). If there's no `.env` file, it uses safe default values — that's why
the price engine still works even before you've made a `.env`.

### `backend/constants.py` — the one master coin list
A tiny file that holds two things:
- `COIN_ID_MAP` — links the short ticker we use (`"BTC"`) to the full name
  CoinGecko wants (`"bitcoin"`).
- `SUPPORTED_COINS` — the list `["BTC", "ETH", "SOL", "DOGE"]`, built straight
  from that map.

**Why it exists:** the coin list used to be typed out *twice* — once in
`price_engine.py` and once in `news_engine.py`. If someone added a coin to one
and forgot the other, you'd get weird bugs. Now both files read from this **one
place**, so they can never disagree. This file imports nothing from the rest of
`backend/`, so importing it can never cause an import loop.

### `backend/price_engine.py` — prices + the volatility engine
The most important backend file. It has two jobs:

1. **Get real prices** from CoinGecko. `_fetch_from_coingecko()` is the only
   function in the whole project that actually touches the internet. There's a
   **30-second memory per coin** (`_price_cache`): once we fetch a coin's price,
   we reuse that same number for 30 seconds instead of asking CoinGecko again —
   no matter how many times the screen refreshes. This keeps us safely under
   CoinGecko's free limit.
   - `get_live_price(coin)` — one coin's real price.
   - `get_live_prices([...])` — all coins in ONE request (what the dashboard uses).

2. **Blow reality up** into a fast, wild fake market. `get_boosted_price(coin)`
   uses the locked formula:
   ```
   boosted_change_pct = (real_change_pct * 5) + a bit of random noise + news effect
   boosted_price      = real_price adjusted by that boosted change
   ```
   Every successful call also saves that moment (real price + boosted price +
   time) into a memory list, which `get_price_history(coin)` gives to Member 3
   for the charts.

   **Recent fix (real-change now sticks):** the real price only updates every 30
   seconds (that 30-second memory above). Earlier, the "real change %" showed up
   for a single split-second and then read `0.00%` on every refresh until the
   next update — so the "5× bigger swings" feature was basically invisible. Now
   the real change is **remembered and kept for the whole 30-second window**, so
   the 5× effect stays switched on and you can actually see it. (Note: real
   crypto barely moves in 30 seconds, so the swing is *correct* but still gentle
   — making it look dramatic would mean changing the locked formula, which needs
   the whole team to agree first.)

   **Recent fix (dashboard and a trade now always agree on price):**
   `get_boosted_price()` used to recompute from scratch — re-rolling its random
   noise and re-consuming any news impact — on *every single call*. That meant
   the price shown on the dashboard a moment ago could already be stale/different
   by the time a trade actually fired. It now caches one snapshot per coin for
   `BOOSTED_TICK_SECONDS` (3 seconds); any call for that coin inside the window
   gets a copy of the same cached snapshot, so a user always trades at the exact
   price they were just shown. Only a freshly-computed tick is appended to the
   history buffer — a cache hit doesn't create a duplicate point.

   **Recent fix (price can't go to zero or negative):** the amplified
   `boosted_change_pct` is now floor-clamped at `-95.0`
   (`BOOSTED_CHANGE_FLOOR`). Without this, a severe real crash amplified 5x plus
   a bad-news hit could in theory push the change below `-100%`, making
   `boosted_price` negative — which would let a BUY slip past the balance check
   and hand the user free cash. `trade_engine.py` also independently rejects a
   non-positive price as a second line of defense.

### `backend/trade_engine.py` — buy/sell logic
`execute_trade(userid, coin, action, quantity)` is the **"cashier"**. Step by
step it:
1. Checks the request makes sense (real action? real coin? quantity above 0?).
2. Gets the **boosted** price (trades always happen at the boosted price, never
   the plain real price).
3. Checks the user can afford a BUY / actually owns enough for a SELL.
4. Writes three things to the database: the new cash balance, the updated coin
   holding, and a line in the transaction history.

It also has `calculate_weighted_avg_buy_price()` — the maths that keeps a coin's
average buy price correct when you buy more of a coin you already own.

**Recent fix (no leftover crumbs):** when you sell *everything*, the leftover
amount can come out as a microscopic number like `0.00000000000000005` instead
of a clean `0` (computers can't store some decimals perfectly). That would leave
a fake "ghost" holding behind. The code now rounds anything that tiny down to
`0`, so a full sell properly removes the coin from your portfolio.

**Recent fix (bad input can't corrupt the balance):** `execute_trade()` now
rejects any `quantity` that isn't a real, finite number — strings, `None`,
booleans, `NaN`, `inf` — before doing any math. `NaN` in particular is sneaky:
it compares `False` to *every* numeric check (`NaN <= 0` is `False`, `cost >
balance` is `False`, ...), so without this check a `NaN` quantity would sail
straight through every guard below it and corrupt the stored balance/holding
with `NaN`.

**Recent fix (all-or-nothing writes):** the three DB writes
(`update_balance()` → `upsert_holding()` → `insert_transaction()`) now roll
back by hand if a later one fails. For example, if `insert_transaction()`
fails after the balance and holding were already updated, `execute_trade()`
puts both back to their exact pre-trade values instead of leaving a
half-applied trade sitting in the database.

**Recent fix (clean cents):** the cash balance is now rounded to 2 decimals
(`round(..., 2)`) on every write, for both BUY and SELL, so binary-float dust
can't slowly accumulate in the balance over many trades. Coin quantities keep
full precision — only the dollars-and-cents balance is snapped.

**How it talks to the database:** at the top it imports straight from Member 2's
real `db/` package (`db.connection`, `db.users_db`, `db.portfolio_db`,
`db.transactions_db`). All calls go to the real MySQL database.

### `backend/news_engine.py` — the fake news engine
A background timer (starts on its own when the file is first imported) fires a
random fake event every 45–90 seconds — no user action needed. Each event:
- goes into `_news_feed`, which `get_news_feed()` shows on the news page, and
- switches on a price effect via `apply_news_impact()`, which the volatility
  engine reads. The effect lasts exactly **3 calls** to `get_boosted_price()`
  for that coin, then switches off.

This link is what makes news *matter*: an "Exchange hacked!" event genuinely
drags the boosted price down for a few ticks.

**Recent fixes:**
- **No duplicate news timers.** Streamlit sometimes reloads a file behind the
  scenes, which could accidentally start a *second* timer and show news twice.
  The timer thread now has a name, and before starting one we check whether a
  timer with that name is already running — so only ever one exists.
- **The news feed hands out copies.** `get_news_feed()` now gives the frontend
  *copies* of the events instead of the originals, so the UI can't accidentally
  change the backend's own records. (`get_price_history()` in `price_engine.py`
  does the same thing now.)

---

## 4. How a single trade flows through the code

When a user clicks "Buy 0.1 BTC" (once the frontend exists):

```
frontend/trade_page.py
   └─ calls  execute_trade(userid, "BTC", "BUY", 0.1)      [trade_engine.py]
              └─ calls  get_boosted_price("BTC")            [price_engine.py]
                         ├─ calls  get_live_price("BTC")    → CoinGecko (or cache)
                         └─ calls  apply_news_impact("BTC") [news_engine.py]
              └─ opens ONE db connection, then on it:
                 ├─ get_user_by_id(userid, conn, for_update=True)  [db/users_db.py]
                 │    (FOR UPDATE locks this user's row — a 2nd
                 │     simultaneous trade waits here until commit)
                 ├─ get_portfolio(userid, conn)             [db/portfolio_db.py]
                 ├─ update_balance(..., conn)               [db/users_db.py]
                 ├─ upsert_holding(..., conn)               [db/portfolio_db.py]
                 ├─ insert_transaction(..., conn)           [db/transactions_db.py]
                 └─ conn.commit()   (all-or-nothing; releases the row lock)
   └─ shows the returned {"success", "message", ...} to the user
```

---

## 5. Resolved: `get_user_by_id`

`execute_trade()` is given a `userid`, but `INTERFACES.md` only had
`get_user(username)`. Member 2 has since delivered **`get_user_by_id(userid)`**
in `db/users_db.py` (same return shape as `get_user`), and `INTERFACES.md` now
documents it — including the optional `conn=` / `for_update=` parameters that
`execute_trade()` uses to lock the user's row for the duration of a trade
(see "Concurrency safety" in `INTERFACES.md`).

---

## 6. Running / testing the backend

See `SETUP.md` → "Backend setup & how to run it". In short, from the project
root:

```bash
./venv/bin/python -m backend.price_engine   # live prices + boosted prices
./venv/bin/python -m backend.trade_engine   # full buy/sell cycle vs the real DB
./venv/bin/python -m backend.news_engine    # sample events + 3-call decay
```

Each file has its own built-in test that prints results to the screen. The
`trade_engine` test writes to the real MySQL database, so it needs MySQL set up
(SETUP.md Steps 3–6) and a user with `userid` 1; the other two need no database.
