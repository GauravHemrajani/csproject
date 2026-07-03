# CryptoRisk — SETUP.md

One-time setup, done **once per teammate, on their own machine**, before writing any `db/` code (Member 2) or running the app. Member 1 and Member 3 also need Steps 1–5 done locally, since `execute_trade()`, login, and signup all hit the same local MySQL database.

## Prerequisites

- Python 3.10+ and `pip` on your PATH
- Git
- A local MySQL server: **MySQL Community Server**, or the MySQL bundled with **XAMPP/WAMP** — either works, pick whichever is easier to install on your OS

---

## Step 1 — Install & start MySQL

- **Windows:** install MySQL Community Server from the MySQL installer, or install XAMPP and start the MySQL module from the XAMPP Control Panel.
- **Mac:** `brew install mysql && brew services start mysql`, or use MAMP.
- **Linux:** `sudo apt install mysql-server && sudo systemctl start mysql`.

Set (and remember) a root password during install. Verify it works:

```bash
mysql -u root -p
```

If that drops you into a `mysql>` prompt, you're good — type `exit;` to leave.

---

## Step 2 — Get the project & Python environment

```bash
git clone <repo-url>
cd cryptorisk
python -m venv venv
# Windows:      venv\Scripts\activate
# Mac/Linux:    source venv/bin/activate
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist yet in your checkout, you're the first person setting up — create it at the project root with:

```
streamlit==1.58.0
mysql-connector-python==9.7.0
pandas==3.0.3
numpy==2.5.0
requests==2.34.2
plotly==6.8.0
```

(`datetime`, `time`, and `threading` are Python standard library — no pip install needed for those.) If any pin above fails to install on your machine, install that one package without a version number, then run `pip freeze > requirements.txt` to lock in whatever resolved, and share the updated file with the group.

---

## Step 3 — Create your local `.env`

**Never commit this file.** Create `.env` in the project root:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=cryptorisk
API_BASE_URL=https://api.coingecko.com/api/v3
API_KEY=
```

Leave `API_KEY` blank unless you've signed up for a CoinGecko API key — the free public endpoint works fine without one for this project's needs.

Confirm `.gitignore` includes `.env` before your first commit.

---

## Step 4 — Create `config.py`

If it doesn't exist yet in your checkout, you're the first person setting up — create it at the project root:

```python
import os

def _load_env(filepath=".env"):
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

_env = _load_env()

DB_HOST = _env.get("DB_HOST", "localhost")
DB_USER = _env.get("DB_USER", "root")
DB_PASSWORD = _env.get("DB_PASSWORD", "")
DB_NAME = _env.get("DB_NAME", "cryptorisk")
API_BASE_URL = _env.get("API_BASE_URL", "https://api.coingecko.com/api/v3")
API_KEY = _env.get("API_KEY", "")
```

This reads `.env` with plain Python rather than a library like `python-dotenv` — that library isn't on the PRD's allowed-libraries list, so this avoids adding an unapproved dependency. No extra `pip install` needed for this step.

---

## Step 5 — Create the database + tables

`schema.sql` contains `CREATE DATABASE cryptorisk;` and `USE cryptorisk;` at the top, so don't create the database separately first — just run it:

```bash
mysql -u root -p < db/schema.sql
```

Verify:

```bash
mysql -u root -p
```
```sql
SHOW DATABASES;
USE cryptorisk;
SHOW TABLES;
DESCRIBE users;
DESCRIBE portfolio;
DESCRIBE transactions;
```

You should see all three tables. `userid` and `transid` should show as plain `INT` (primary key) — **no `AUTO_INCREMENT`**, per the locked decision in `INTERFACES.md`; IDs are generated manually in Python via `SELECT MAX(...)+1`.

---

## Step 6 — Smoke-test the Python ↔ MySQL connection

Standalone check, not part of the app itself:

```python
import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

db = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
cur = db.cursor()
cur.execute("SHOW TABLES")
print(cur.fetchall())
db.close()
```

Should print `[('portfolio',), ('transactions',), ('users',)]`. If this fails, see Troubleshooting below.

---

## Step 7 — Run the app

Once `frontend/` and `app.py` exist:

```bash
streamlit run app.py
```

---

## Troubleshooting

| Error | Likely cause / fix |
|---|---|
| `Access denied for user 'root'@'localhost'` | Wrong password in `.env`, or MySQL is set to `auth_socket` instead of password auth. Fix from an admin session: `ALTER USER 'root'@'localhost' IDENTIFIED BY 'yourpassword';` |
| `Can't connect to MySQL server on 'localhost'` | The MySQL service isn't running — start it (Services app on Windows, `brew services start mysql` on Mac, `sudo systemctl start mysql` on Linux, or open the XAMPP/WAMP control panel and start MySQL). |
| `ModuleNotFoundError: No module named 'mysql'` | `mysql-connector-python` isn't installed in the Python/venv you're actually running — activate your venv, then re-run `pip install -r requirements.txt`. |
| `1049 (42000): Unknown database 'cryptorisk'` | `schema.sql` didn't run cleanly — re-run `mysql -u root -p < db/schema.sql` and read the terminal output for the actual error. |
| Port 3306 already in use | Two MySQL instances are both trying to bind it (e.g. a standalone install and XAMPP's bundled one both running) — stop one of them. |

---

## Reminders

- Each teammate's MySQL server and data are **local and independent** — there's no shared server for this project.
- If `schema.sql` ever changes, everyone re-runs Step 5 against their own local server.
- `INTERFACES.md` is still the source of truth for every function signature — this file only covers environment setup, not code.
