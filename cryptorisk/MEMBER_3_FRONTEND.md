# Member 3 — Frontend + Visualization

**Owns:** `frontend/` folder and `app.py` (see `FILE_STRUCTURE.md`)
**Files:** `app.py`, `frontend/login_page.py`, `frontend/signup_page.py`, `frontend/dashboard_page.py`, `frontend/trade_page.py`, `frontend/portfolio_page.py`, `frontend/news_page.py`

## Goal

Turn the backend and DB layers into something a user can actually see and click through — clean Streamlit pages, working charts, smooth navigation.

> **Function signatures for everything below are locked in `INTERFACES.md`. Read it before writing code — it also covers failure/edge-case behavior (what a function returns when nothing is found), which this doc doesn't repeat.**

## Core Tasks

- [ ] **Navigation mechanism (locked): use `st.sidebar` + `if/elif`, not `st.tabs`.** This isn't a style preference — it's required by how the Dashboard's auto-refresh works (see below).
  - **The core Streamlit fact to know:** on every rerun (any click, any form submit, any timer firing), Streamlit re-executes the *entire* script top to bottom. It doesn't just update the part of the screen you're looking at.
  - **Why tabs don't work here:** `st.tabs` puts all four pages' code in one script, each nested inside its own tab block. But because of the fact above, the code inside *every* tab still runs on every rerun — Streamlit just visually hides the tabs you're not on. Nothing is actually skipped. So the Dashboard's 15-second auto-refresh loop (`time.sleep(15)` + `st.rerun()`) would keep firing even while a user is sitting on the Portfolio or News page, force-refreshing the whole app every 15 seconds no matter where they are — not what we want.
  - **Why sidebar + if/elif works:** only the branch matching the selected page actually executes. The Dashboard's sleep-and-rerun loop only runs when Dashboard is the page currently selected. Sit on Portfolio, and nothing refreshes until the user clicks back to Dashboard themselves.
  - **Pattern to follow in `app.py`:**
    ```python
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        # unauthenticated: login <-> signup
        auth_page = st.sidebar.radio("", ["Login", "Signup"])
        if auth_page == "Login":
            login_page.render()
        elif auth_page == "Signup":
            signup_page.render()
    else:
        # authenticated: the 4 main pages
        page = st.sidebar.radio("Go to", ["Dashboard", "Trade", "Portfolio", "News"])
        if page == "Dashboard":
            dashboard_page.render()
        elif page == "Trade":
            trade_page.render()
        elif page == "Portfolio":
            portfolio_page.render()
        elif page == "News":
            news_page.render()
    ```
  - This is also simply less code than tabs — one `if/elif` chain instead of wrapping every page in a `with tab:` block — and it naturally handles the login/signup ↔ main-app split described later in this doc using the exact same pattern, just gated on `st.session_state.logged_in`.
  - **One side effect to expect, not fix:** while the Dashboard's `time.sleep(15)` is running, nothing on that page is clickable — this is a real limitation of building auto-refresh this way with the allowed libraries, not a bug.
  - **Logout is explicitly out of scope for MVP (locked).** No logout button/flow — once `st.session_state.logged_in` is set `True`, the only way back to the login page is closing/restarting the app (session state resets). Don't build a logout control unless the team later decides to add it.
