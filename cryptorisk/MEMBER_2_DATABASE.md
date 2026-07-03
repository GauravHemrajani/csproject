# Member 2 — Database + Data Layer

**Owns:** `db/` folder (see `FILE_STRUCTURE.md`)
**Files:** `db/connection.py`, `db/schema.sql`, `db/users_db.py`, `db/portfolio_db.py`, `db/transactions_db.py`

## Goal

Build the data foundation everyone else depends on. This is the most independent role on the team — the schema is already fully specified in the PRD, so you can build and test everything against dummy data without waiting on the API, Streamlit, or the volatility engine.

**Engine: MySQL (`mysql.connector`).** You need a real MySQL server running locally — install MySQL Community Server, or use the MySQL bundled with XAMPP/WAMP if that's easier to set up. The database itself (`cryptorisk`) is created with `CREATE DATABASE cryptorisk;` and connected to with `mysql.connector.connect(host=..., user=..., password=..., database="cryptorisk")` (see `get_connection()` in `INTERFACES.md`). Every teammate runs their own local MySQL server — there's no shared server for the group project.

> **Function signatures for everything below are locked in `INTERFACES.md`. Read it before writing code — it also covers failure/edge-case behavior (None vs False vs empty list), which this doc doesn't repeat.**

## Core Tasks

- [ ] **Connection lifecycle (locked): use short-lived connections, not one shared long-lived connection.** Every function in `db/` that touches the database — `get_user()`, `create_user()`, `update_balance()`, `get_portfolio()`, `upsert_holding()`, `insert_transaction()`, `get_transaction_history()` — must open its own connection via `get_connection()`, do its query, and close the connection (and cursor) before returning. Do **not** open one connection at app startup and reuse it for the lifetime of the session.
  - **Why this matters:** Streamlit reruns the entire script on every user interaction and on the dashboard's 15-second auto-refresh. A connection opened once and held open across many reruns will eventually be dropped by MySQL (`MySQL server has gone away`) after sitting idle too long, and every DB call after that silently fails until the app restarts. Short-lived, open-query-close connections avoid this entirely and are cheap enough on a local MySQL server that there's no real performance downside for this project's scale.
  - **Pattern to follow in every `db/` function:**
    ```python
    def get_user(username):
        conn = get_connection()
        if conn is None:
            return None
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            return row
        except Exception as e:
            print(e)
            return None
        finally:
            conn.close()
    ```
  - This applies uniformly across `users_db.py`, `portfolio_db.py`, and `transactions_db.py` — every function, no exceptions, so behavior is consistent and nobody has to remember which functions are "safe" to call repeatedly and which aren't.
