"""
trade_engine.py — buy/sell validation + orchestration (Member 1)
================================================================

This is the "cashier" of the app. execute_trade() takes a requested buy or
sell, validates it, and (if valid) updates three things in the database:
the user's cash balance, their coin holdings, and the transaction log.

KEY RULE (locked): trades ALWAYS execute at the BOOSTED (simulated) price
from price_engine.get_boosted_price(), never the real CoinGecko price.

All signatures here are locked in INTERFACES.md.
"""

from datetime import date

from backend.price_engine import SUPPORTED_COINS, get_boosted_price

# ---------------------------------------------------------------------------
# Database imports.
# We try to import Member 2's real db/ package first. Until they've delivered
# it, that import fails and we fall back to the in-memory stubs in db_stub.py.
# Because both expose the SAME function names, nothing below this block has to
# change when the real database arrives — the import just switches over.
#
# NOTE: get_user_by_id(userid) is a small addition we need from Member 2.
# INTERFACES.md only has get_user(username), but execute_trade() is given a
# userid, so we need to look a user up by id. Flagged for the team.
# ---------------------------------------------------------------------------
try:
    from db.users_db import get_user_by_id, update_balance
    from db.portfolio_db import get_portfolio, upsert_holding
    from db.transactions_db import insert_transaction
except ImportError:
    from backend.db_stub import (
        get_user_by_id,
        update_balance,
        get_portfolio,
        upsert_holding,
        insert_transaction,
    )


def calculate_weighted_avg_buy_price(existing_qty, existing_avg_price, new_qty, new_price):
    """
    When a user buys MORE of a coin they already hold, the stored average buy
    price has to be recalculated as a weighted average of the old and new
    purchases. Example: hold 1 BTC bought at $100, buy 1 more at $200 ->
    new average is $150.
    """
    total_cost = (existing_qty * existing_avg_price) + (new_qty * new_price)
    return total_cost / (existing_qty + new_qty)


def _fail(message):
    """Helper: build the standard 'trade rejected' return dict."""
    return {"success": False, "message": message, "executed_price": None, "new_balance": None}


def execute_trade(userid, coin, action, quantity):
    """
    Validate and execute a BUY or SELL, then write the result to the database.

    Return shape (locked):
        {"success": bool, "message": str,
         "executed_price": float | None, "new_balance": float | None}
    """
    # --- Cheap input checks first ---
    if action not in ("BUY", "SELL"):
        return _fail("Invalid action — must be BUY or SELL")
    if coin not in SUPPORTED_COINS:
        return _fail("Invalid coin")
    if quantity <= 0:
        return _fail("Quantity must be greater than 0")

    # --- Price check BEFORE any money math (locked ordering) ---
    # If CoinGecko is down there's no price to trade against, so we stop here
    # rather than validating a balance against a missing number.
    snapshot = get_boosted_price(coin)
    if snapshot is None:
        return _fail("Price temporarily unavailable — try again in a moment")
    price = snapshot["boosted_price"]        # trade executes at the boosted price

    # --- Look up the user's current balance ---
    user = get_user_by_id(userid)
    if user is None:
        return _fail("User not found")
    balance = user["balance"]

    # --- Find the user's current holding of THIS coin, if any ---
    holding = None
    for row in get_portfolio(userid):
        if row["coin"] == coin:
            holding = row
            break

    if action == "BUY":
        cost = quantity * price
        if cost > balance:
            return _fail("Insufficient balance")
        new_balance = balance - cost
        # New holding total + recalculated average buy price.
        if holding is None:
            new_qty = quantity               # first time buying this coin
            new_avg_price = price
        else:
            new_qty = holding["quantity"] + quantity
            new_avg_price = calculate_weighted_avg_buy_price(
                holding["quantity"], holding["buy_price"], quantity, price
            )
    else:  # SELL
        owned = holding["quantity"] if holding else 0.0
        if quantity > owned:
            return _fail("Insufficient quantity owned")
        new_balance = balance + (quantity * price)   # selling adds cash
        new_qty = owned - quantity           # could be 0 (full sell-out)
        # Floating-point subtraction can leave microscopic dust (e.g. 5e-17)
        # instead of a clean 0, which would leave a phantom near-zero holding.
        # Snap that to 0 so upsert_holding() deletes the row on a full sell.
        if new_qty < 1e-9:
            new_qty = 0.0
        new_avg_price = holding["buy_price"] # average is unchanged on a sell

    # --- Commit the three database writes ---
    # 1) new cash balance
    if not update_balance(userid, new_balance):
        return _fail("Database error while updating balance")
    # 2) new holding. upsert_holding() deletes the row itself if new_qty <= 0,
    #    so a full sell-out needs no separate delete call from us.
    if not upsert_holding(userid, coin, new_qty, new_avg_price):
        return _fail("Database error while updating portfolio")
    # 3) transaction log entry (trade_date is a real date object — MySQL
    #    stores it as a native DATE, no string formatting needed).
    if insert_transaction(userid, coin, action, quantity, price, date.today()) is None:
        return _fail("Database error while recording transaction")

    return {
        "success": True,
        "message": f"{action} {quantity} {coin} at ${price:,.4f}",
        "executed_price": price,
        "new_balance": new_balance,
    }


# ---------------------------------------------------------------------------
# Standalone smoke test. Run with:  python -m backend.trade_engine
# Runs against the in-memory stub database (test user: userid 1, $10,000).
# Exercises every rejection case plus a full buy/buy/sell cycle.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Invalid action:", execute_trade(1, "BTC", "HOLD", 1))
    print("Invalid coin:", execute_trade(1, "XRP", "BUY", 1))
    print("Zero qty:", execute_trade(1, "BTC", "BUY", 0))
    print("Oversized buy:", execute_trade(1, "BTC", "BUY", 9999))
    print("Sell nothing owned:", execute_trade(1, "ETH", "SELL", 1))

    print("\nBuy 0.05 BTC:", execute_trade(1, "BTC", "BUY", 0.05))
    print("Buy 0.05 more:", execute_trade(1, "BTC", "BUY", 0.05))
    print("Portfolio:", get_portfolio(1))
    print("\nSell 0.10 BTC (full):", execute_trade(1, "BTC", "SELL", 0.10))
    print("Portfolio after full sell:", get_portfolio(1))

    from backend.db_stub import get_transaction_history
    print("\nHistory:")
    for t in get_transaction_history(1):
        print(" ", t)
