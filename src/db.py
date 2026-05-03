"""
db.py - Database setup and utilities.

Two tables: people, memberships
Query we blame against:
    SELECT p.name, m.role
    FROM people p
    JOIN memberships m ON p.id = m.person_id
    WHERE m.active = true

Three blame categories covered:
    Alice  → unattributed (inserted before window T)
    Bob    → positive     (inserted inside window T)
    Carol  → negative     (inserted then deactivated inside window T)
"""

import psycopg2
from psycopg2 import sql


def get_connection(host="localhost", port=5432, dbname="postgres",
                   user="postgres", password="postgres"):
    conn = psycopg2.connect(host=host, port=port, dbname=dbname,
                            user=user, password=password)
    conn.autocommit = True
    return conn


def setup(conn, reset=False):
    """
    Create tables, populate data, return (T_start, T_end) window.
    Alice is inserted before the window. Bob and Carol inside.
    """
    conn.autocommit = True
    cur = conn.cursor()

    if reset:
        cur.execute(
            "DROP TABLE IF EXISTS memberships; DROP TABLE IF EXISTS people;")

    # cur.execute("CREATE ROLE audit_tracker NOLOGIN;")
    # cur.execute("ALTER SYSTEM SET pgaudit.role = 'audit_tracker';")
    # cur.execute("SELECT pg_reload_conf();")

    # conn.autocommit = False  # optional restore
    cur.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL UNIQUE,
            deprecated  BOOLEAN NOT NULL DEFAULT false
        );
        CREATE TABLE IF NOT EXISTS memberships (
            id          SERIAL PRIMARY KEY,
            person_id   INTEGER NOT NULL REFERENCES people(id),
            role        TEXT NOT NULL,
            active      BOOLEAN NOT NULL DEFAULT true,
            deprecated  BOOLEAN NOT NULL DEFAULT false
        );
        GRANT SELECT, INSERT, UPDATE, DELETE ON people      TO audit_tracker;
        GRANT SELECT, INSERT, UPDATE, DELETE ON memberships TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE people_id_seq      TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE memberships_id_seq TO audit_tracker;
    """)

    # Phase 0: before window — unattributed
    cur.execute(
        "INSERT INTO people (name, email) VALUES ('Alice', 'alice@example.com') ON CONFLICT DO NOTHING RETURNING id")
    row = cur.fetchone()
    if row:
        cur.execute(
            "INSERT INTO memberships (person_id, role) VALUES (%s, 'Observer')", (row[0],))

    # Phase 1: positive blame
    cur.execute(
        "INSERT INTO people (name, email) VALUES ('Bob', 'bob@example.com') ON CONFLICT DO NOTHING RETURNING id")
    bob_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO memberships (person_id, role) VALUES (%s, 'Member')", (bob_id,))

    # Phase 2: negative blame — insert then deactivate
    cur.execute(
        "INSERT INTO people (name, email) VALUES ('Carol', 'carol@example.com') ON CONFLICT DO NOTHING RETURNING id")
    carol_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO memberships (person_id, role) VALUES (%s, 'Lead') RETURNING id", (carol_id,))
    carol_m_id = cur.fetchone()[0]
    cur.execute(
        "UPDATE memberships SET active = false WHERE id = %s", (carol_m_id,))


def get_db_overview(conn, limit=5):
    """
    Return schemas, tables, columns, and head(limit) rows for pretty-printing.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        """
    )
    tables = cur.fetchall()

    overview = []
    for schema_name, table_name in tables:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema_name, table_name),
        )
        columns = [row[0] for row in cur.fetchall()]

        # Safe identifier quoting for schema/table names.
        cur.execute(
            sql.SQL("SELECT * FROM {}.{} LIMIT %s").format(
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
            ),
            (limit,),
        )
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]

        overview.append({
            "schema": schema_name,
            "table": table_name,
            "columns": columns,
            "rows": rows,
        })

    cur.close()
    return overview


# def fetch(conn, sql, params=None):
#     """Run a SELECT, return list of dicts."""
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute(sql, params or [])
#     rows = [dict(r) for r in cur.fetchall()]
#     cur.close()
#     return rows


# BLAME_QUERY = """
#     SELECT p.name, m.role
#     FROM people p
#     JOIN memberships m ON p.id = m.person_id
#     WHERE m.active = true
# """


# if __name__ == "__main__":
#     conn = get_connection()
#     T_start, T_end = setup(conn, reset=True)
#     print("Result:", fetch(conn, BLAME_QUERY))
#     print("T_start:", T_start)
#     print("T_end:  ", T_end)
#     conn.close()
