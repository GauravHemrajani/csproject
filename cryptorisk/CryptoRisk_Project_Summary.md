# CryptoRisk — Project Summary

**Type:** Grade 12 CBSE Computer Science Project (Python + SQL)
**Team Size:** 3 members
**Deadline:** 1 month

## Academic Positioning

> "A behavioral finance simulator demonstrating how cryptocurrency volatility influences irrational investment decisions and educating users about risks of speculative trading."

*Do not present this as a "crypto trading simulator" — that framing is academically weak.*

## Core Idea

CryptoRisk is an **educational cryptocurrency trading simulator** built to teach users about:

- Financial risk
- Market volatility
- Emotional investing mistakes (panic selling, FOMO, greed-driven decisions)
- Dangers of speculative crypto trading

It does **not** encourage real trading — it's a simplified Binance/Coinbase-style simulator combined with a behavioral finance education tool, using fake money only.

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Streamlit** | Faster than Tkinter, better UI/dashboards, easy chart integration |
| Database | **MySQL** (`mysql.connector`) | Matches the standard CBSE Class 12 CS "Python–SQL interface" syllabus, which is written around MySQL. Evaluators expect to see `CREATE DATABASE`, `USE`, `SHOW DATABASES`, and `mysql.connector` during the viva. Demonstrates every required CBSE SQL concept (DDL, DML, joins, aggregates, grouping) using a real database server. |

**Allowed libraries:** `streamlit`, `mysql-connector-python` (install via `pip install mysql-connector-python`), `pandas`, `numpy`, `requests`, `plotly`, `datetime`, `time`, (optional) `threading`

**Explicitly disallowed:** Tkinter, Flask, Django, bcrypt, hashlib, TensorFlow. Passwords are stored in plain text (acceptable project simplification).

