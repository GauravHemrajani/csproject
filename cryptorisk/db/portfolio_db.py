from db.connection import get_connection


def get_portfolio(userid, conn=None):
    # When the caller passes `conn`, this read joins the caller's transaction
    # (no close here — the caller commits/rolls back and closes), so a trade
    # reads holdings on the same connection that holds the user-row lock.
    # Called standalone (conn=None), behavior is unchanged.
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    if conn is None:
        return []

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT coin, quantity, buy_price FROM portfolio WHERE userid = %s",
            (userid,)
        )

        rows = cur.fetchall()

        for row in rows:
            row["quantity"] = float(row["quantity"])
            row["buy_price"] = float(row["buy_price"])

        return rows

    except Exception as e:
        print("get_portfolio failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        if owns_conn:
            conn.close()


def upsert_holding(userid, coin, quantity, buy_price, conn=None):
    # When the caller passes `conn`, this write joins the caller's transaction:
    # no commit and no close here — the caller commits (or rolls back) all its
    # writes together. Called standalone (conn=None), behavior is unchanged.
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    if conn is None:
        return False

    cur = None
    try:
        cur = conn.cursor()

        if quantity <= 0:
            cur.execute(
                "DELETE FROM portfolio WHERE userid = %s AND coin = %s",
                (userid, coin)
            )
        else:
            cur.execute(
                """
                INSERT INTO portfolio (userid, coin, quantity, buy_price)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    quantity = VALUES(quantity),
                    buy_price = VALUES(buy_price)
                """,
                (userid, coin, quantity, buy_price)
            )

        if owns_conn:
            conn.commit()

        return True

    except Exception as e:
        print("upsert_holding failed:", e)
        return False

    finally:
        if cur:
            cur.close()
        if owns_conn:
            conn.close()


def get_total_invested_per_user():
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
                   SUM(p.quantity * p.buy_price) AS total_invested
            FROM users u
            JOIN portfolio p ON u.userid = p.userid
            GROUP BY u.userid, u.username
            ORDER BY total_invested DESC
            """
        )

        rows = cur.fetchall()

        for row in rows:
            row["total_invested"] = float(row["total_invested"])

        return rows

    except Exception as e:
        print("get_total_invested_per_user failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        conn.close()