- [ ] **Login page** — username/password form. **Important: there's no dedicated login function on the DB side.** Call Member 2's `get_user(username)`, then compare `result["password"]` against the entered password yourself, right here in `login_page.py`. Handle `None` (username not found) as a distinct error message from "wrong password." Include a link/button to the signup page for users without an account.
- [ ] **Signup page** — its own dedicated page (`signup_page.py`), not a tab or toggle inside `login_page.py`. Username/password form (consider a "confirm password" field for basic UX, purely client-side). Calls Member 2's `create_user(username, password)` and branches on the return dict: `success: False` → show `message` as an error (this is how a duplicate username surfaces — no separate uniqueness check needed on your end, the DB layer already did it); `success: True` → show a confirmation and route the user to the login page (or straight into a logged-in session, if the team prefers auto-login — either is fine, just be consistent with how `login_page.py` sets session state). Add a link back to login for existing users.
- [ ] **Dashboard page** — live price display for BTC/ETH/SOL/DOGE, pulling from Member 1's `get_live_prices()` (batch, for the 4-coin display) and `get_boosted_price()` (per-coin, for current values) plus `get_price_history()` (for the movement and volatility-spikes charts — both live here, see the Plotly charts task below). **Confirmed fine to call `get_boosted_price()` 4x per rerun** (once per coin) — it doesn't hit CoinGecko directly, just reads the already-throttled real price and does cheap math, so no batch version is needed here (unlike `get_live_prices()`, which exists specifically to avoid repeated API calls).
  - **Handle `None` from `get_boosted_price()` (locked, see `INTERFACES.md`).** This now returns `None` for a valid coin if CoinGecko itself failed, not just for an invalid coin — show a "price temporarily unavailable" state for that coin's card instead of crashing the page. This applies here and on the Portfolio page (below) wherever `get_boosted_price()` is called directly.
  - **Empty/near-empty history guard.** Right after the app starts, `get_price_history(coin)` will legitimately return `[]` or just 1–2 points — a Plotly line chart on that little data looks broken, not blank. Guard for it: e.g. `if len(history) < 2: st.info("Gathering price data…")` instead of handing it straight to the chart. Applies to all three chart types below (real-vs-boosted, volatility spikes, portfolio growth), since all three read from the same early-app-life data source.
  - **Auto-refresh (locked): the dashboard reruns on its own every 15 seconds** — no manual "refresh" button needed. Simplest approach with the allowed libraries: call `time.sleep(15)` followed by `st.rerun()` at the end of the page's render, or use a small placeholder loop — either way, no new dependency is needed (no `streamlit-autorefresh` or similar, since it's not on the allowed-libraries list). This is independent of the 30-second CoinGecko throttle in `get_live_price()`/`get_live_prices()` — some 15-second reruns will just re-serve the same cached real price, which is expected and fine; the boosted price still updates every rerun since its random/news component changes independently. **This is exactly why navigation must be sidebar + if/elif, not tabs — see the Navigation task above.**
- [ ] **Trading page** — buy/sell forms (coin, quantity), calls Member 1's `execute_trade()`, shows success/error feedback (insufficient balance, invalid quantity, etc.)
- [ ] **Portfolio page** — holdings table, balance, profit/loss, total investment, pulling from Member 2's `get_portfolio()` for holdings and Member 1's `get_boosted_price()` for each coin's current price (needed to compute live profit/loss: `(current_boosted_price - buy_price) * quantity`). Also hosts the **portfolio-growth chart** (see the Plotly charts task below — built from `get_transaction_history()` + `get_portfolio()`, not price history). If `get_boosted_price()` returns `None` for a held coin, skip that coin's live P/L for this render (e.g. show "price unavailable" next to that row) rather than crashing the whole page — don't let one coin's fetch failure take down the rest of the table.
- [ ] **News feed page** — displays fake market events by calling Member 1's `get_news_feed(limit)`. Note these events aren't just decorative — they're also actively nudging the boosted prices you show elsewhere, so this page is explaining *why* the dashboard is moving, not a side attraction.
- [ ] **Plotly charts (placement locked):** real-vs-boosted price movement and volatility-spikes both live on the **Dashboard page** (both read the same `get_price_history()` call per coin). Portfolio-growth lives on the **Portfolio page** (it reads `get_transaction_history()` + `get_portfolio()`, not price history, so it belongs next to the holdings table it explains). All three pull from Member 1's `get_price_history(coin, limit)` or Member 2's transaction/portfolio functions as noted below — you never accumulate history yourself in `st.session_state`, the backend/DB already keep it:
  - Real-time price movement (real vs boosted) — plot both series from the same `get_price_history()` call
  - Volatility spikes visualization — same data, highlight large jumps between consecutive `boosted_price` points
  - Portfolio growth over time — this one's different: build it from Member 2's `get_transaction_history()` (running balance/holdings value over the trade timeline), not from price history. **Methodology (locked):**
    1. Call `get_transaction_history()` and sort the results **oldest → newest** (the function itself returns newest-first, so reverse it for this chart).
    2. Walk through transactions in that order, maintaining a running `cash` total (start at `10000.0`) and a running `{coin: quantity}` holdings dict. For each `BUY`, subtract `quantity * price` from `cash` and add to holdings; for each `SELL`, add `quantity * price` to `cash` and subtract from holdings. Track each coin's `price` from that same transaction row as its "last known price."
    3. After each transaction, plot one point: `total_value = cash + sum(quantity_held[coin] * last_known_price[coin] for coin in holdings)`. This uses the price actually recorded on the transaction, not a live lookup — it's the value the trade itself already tells you.
    4. Add one final point for "now": `cash + sum(quantity * get_boosted_price(coin)["boosted_price"])` using the live portfolio from `get_portfolio()`, so the chart's rightmost point reflects current prices instead of stopping at the last trade.
    - This keeps everything inside `frontend/` — no new function needed from Member 1 or Member 2, and it only uses data both already expose.
