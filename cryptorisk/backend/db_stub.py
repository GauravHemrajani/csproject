"""
db_stub.py — TEMPORARY in-memory stand-in for Member 2's db/ package
====================================================================

WHY THIS EXISTS
    Member 1 (backend) needs the database functions to build and test
    trade_engine.py, but Member 2 hasn't delivered the real db/ package yet.
    So this file provides fake, in-memory versions of every db/ function that
    match INTERFACES.md exactly. trade_engine.py imports the real db/ first
    and only falls back to this file when db/ doesn't exist.

WHY IT LIVES IN backend/ (not db/)
    db/ is Member 2's folder. Putting stub files there would collide with
    their real code in git. Keeping the stub in backend/ (Member 1's folder)
    keeps the two people's work cleanly separated.

WHEN TO DELETE IT
    Once Member 2's real db/ package is merged and working, delete this file.
    trade_engine.py needs NO changes — its import automatically switches to
    the real db/ functions.

The "tables" below are just Python dicts/lists held in memory. They reset
every time the program restarts (unlike the real MySQL database).

INTERFACE NOTE FOR THE TEAM
    INTERFACES.md gives execute_trade() a userid, but the only balance-reader,
    get_user(username), takes a username. The backend therefore needs
    get_user_by_id(userid). It's implemented below and flagged for Member 2 /
    the team lead to add to the real db/users_db.py.
"""

from datetime import date

# --- Fake "tables", pre-seeded with one test user so smoke tests can run ---
_users = {
    1: {"userid": 1, "username": "testuser", "password": "test123", "balance": 10000.0},
}
_portfolio = {}     # (userid, coin) -> {"quantity": float, "buy_price": float}
_transactions = []  # list of transaction dicts


def create_user(username, password):
    """Add a new user (starting balance $10,000). Rejects duplicate usernames."""
    for user in _users.values():
        if user["username"] == username:
            return {"success": False, "userid": None, "message": "Username already exists"}
    # Manual ID generation (mirrors the real SELECT MAX(userid)+1 approach).
    new_id = max(_users.keys(), default=0) + 1
    _users[new_id] = {
        "userid": new_id, "username": username, "password": password, "balance": 10000.0,
    }
    return {"success": True, "userid": new_id, "message": "Account created"}


def get_user(username):
    """Look a user up by USERNAME (this is also the login function). None if not found."""
    for user in _users.values():
        if user["username"] == username:
            return dict(user)                # copy so callers can't mutate our store
    return None


def get_user_by_id(userid):
    """Look a user up by ID. PROPOSED ADDITION to INTERFACES.md (see header)."""
    user = _users.get(userid)
    return dict(user) if user else None


def update_balance(userid, new_balance):
    """Overwrite a user's balance with an absolute value. True on success."""
    if userid not in _users:
        return False
    _users[userid]["balance"] = new_balance
    return True


def get_portfolio(userid):
    """All of a user's holdings as a list of dicts. [] if they hold nothing."""
    holdings = []
    for (uid, coin), row in _portfolio.items():
        if uid == userid:
            holdings.append({
                "coin": coin, "quantity": row["quantity"], "buy_price": row["buy_price"],
            })
    return holdings


def upsert_holding(userid, coin, quantity, buy_price):
    """
    Insert or update one holding. `quantity` is the NEW TOTAL after the trade.
    If quantity <= 0 (a full sell-out) the row is DELETED rather than kept at
    zero — so the backend never needs a separate delete call.
    """
    if userid not in _users:
        return False
    if quantity <= 0:
        _portfolio.pop((userid, coin), None)     # full sell removes the row
    else:
        _portfolio[(userid, coin)] = {"quantity": quantity, "buy_price": buy_price}
    return True


def insert_transaction(userid, coin, action, quantity, price, trade_date):
    """Log one BUY/SELL. Returns the new transaction id, or None on failure."""
    if userid not in _users:
        return None
    transid = len(_transactions) + 1         # manual id (real code uses MAX+1)
    _transactions.append({
        "transid": transid, "userid": userid, "coin": coin, "action": action,
        "quantity": quantity, "price": price, "trade_date": trade_date,
    })
    return transid


def get_transaction_history(userid):
    """A user's trades, newest first. [] if none. (userid is dropped from each row.)"""
    rows = [dict(t) for t in _transactions if t["userid"] == userid]
    # Newest first; transid breaks ties between same-day trades.
    rows.sort(key=lambda t: (t["trade_date"], t["transid"]), reverse=True)
    for row in rows:
        del row["userid"]                    # match the INTERFACES.md return shape
    return rows


# ---------------------------------------------------------------------------
# Standalone smoke test. Run with:  python -m backend.db_stub
# Proves each fake table behaves like the real database will.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("create:", create_user("alice", "pw"))
    print("duplicate:", create_user("alice", "pw"))
    print("get_user:", get_user("testuser"))
    print("update_balance:", update_balance(1, 9500.0), get_user_by_id(1))
    print("upsert:", upsert_holding(1, "BTC", 0.5, 40000.0), get_portfolio(1))
    print("full sell deletes:", upsert_holding(1, "BTC", 0, 40000.0), get_portfolio(1))
    print("transaction:", insert_transaction(1, "BTC", "BUY", 0.5, 40000.0, date.today()))
    print("history:", get_transaction_history(1))