- [ ] **Error logging (locked)** — `get_connection()` and every function that catches a connection/query error must `print()` the actual exception before returning `None`/`False`/`[]` as spec'd. The return value itself still doesn't distinguish "not found" from "DB failed" (that's unchanged and intentional) — the print statement is just so a real failure is visible in the terminal instead of looking identical to a normal "not found" case. See `INTERFACES.md` for the full note.
- [ ] **Set up the local MySQL server first.** Install MySQL Community Server (or XAMPP/WAMP), start the service, and confirm you can log in via `mysql -u root -p` (or a dedicated non-root user, your choice) before writing any Python. This is a one-time setup step per machine — see `SETUP.md`.
- [ ] **Design/finalize the MySQL schema** — `users`, `portfolio`, `transactions` (already spec'd in the PRD — implement it in `schema.sql`, starting with `CREATE DATABASE cryptorisk;` and `USE cryptorisk;`).
  - **Use manual ID generation on `userid` and `transid`** — declare both as plain `INT PRIMARY KEY` (no `AUTO_INCREMENT`). `create_user()` and `insert_transaction()` each run `SELECT COALESCE(MAX(...), 0) + 1` to compute the next ID, then insert explicitly with that value. Keep the compute-then-insert as tight as possible within the same function call to minimize (low-risk on a single local server) the chance of two inserts computing the same ID.
  - `trade_date` uses MySQL's native `DATE` type — declare it `DATE` in `schema.sql`. `mysql.connector` converts to/from Python `date` objects automatically, so no manual string formatting is needed in `insert_transaction()` or `get_transaction_history()`.
  - Add `FOREIGN KEY (userid) REFERENCES users(userid)` on both `portfolio` and `transactions` — this is a real, enforced constraint in MySQL.
- [ ] **Write all SQL queries** demonstrating CBSE-safe concepts:
  - `INSERT`, `UPDATE`, `DELETE`, `SELECT ... WHERE`
  - `ORDER BY`, `BETWEEN`, `IN`, `LIKE`, `DISTINCT`
  - Aggregates: `SUM()`, `COUNT()`, `AVG()`, `MAX()`
  - `GROUP BY`, `HAVING`
  - Joins (standard syntax: `users, transactions WHERE users.userid = transactions.userid`, or explicit `JOIN ... ON`)
  - **Database-level commands** (`CREATE DATABASE`, `USE`, `SHOW DATABASES`, `DROP DATABASE`) — these are real MySQL statements now, not just conceptual. Have `schema.sql` demonstrate them explicitly at the top, since evaluators expect to see this in the viva.
- [ ] **Build Python DB connector functions** using `mysql.connector` (`pip install mysql-connector-python`), wrapping `connect()`, `cursor()`, `execute()`, `commit()`, `fetchone()`, `fetchall()` — each wrapped inside the open-query-close pattern above.
- [ ] **Signup validation** — `create_user()` checks username uniqueness internally before inserting (see `INTERFACES.md` for the exact return shape on a duplicate)
- [ ] **Login** — you only need to implement `get_user(username)`. **There is no separate `login_user()` function** — Member 3 calls `get_user()` and compares the plaintext password itself in `login_page.py`. Don't build password verification into the DB layer.
- [ ] **Transaction history storage** — every buy/sell gets logged to `transactions` with a proper `trade_date`. Since `trade_date` is a native `DATE` column in MySQL, both `insert_transaction()` and `get_transaction_history()` pass/receive real Python `date` objects directly — `mysql.connector` handles the conversion. No manual ISO-string formatting needed anywhere.
- [ ] **`upsert_holding()` delete-on-zero** — if the resulting quantity after a sell is `<= 0`, this function must delete the `portfolio` row rather than leaving a zero-quantity row behind. Member 1 will just pass you the new total quantity; the delete logic lives here, not in `backend/`.

## Deliverables / Definition of Done

- All three tables created and match the PRD schema exactly (plain `INT PRIMARY KEY` on `userid`/`transid` — no `AUTO_INCREMENT`, IDs generated manually via `SELECT MAX(...)+1` — and the `FOREIGN KEY` constraints on `portfolio`/`transactions`)
- Every function opens its own connection and closes it before returning — no shared/long-lived connection anywhere in `db/`
- Every CRUD operation works reliably against the real local MySQL `cryptorisk` database, not just in theory
- SQL syllabus concepts (joins, aggregates, grouping, and the MySQL-specific database commands) are clearly demonstrated somewhere in the codebase — useful for the viva
- Function signatures match `INTERFACES.md` exactly — this is what lets Member 1 and Member 3 build against you without waiting

## Dependencies

- **You're independent early** — nothing blocks you at the start, other than getting MySQL installed and running locally. Build against dummy/sample rows you insert yourself.
- **You unblock everyone else.** Member 1 needs `get_user()`, `update_balance()`, `insert_transaction()`, `upsert_holding()`. Member 3 needs `get_user()` (for login), `get_portfolio()`, `get_transaction_history()`. Late or changed signatures here stall both of them.
- **Critical rule:** `INTERFACES.md` is now locked. Do not change a function's name, parameters, or return type without telling the group immediately. A silent change here is the #1 way this project breaks in week 3–4 when the others start calling your functions for real.

## Suggested Order of Attack

1. Install and start MySQL locally (Community Server or XAMPP/WAMP). Confirm you can connect via `mysql -u root -p`.
2. Run `schema.sql` against a fresh MySQL server (`CREATE DATABASE cryptorisk;`, then the three `CREATE TABLE` statements). Confirm all 3 tables create cleanly with `SHOW TABLES;`.
3. Manually insert a few dummy rows, write and test every query from the "Required SQL Concepts" list against them
4. Wrap each query in a Python function matching the agreed `INTERFACES.md` signature, using the open-query-close connection pattern above
5. Manually exercise every function against your local MySQL data (e.g. via a Python REPL or throwaway `print()` calls) before handing off — no formal test suite/`tests/` folder for this project (team decision), just confirm each function behaves per `INTERFACES.md` before Member 1/Member 3 start calling it
6. Hand off signatures early — you're the critical path for the other two, so lock this before diving deep into polish