> ⚠️ **Setup requirement:** every teammate needs a local MySQL server installed and running (MySQL Community Server or XAMPP/WAMP's bundled MySQL both work). Each teammate creates the `cryptorisk` database locally on their own machine using `schema.sql` (see `SETUP.md`). Connection credentials (`host`, `user`, `password`) go in each person's local `.env` — **never commit real credentials.**

## Core Simulation Logic

- Each user starts with **$10,000 fake balance**.
- Users can buy/sell crypto, view portfolio, track profit/loss, and view transaction history.
- Supported coins: **BTC, ETH, SOL, DOGE**
- Real prices fetched from the **CoinGecko API**.

### Volatility Engine (Signature Feature)

Real price changes are artificially amplified to create a fast, high-volatility environment so users quickly experience emotional trading mistakes.

```
boosted_change = (real_change * 5) + np.random.normal(0, 3) + news_impact
```

Example: a real BTC change of +2% might become a simulated +14% (before any news impact). The `news_impact` term is not cosmetic — active fake news events actively nudge this value. The resulting % change is floor-clamped at -95% so the simulated price can never hit zero or go negative. **This formula is summarized here for context; `INTERFACES.md` is the authoritative, locked spec** for the exact function signature (`get_boosted_price()`) and field names.

## MVP Feature Scope

Build **only** these:

1. **Multi-user login + signup system** — userid, username, password, balance (starts at $10,000). Signup is its own dedicated page, separate from login.
2. **Real-time price fetching** — CoinGecko API for BTC, ETH, SOL, DOGE
3. **Buy/Sell system** — checks balance and quantity owned, updates DB automatically
4. **Portfolio page** — holdings, balance, profit/loss, total investment
5. **Live charts (Plotly)** — price movement, portfolio growth, volatility spikes
6. **Fake news engine** — generates fake market events (e.g., "Exchange hacked," "Whale sold 50,000 BTC," "Government bans exchange," "ETF approval rumor") that affect prices and demonstrate emotional reactions

### Explicitly Out of Scope

❌ Blockchain simulation · ❌ Crypto mining · ❌ Wallet generation · ❌ Smart contracts · ❌ Real money integration

## Database Design (3 Tables Only)

The database is a real MySQL database named `cryptorisk`, created via `CREATE DATABASE cryptorisk;` and connected to via `mysql.connector.connect(host=..., user=..., password=..., database="cryptorisk")` (see `db/connection.py` / `get_connection()` in `INTERFACES.md`). Each teammate runs their own local MySQL server.

### `users`
```sql
CREATE TABLE users (
    userid INT PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(100) NOT NULL,
    balance FLOAT
);
```
Demonstrates: primary key, unique, not null, varchar, float. `userid` is generated **manually** in Python — no `AUTO_INCREMENT`. `create_user()` runs `SELECT COALESCE(MAX(userid), 0) + 1 FROM users` to compute the next ID, then inserts explicitly with that value and includes it in its return dict.

### `portfolio`
```sql
CREATE TABLE portfolio (
    userid INT,
    coin VARCHAR(15),
    quantity FLOAT,
    buy_price FLOAT,
    PRIMARY KEY (userid, coin),
    FOREIGN KEY (userid) REFERENCES users(userid)
);
```
Demonstrates: foreign key relation, composite primary key. Composite primary key `(userid, coin)` ensures one row per user per coin — buying an already-held coin updates the existing row (recalculating average `buy_price`) rather than inserting a duplicate.

### `transactions`
```sql
CREATE TABLE transactions (
    transid INT PRIMARY KEY,
    userid INT,
    coin VARCHAR(15),
    action VARCHAR(10),
    quantity FLOAT,
    price FLOAT,
    trade_date DATE,
    FOREIGN KEY (userid) REFERENCES users(userid)
);
```
Demonstrates: date handling, relational structure, primary key, foreign key. Same as `users` — no `AUTO_INCREMENT`. `insert_transaction()` runs `SELECT COALESCE(MAX(transid), 0) + 1 FROM transactions` to compute the next ID, then inserts explicitly with that value and returns it.

**Date storage note:** MySQL has a native `DATE` type, so `trade_date` is stored natively — no string conversion needed anywhere. `insert_transaction()` and `get_transaction_history()` pass/receive real Python `date` objects directly; `mysql.connector` handles the conversion to/from MySQL's `DATE` type automatically.

## Required SQL Concepts (CBSE-Safe)

- **Database commands:** `CREATE DATABASE`, `USE`, `SHOW DATABASES`, `DROP DATABASE` — all standard MySQL statements, directly matching the syllabus. `SHOW TABLES` and `DESCRIBE table_name` also work natively.
- **Table commands:** `CREATE TABLE`, `DESCRIBE`, `ALTER TABLE ADD`, `ALTER TABLE DROP COLUMN`, `DROP TABLE`
- **DML:** `INSERT INTO`, `SELECT ... WHERE`, `UPDATE`, `DELETE`
- **Sorting/Filtering:** `ORDER BY`, `BETWEEN`, `IN`, `LIKE`, `DISTINCT`
- **Aggregates:** `SUM()`, `COUNT()`, `AVG()`, `MAX()`
- **Grouping:** `GROUP BY`, `HAVING`
- **Joins:** standard join syntax (e.g., `users, transactions WHERE users.userid = transactions.userid`); optional explicit `JOIN ... ON` / `NATURAL JOIN`

**Not allowed:** stored procedures, triggers, indexes beyond primary/foreign keys, advanced nested queries, transaction logic (`BEGIN`/`ROLLBACK`/`COMMIT`), ORM frameworks, advanced authentication.

## Python–SQL Integration

Must demonstrate the standard `mysql.connector` workflow (install via `pip install mysql-connector-python`):

```python
import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="yourpassword",
    database="cryptorisk"
)
cur = db.cursor()
cur.execute("SELECT * FROM users")
data = cur.fetchall()
```

Key methods to show: `connect()`, `cursor()`, `execute()`, `commit()`, `fetchone()`, `fetchall()`, `rowcount`. (No `lastrowid` — IDs are computed manually via a `SELECT MAX(...)+1` query before each insert, per the locked decision in `INTERFACES.md`.)

## Team Division

| Member | Responsibility |
|---|---|
| 1 — Backend Logic | API connection, volatility engine, buy/sell logic |
| 2 — Database | MySQL database, SQL queries, Python–SQL connectivity |
| 3 — Frontend/UI | Streamlit pages, dashboard, charts, user interaction |

**`INTERFACES.md` is the locked contract for every function that crosses between these three layers** (exact params, return shapes, and failure behavior). All three `MEMBER_*.md` docs reference it — build against it, not against assumptions about what a teammate's function returns.

## Constraints

- Must stay within CBSE Grade 12 syllabus (no college-level concepts)
- 3-person team, 1-month deadline
- Every teammate must have a local MySQL server installed and running before starting `db/` work