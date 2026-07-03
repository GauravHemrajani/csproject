# CryptoRisk — File Structure

This is the locked folder/file layout. Nobody creates new top-level files or renames existing ones without telling the other two — that's how merge conflicts and "where did you put that function" chaos happen.

```
cryptorisk/
│
├── app.py                     # Streamlit entry point — page router only, no logic here
├── requirements.txt           # pinned dependencies, one source of truth
├── .env                       # local secrets (MySQL host/user/password, CoinGecko API base URL/key) — NEVER committed
├── .gitignore                 # must include .env, __pycache__/, *.pyc
├── config.py                  # loads .env, exposes constants (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, API_BASE_URL, etc.)
│
├── db/                        # Member 2 — Database
│   ├── __init__.py
│   ├── connection.py          # get_connection() — opens a mysql.connector connection to the local MySQL server
│   ├── schema.sql             # CREATE DATABASE + CREATE TABLE statements (users, portfolio, transactions)
│   ├── users_db.py            # get_user(), create_user(), update_balance()
│   ├── portfolio_db.py        # get_portfolio(), upsert_holding()
│   └── transactions_db.py     # insert_transaction(), get_transaction_history()
│
├── backend/                   # Member 1 — Backend logic
│   ├── __init__.py
│   ├── price_engine.py        # get_live_price(), get_live_prices(), get_boosted_price(), get_price_history() (volatility formula + in-memory history buffer)
│   ├── trade_engine.py        # execute_trade() — buy/sell validation + orchestration
│   └── news_engine.py         # generate_news_event(), get_news_feed(), apply_news_impact() — background timer thread auto-generates events
│
├── frontend/                  # Member 3 — Streamlit UI
│   ├── __init__.py
│   ├── login_page.py
│   ├── signup_page.py         # registration form — calls db.create_user()
│   ├── dashboard_page.py      # live prices + charts
│   ├── trade_page.py          # buy/sell UI
│   ├── portfolio_page.py      # holdings, P/L
│   └── news_page.py           # fake news feed display
│
├── CryptoRisk_Project_Summary.md
├── FILE_STRUCTURE.md
├── INTERFACES.md              # LOCKED contract for every cross-module function — read before writing code
├── MEMBER_1_BACKEND.md
├── MEMBER_2_DATABASE.md
├── MEMBER_3_FRONTEND.md
├── SETUP.md
```

**Real DB server required.** The database is MySQL, running as a local server process on each teammate's machine (MySQL Community Server, or the MySQL bundled with XAMPP/WAMP). `.env`/`config.py` carry `DB_HOST` (usually `localhost`), `DB_USER`, `DB_PASSWORD`, `DB_NAME` (`cryptorisk`), plus the CoinGecko API base URL (and an API key, if you end up using one). Unlike a single-file database, there's no DB artifact to accidentally commit — but credentials in `.env` must still never be committed.

## Ownership map

| Folder | Owner | Others may... |
|---|---|---|
| `db/` | Member 2 | ...call functions, never edit internals directly |
| `backend/` | Member 1 | ...call functions, never edit internals directly |
| `frontend/`, `app.py` | Member 3 | ...call functions; heads-up in group chat before adding new pages/routes to `app.py` |
| `config.py`, `requirements.txt` | Shared | Edit only with a heads-up in the group chat — these are the most conflict-prone files |

**`config.py` and `SETUP.md` (locked):** no fixed owner — whoever sets up the repo/environment first writes the initial version of both, and the other two just follow what's there. Since these two files barely change after the first setup, this stays informal rather than assigning a permanent owner.

## Rules that make this survivable with 3 people on Git

1. **`app.py` stays thin, and Member 3 owns it (locked).** It's really just routing logic between frontend pages — imports from `frontend/` and switches between pages via `st.sidebar` or `st.tabs`, no business logic, no DB calls, no API calls directly in it. Since it's a frontend concern in substance, Member 3 writes and maintains it. Members 1 and 2 can still request changes (e.g. a new page needs a route) but give Member 3 a heads-up in the group chat first rather than editing it directly — that's how 3-way merge conflicts on a single file happen.
2. **Every folder gets an `__init__.py`** (can be empty) so imports like `from db.users_db import get_user` work cleanly.
3. **`.env` is never committed.** Each teammate creates their own local MySQL user/database and their own `.env` from a shared `.env.example` (add this file if useful — happy to generate it). Since MySQL is a real server, each teammate's local data is independent per machine unless you explicitly export/import (e.g. via `mysqldump` for a demo with pre-loaded data).
4. **`schema.sql` is the single source of truth for the DB structure.** If Member 2 changes a column or table, this file is updated immediately and the other two are notified — this is where the PRD's schema lives in code form. Everyone re-runs `schema.sql` against their own local MySQL server after a schema change.
5. **`INTERFACES.md` is locked.** Every function signature crossing `db/` ↔ `backend/` ↔ `frontend/` lives there. If you find yourself guessing a parameter order or return type instead of checking that file, stop and check the file first.