- [ ] **Display rounding (locked): round every displayed monetary value and coin quantity to 3 decimal places** — balance, prices, profit/loss, total investment, holdings quantity (e.g. `f"{value:.3f}"`). These are `FLOAT` under the hood and will otherwise show ugly precision artifacts (`$9999.999999997`). This is display-only formatting in `frontend/` — don't round anything before it's stored or used in a calculation, only when it's rendered to the screen.
- [ ] **Navigation** — smooth page routing via `app.py` using the sidebar + if/elif pattern locked above, consistent layout across pages. **`app.py` ownership (locked):** you own and write this file — it's frontend routing logic in substance, even though it lives at the repo root. Members 1 and 2 give you a heads-up in the group chat before requesting a new page/route rather than editing it directly — that's how 3-way merge conflicts on a single file happen. Needs an unauthenticated-state path between login ↔ signup (not just the 4 post-login pages) — `app.py` shows login/signup until `st.session_state.logged_in` is `True`, then switches to the sidebar radio for the other 4 pages, per the pattern above.

## Deliverables / Definition of Done

- All 6 pages (including signup) render without errors and look coherent as one app, not disconnected pieces
- Navigation uses sidebar + if/elif, not tabs — confirm the Dashboard's auto-refresh only fires while Dashboard is the selected page
- Charts update when new trades happen or prices refresh (dashboard auto-refreshes every 15 seconds on its own) — no stale data on screen
- Every button/form is wired to a real backend/DB call, not a placeholder
- Error states are visible to the user (e.g. "insufficient balance") instead of silent failures or raw tracebacks

## Dependencies

- **Blocked on Member 1** for: `get_live_price()`, `get_live_prices()`, `get_boosted_price()`, `get_price_history()`, `execute_trade()`, `get_news_feed()`
- **Blocked on Member 2** for: `get_user()` (login), `create_user()` (signup), `get_portfolio()`, `get_transaction_history()`
- Full signatures and return shapes for all of the above are in `INTERFACES.md` — this is now locked, so build against it directly rather than asking either teammate.
- Since you depend on both other members, this is the role most likely to be waiting — mitigate it by building UI against **stub functions** matching `INTERFACES.md` signatures from day one, then swapping in real calls as they land
- **Git note:** this folder is the most naturally isolated slice of the app, which is why it's a good fit if you're less comfortable with Git — you can work mostly independently and hand off files for a teammate to commit if needed (see the team's hybrid Git approach)

## Suggested Order of Attack

1. Build `app.py`'s sidebar + if/elif skeleton first (login/signup ↔ the 4 main pages), even with empty page functions — get the navigation shape locked before filling in content
2. Build static page skeletons (layout, forms, placeholders) inside each page file — no real data needed yet
3. Wire in stub functions matching `INTERFACES.md`, confirm pages behave with fake data
4. Build Plotly charts against the stubbed data so chart logic is done before real data exists
5. Swap stubs for real backend/DB calls as Member 1 and Member 2 deliver them
6. Polish: navigation flow, error messages, consistent styling across all 6 pages last