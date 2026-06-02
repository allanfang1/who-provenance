import datetime

from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from src import demo_db
import pandas as pd

TABLES = (
    ("people", "People"),
    ("memberships", "Memberships"),
    ("audit_log_pos", "Birth Log"),
    ("audit_log_neg", "Death Log"),
)


def get_connection():
    return demo_db.get_connection()


def load_table_rows(table_name, limit=200):
    conn = demo_db.get_connection()
    try:
        columns = demo_db.get_table_columns(conn, table_name)
        query = sql.SQL("SELECT * FROM {} ORDER BY id ASC LIMIT %s").format(
            sql.Identifier(table_name)
        )
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

        df = pd.DataFrame(rows)
        if 'death' in df.columns:
            max_dt = datetime.datetime.max
            df['death'] = df['death'].apply(
                lambda e: 'infinity' if e == max_dt.replace(
                    tzinfo=e.tzinfo) else e
            )
            df["death"] = df["death"].astype(str)

    finally:
        conn.close()
    return columns, df


def get_users():
    return ["postgres"] + list(demo_db.DEMO_USERS)


def update_state(time_override, exec_user, sql_text):
    conn = demo_db.get_connection()
    try:
        if time_override.strip():
            demo_db.set_time(conn, time_override.strip())
        cur = conn.cursor()
        demo_db._set_role(cur, exec_user)
        cur.execute(sql_text)
        demo_db._reset_role(cur)
        cur.close()
    finally:
        demo_db.reset_time(conn)
        conn.close()


def reset_demo_state():
    conn = demo_db.get_connection()
    try:
        demo_db.setup(conn, reset=True)
    finally:
        conn.close()
    seed_demo_state()


def seed_demo_state():
    conn = demo_db.get_connection()
    try:

        demo_db.set_time(conn, "2024-01-06 10:00:00Z")
        demo_db.insert(conn, "memberships", {"y": "b1", "z": "e"})

        demo_db.set_time(conn, "2025-01-01 10:00:00Z")
        demo_db.insert(conn, "people", {"x": "a", "y": "b"})

        demo_db.set_time(conn, "2025-01-02 10:00:00Z")
        demo_db.delete(conn, "people", {"x": "a", "y": "b"})

        demo_db.set_time(conn, "2025-01-03 10:00:00Z")
        demo_db.insert(conn, "people", {"x": "a", "y": "b1"})

        demo_db.set_time(conn, "2025-01-04 10:00:00Z")
        demo_db.insert(conn, "memberships", {"y": "b", "z": "c"})

        demo_db.set_time(conn, "2025-01-05 10:00:00Z")
        demo_db.update(conn, "memberships", {"y": "b", "z": "c"}, {"y": "b1"})

        demo_db.set_time(conn, "2025-01-05 10:00:00Z")
        demo_db.insert(conn, "memberships", {"y": "b1", "z": "d"})

        demo_db.set_time(conn, "2025-01-06 10:00:00Z")
        demo_db.delete(conn, "memberships", {"y": "b1", "z": "d"})
    finally:
        demo_db.reset_time(conn)
        conn.close()


def clear_demo_state():
    try:
        conn = demo_db.get_connection()
        demo_db.truncate_tables(conn)
    finally:
        demo_db.reset_time(conn)
        conn.close()


def insert_action(table, values, exec_user, time_override=None):
    dt = pd.to_datetime(time_override.strip(), errors="coerce", utc=True)

    if pd.notna(dt):
        demo_db.set_time(get_connection(), dt.strftime("%Y-%m-%d %H:%M:%SZ"))

    try:
        conn = demo_db.get_connection()
        demo_db.insert(conn, table, values, as_user=exec_user)
    finally:
        if pd.notna(dt):
            demo_db.reset_time(conn)
        conn.close()


def delete_action(table, values, exec_user, time_override=None):
    dt = pd.to_datetime(time_override.strip(), errors="coerce", utc=True)

    if pd.notna(dt):
        demo_db.set_time(get_connection(), dt.strftime("%Y-%m-%d %H:%M:%SZ"))

    try:
        conn = demo_db.get_connection()
        demo_db.delete(conn, table, values, as_user=exec_user)
    finally:
        if pd.notna(dt):
            demo_db.reset_time(conn)
        conn.close()


def update_action(table, old_values, new_values, exec_user, time_override=None):
    dt = pd.to_datetime(time_override.strip(), errors="coerce", utc=True)

    if pd.notna(dt):
        demo_db.set_time(get_connection(), dt.strftime("%Y-%m-%d %H:%M:%SZ"))

    try:
        conn = demo_db.get_connection()
        demo_db.update(conn, table, old_values, new_values, as_user=exec_user)
    finally:
        if pd.notna(dt):
            demo_db.reset_time(conn)
        conn.close()
