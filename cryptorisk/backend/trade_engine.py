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

import math
from datetime import date

from backend.price_engine import SUPPORTED_COINS, get_boosted_price

from db.connection import get_connection
from db.users_db import get_user_by_id, update_balance
from db.portfolio_db import get_portfolio, upsert_holding
from db.transactions_db import insert_transaction


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
    # Reject non-numeric quantities (str, None, ...) and non-finite ones (NaN, inf)
    # before any comparison — NaN in particular compares False to everything
    # (NaN <= 0, cost > balance, etc.), so it would otherwise slip past every
    # check below and corrupt the balance/holding with NaN.
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not math.isfinite(quantity):
        return _fail("Quantity must be a valid number")
    if quantity <= 0:
        return _fail("Quantity must be greater than 0")

    # --- Price check BEFORE any money math (locked ordering) ---
    # If CoinGecko is down there's no price to trade against, so we stop here
    # rather than validating a balance against a missing number.
    snapshot = get_boosted_price(coin)
    if snapshot is None:
        return _fail("Price temporarily unavailable — try again in a moment")
    price = snapshot["boosted_price"]        # trade executes at the boosted price
    # Defense in depth: price_engine floors the boosted change so this should never
    # happen, but never trade against a non-positive price — a negative price would
    # make cost negative and let a BUY ADD cash instead of spending it.
    if price <= 0:
        return _fail("Price temporarily unavailable — try again in a moment")

    # --- Open the trade's ONE connection and lock the user's row ---
    # Everything below — the balance read, the holding read, and the three
    # writes — runs on this single connection as one transaction. The balance
    # is read with FOR UPDATE, which locks this user's row until commit(): a
    # second trade fired at the same instant (double-click, second tab) waits
    # at its own locked read instead of seeing the stale balance, so two trades
    # can never both spend the same money. All writes then commit together at
    # the very end (all-or-nothing): if anything fails mid-trade, rollback
    # discards every uncommitted write. Uses only conn.commit()/conn.rollback()
    # from mysql.connector (the same API every db/ function already uses) — no
    # SQL transaction statements, so the CBSE constraint in the summary holds.
    conn = get_connection()
    if conn is None:
        return _fail("Database error — could not connect")
    try:
        # --- Look up (and lock) the user's current balance ---
        user = get_user_by_id(userid, conn=conn, for_update=True)
        if user is None:
            conn.rollback()
            return _fail("User not found")
        balance = user["balance"]

        # --- Find the user's current holding of THIS coin, if any ---
        holding = None
        for row in get_portfolio(userid, conn=conn):
            if row["coin"] == coin:
                holding = row
                break

        if action == "BUY":
            cost = quantity * price
            if cost > balance:
                conn.rollback()
                return _fail("Insufficient balance")
            # Round cash to whole cents so binary-float dust can't accumulate in
            # the balance over many trades. (Coin QUANTITIES stay full precision;
            # only the dollars-and-cents cash figure is snapped.)
            new_balance = round(balance - cost, 2)
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
                conn.rollback()
                return _fail("Insufficient quantity owned")
            new_balance = round(balance + (quantity * price), 2)   # selling adds cash (cents)
            new_qty = owned - quantity           # could be 0 (full sell-out)
            # Floating-point subtraction can leave microscopic dust (e.g. 5e-17)
            # instead of a clean 0, which would leave a phantom near-zero holding.
            # Snap that to 0 so upsert_holding() deletes the row on a full sell.
            if new_qty < 1e-9:
                new_qty = 0.0
            new_avg_price = holding["buy_price"] # average is unchanged on a sell

        # --- The three writes, committed together ---
        # 1) new cash balance
        if not update_balance(userid, new_balance, conn=conn):
            conn.rollback()
            return _fail("Database error while updating balance")
        # 2) new holding. upsert_holding() deletes the row itself if new_qty <= 0,
        #    so a full sell-out needs no separate delete call from us.
        if not upsert_holding(userid, coin, new_qty, new_avg_price, conn=conn):
            conn.rollback()
            return _fail("Database error while updating portfolio")
        # 3) transaction log entry (trade_date is a real date object — MySQL
        #    stores it as a native DATE, no string formatting needed).
        if insert_transaction(userid, coin, action, quantity, price, date.today(), conn=conn) is None:
            conn.rollback()
            return _fail("Database error while recording transaction")
        conn.commit()
    except Exception as e:
        print("execute_trade transaction failed:", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return _fail("Database error during trade")
    finally:
        conn.close()

    return {
        "success": True,
        "message": f"{action} {quantity} {coin} at ${price:,.4f}",
        "executed_price": price,
        "new_balance": new_balance,
    }


# ---------------------------------------------------------------------------
# Standalone smoke test. Run with:  python -m backend.trade_engine
# Runs against the real MySQL database (needs a user with userid 1).
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

    from db.transactions_db import get_transaction_history
    print("\nHistory:")
    for t in get_transaction_history(1):
        print(" ", t)
