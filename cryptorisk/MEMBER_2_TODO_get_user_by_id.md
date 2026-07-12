# TODO for Member 2 — add `get_user_by_id()` to `db/users_db.py`

**From:** Member 1 (Backend)
**Priority:** High — this is an integration blocker for buy/sell.
**Status:** NOT yet in `INTERFACES.md`. Please read this, agree with the team,
then we add it to the locked contract together. (I have deliberately not edited
`INTERFACES.md` myself.)

---

## The problem in one sentence

`execute_trade()` is handed a **`userid`**, but the only user-reading function in
the locked contract is **`get_user(username)`** — which takes a *username*. There
is currently no contract-blessed way for the backend to read a user's balance by
their id, so `execute_trade()` cannot look the user up.

## What I need you to add

A single new function in `db/users_db.py`, right next to `get_user()`. It's the
**exact same query and return shape as `get_user()`**, just keyed on `userid`
instead of `username`.

### Signature (proposed — please confirm so we can lock it in `INTERFACES.md`)

```python
def get_user_by_id(userid: int) -> dict | None:
    """
    Look a user up by their numeric userid.
    Returns None if no user has that id.
    Same return shape as get_user():
        {"userid": int, "username": str, "password": str, "balance": float}
    """
```

### Reference implementation (mirror your existing `get_user()`)

```python
def get_user_by_id(userid):
    conn = get_connection()
    if conn is None:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT userid, username, password, balance FROM users WHERE userid = %s",
            (userid,),
        )
        return cur.fetchone()          # a dict, or None if not found
    except Exception as e:
        print("get_user_by_id failed:", e)   # locked db/ error-logging convention
        return None
    finally:
        conn.close()
```

> Match whatever style your real `get_user()` already uses (cursor type, how you
> close the connection, etc.) — the important part is the **name, the parameter,
> and the return shape**, which must match `get_user()` exactly.

## Why this is safe / low-risk for you

- It's additive — it doesn't change any existing function.
- The backend already works against it today: `backend/db_stub.py` implements
  `get_user_by_id()`, and `trade_engine.py` imports it. The moment your real
  `db/users_db.py` defines it, the `try: from db... except ImportError` switch in
  `trade_engine.py` picks up your version automatically — no backend changes.

## What happens if you DON'T add it

When the real `db/` package is merged and `db_stub.py` is deleted, the import in
`trade_engine.py`:

```python
from db.users_db import get_user_by_id, update_balance
```

will raise `ImportError`, and **every trade will fail** (or silently fall back to
the stub if it hasn't been deleted yet — which is worse, because trades would hit
fake in-memory data instead of the real DB).

## Action items

1. Member 2: add `get_user_by_id()` to `db/users_db.py` as above.
2. Team: agree on the signature and add it to `INTERFACES.md` under the Database
   Layer section (right after `get_user()`), so it becomes part of the locked
   contract.
