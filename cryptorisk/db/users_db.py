from db.connection import get_connection


def create_user(username, password):
    conn = get_connection()

    if conn is None:
        return {"success": False, "userid": None, "message": "Database connection failed"}

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT userid FROM users WHERE username = %s",
            (username,)
        )

        if cur.fetchone():
            return {"success": False, "userid": None, "message": "Username already exists"}

        cur.execute(
            "SELECT COALESCE(MAX(userid), 0) + 1 AS next_id FROM users"
        )
        userid = cur.fetchone()["next_id"]

        starting_balance = 10000.0

        cur.execute(
            """
            INSERT INTO users(userid, username, password, balance)
            VALUES(%s, %s, %s, %s)
            """,
            (userid, username, password, starting_balance)
        )

        conn.commit()

        return {"success": True, "userid": userid, "message": "User created successfully"}

    except Exception as e:
        print("create_user failed:", e)
        return {"success": False, "userid": None, "message": "Database error"}

    finally:
        if cur:
            cur.close()
        conn.close()


def get_user(username):
    conn = get_connection()

    if conn is None:
        return None

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT userid, username, password, balance FROM users WHERE username = %s",
            (username,)
        )

        row = cur.fetchone()

        if row is None:
            return None

        row["balance"] = float(row["balance"])

        return row

    except Exception as e:
        print("get_user failed:", e)
        return None

    finally:
        if cur:
            cur.close()
        conn.close()


def get_user_by_id(userid, conn=None, for_update=False):
    # When the caller passes `conn`, this read joins the caller's transaction:
    # no close here — the caller commits (or rolls back) and closes. With
    # for_update=True the SELECT locks the user's row until that commit, so a
    # concurrent trade for the same user waits here instead of reading a stale
    # balance. Called standalone (conn=None, for_update=False), behavior is
    # unchanged.
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    if conn is None:
        return None

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        query = "SELECT userid, username, password, balance FROM users WHERE userid = %s"
        if for_update:
            query += " FOR UPDATE"

        cur.execute(query, (userid,))

        row = cur.fetchone()

        if row is None:
            return None

        row["balance"] = float(row["balance"])

        return row

    except Exception as e:
        print("get_user_by_id failed:", e)
        return None

    finally:
        if cur:
            cur.close()
        if owns_conn:
            conn.close()


def update_balance(userid, new_balance, conn=None):
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

        cur.execute(
            "UPDATE users SET balance = %s WHERE userid = %s",
            (new_balance, userid)
        )

        if cur.rowcount == 0:
            return False

        if owns_conn:
            conn.commit()

        return True

    except Exception as e:
        print("update_balance failed:", e)
        return False

    finally:
        if cur:
            cur.close()
        if owns_conn:
            conn.close()


def get_users_with_balance_between(low, high):
    conn = get_connection()

    if conn is None:
        return []

    cur = None
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT userid, username, balance
            FROM users
            WHERE balance BETWEEN %s AND %s
            ORDER BY balance DESC
            """,
            (low, high)
        )

        rows = cur.fetchall()

        for row in rows:
            row["balance"] = float(row["balance"])

        return rows

    except Exception as e:
        print("get_users_with_balance_between failed:", e)
        return []

    finally:
        if cur:
            cur.close()
        conn.close()