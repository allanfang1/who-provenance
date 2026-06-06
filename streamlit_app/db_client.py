import datetime

from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from src import demo_db
import pandas as pd
from src.ast_rewriter import rewrite_sql

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
        demo_db.insert(conn, "people", {"x": "a", "y": "b"}, as_user="miika")

        demo_db.set_time(conn, "2025-01-02 10:00:00Z")
        demo_db.insert(conn, "memberships", {
                       "y": "b", "z": "c"}, as_user="miika")

        demo_db.set_time(conn, "2025-01-03 10:00:00Z")
        demo_db.delete(conn, "people", {"x": "a", "y": "b"})

        demo_db.set_time(conn, "2025-01-04 10:00:00Z")
        demo_db.insert(conn, "people", {"x": "a", "y": "b1"})

        demo_db.set_time(conn, "2025-01-05 10:00:00Z")
        demo_db.update(conn, "memberships", {"y": "b", "z": "c"}, {
                       "y": "b1"}, as_user="riccardo")

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


def submit_query(schema, sql_text, window_start, window_end=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")):
    conn = demo_db.get_connection()
    try:
        rewritten_query = rewrite_sql(
            sql_text, window_start=window_start, window_end=window_end, schema=schema)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(rewritten_query)
        rows = cur.fetchall()

        df = pd.DataFrame(rows)

        # print(rows)
    finally:
        conn.close()
    return preprocessing(df)


def preprocessing(df):
    def expand(annotation):
        result = []
        for exp in annotation:
            exp_result = []
            for i, frame in enumerate(exp):
                exp_result.append({
                    "pos_neg": "pos",
                    "start": frame.get("interval")[0],
                    "end": frame.get("interval")[1],
                    "blame": frame.get("birth")
                })
                if frame.get("interval")[1] != 'infinity':
                    exp_result.append({
                        "pos_neg": "neg",
                        "start": frame.get("interval")[1],
                        "end": exp[i + 1].get("interval")[0] if i + 1 < len(exp) else 'infinity',
                        "blame": frame.get("death")
                    })
            result.append(exp_result)
        return result

    df = df[df['annotation'].apply(len) > 0]

    df['tmp_alive'] = df['annotation'].apply(
        lambda ann: any(
            lineage[-1]['interval'][1] == 'infinity'
            for lineage in ann
        )
    )

    df['tmp_annotation'] = df['annotation'].apply(expand)

    df = df.drop(columns=["annotation"])

    return df
