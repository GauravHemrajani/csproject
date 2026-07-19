from db.connection import get_connection


def insert_transaction(userid, coin, action, quantity, price, trade_date, conn=None):
    # When the caller passes `conn`, this write joins the caller's transaction:
    # no commit and no close here — the caller commits (or rolls back) all its
    # writes together. Called standalone (conn=None), behavior is unchanged.
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    if conn is None:
        return None

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT COALESCE(MAX(transid), 0) + 1 AS next_id FROM transactions"
        )
        transid = cur.fetchone()["next_id"]

        cur.execute(
            """
            INSERT INTO transactions
                (transid, userid, coin, action, quantity, price, trade_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (transid, userid, coin, action, quantity, price, trade_date)
        )

        if owns_conn:
            conn.commit()

        return transid

    except Exception as e:
        print("insert_transaction failed:", e)
        return None

    finally:
        if cur:
            cur.close()
        if owns_conn:
            conn.close()


def get_transaction_history(userid):
    conn = get_connection()

    if conn is None:
        return []

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT transid, coin, action, quantity, price, trade_date
            FROM transactions
            WHERE userid = %s
            ORDER BY trade_date DESC, transid DESC
            """,
            (userid,)
        )

        rows = cur.fetchall()

        for row in rows:
            row["quantity"] = float(row["quantity"])
            row["price"] = float(row["price"])

        return rows

    except Exception as e:
        print("get_transaction_history failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        conn.close()


def get_distinct_coins_traded():
    conn = get_connection()

    if conn is None:
        return []

    cur = None
    try:
        cur = conn.cursor()

        cur.execute("SELECT DISTINCT coin FROM transactions")

        return [row[0] for row in cur.fetchall()]

    except Exception as e:
        print("get_distinct_coins_traded failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        conn.close()


def get_transactions_by_actions(actions):
    conn = get_connection()

    if conn is None:
        return []

    if not actions:
        return []

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        placeholders = ", ".join(["%s"] * len(actions))
        cur.execute(
            f"""
            SELECT transid, userid, coin, action, quantity, price, trade_date
            FROM transactions
            WHERE action IN ({placeholders})
            ORDER BY trade_date DESC
            """,
            tuple(actions)
        )

        rows = cur.fetchall()

        for row in rows:
            row["quantity"] = float(row["quantity"])
            row["price"] = float(row["price"])

        return rows

    except Exception as e:
        print("get_transactions_by_actions failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        conn.close()


def search_coins_by_name(pattern):
    conn = get_connection()

    if conn is None:
        return []

    cur = None
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT DISTINCT coin FROM transactions WHERE coin LIKE %s",
            (pattern,)
        )

        return [row[0] for row in cur.fetchall()]

    except Exception as e:
        print("search_coins_by_name failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        conn.close()


def get_active_traders(min_trades=3):
    conn = get_connection()

    if conn is None:
        return []

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT u.userid AS userid,
                   u.username AS username,
                   COUNT(t.transid) AS trade_count
            FROM users u
            JOIN transactions t ON u.userid = t.userid
            GROUP BY u.userid, u.username
            HAVING COUNT(t.transid) >= %s
            ORDER BY trade_count DESC
            """,
            (min_trades,)
        )

        return cur.fetchall()

    except Exception as e:
        print("get_active_traders failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        conn.close()