"""
db.py - Database setup and utilities.

Two tables: people, memberships
Query we blame against:
    SELECT p.name, m.role
    FROM people p
    JOIN memberships m ON p.email = m.email
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
    Create tables and permissions only.
    """
    cur = conn.cursor()
    if reset:
        cur.execute("""
            DROP TABLE IF EXISTS memberships;
            DROP TABLE IF EXISTS people;
            DROP TABLE IF EXISTS audit_log;
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            deprecated  BOOLEAN NOT NULL DEFAULT false
        );
        CREATE TABLE IF NOT EXISTS memberships (
            id          SERIAL PRIMARY KEY,
            email       TEXT NOT NULL,
            role        TEXT NOT NULL,
            active      BOOLEAN NOT NULL DEFAULT true,
            deprecated  BOOLEAN NOT NULL DEFAULT false
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id          SERIAL PRIMARY KEY,
            ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
            db_user     TEXT NOT NULL,
            action      TEXT NOT NULL,
            table_name  TEXT NOT NULL,
            row_id      INTEGER NOT NULL,
            query       TEXT
        );

        CREATE OR REPLACE FUNCTION audit_trigger() RETURNS trigger AS $$
        BEGIN
            INSERT INTO audit_log (db_user, action, table_name, row_id, query)
            VALUES (current_user, TG_OP, TG_TABLE_NAME, NEW.id, current_query());
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE OR REPLACE TRIGGER people_audit
            AFTER INSERT OR UPDATE ON people
            FOR EACH ROW EXECUTE FUNCTION audit_trigger();

        CREATE OR REPLACE TRIGGER memberships_audit
            AFTER INSERT OR UPDATE ON memberships
            FOR EACH ROW EXECUTE FUNCTION audit_trigger();

        CREATE UNIQUE INDEX IF NOT EXISTS people_email_active_uq
            ON people (email)
            WHERE deprecated = false;

        CREATE UNIQUE INDEX IF NOT EXISTS memberships_active_uq
            ON memberships (email, role, active)
            WHERE deprecated = false;

        GRANT SELECT, INSERT, UPDATE, DELETE ON people      TO audit_tracker;
        GRANT SELECT, INSERT, UPDATE, DELETE ON memberships TO audit_tracker;
        GRANT INSERT                          ON audit_log   TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE people_id_seq       TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE memberships_id_seq  TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq    TO audit_tracker;
    """)
    cur.close()


def insert(cur, table, data):
    """
    Insert a new row into table. data is a dict of column->value.
    """
    columns = data.keys()
    values = list(data.values())
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING RETURNING id").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() * len(values))
    )

    cur.execute(query, values)
    row = cur.fetchone()
    return row[0] if row else None


def update(cur, table, row_id, data):
    """
    Soft-update: deprecate the old row, insert a new one with updated values.
    Returns the new row id, or None if the row doesn't exist or is already deprecated.
    """
    cur.execute(
        sql.SQL("SELECT * FROM {} WHERE id = %s AND deprecated = false").format(
            sql.Identifier(table)
        ),
        [row_id]
    )
    row = cur.fetchone()
    if row is None:
        return None  # row doesn't exist or is already deprecated, nothing to do

    colnames = [desc[0] for desc in cur.description]
    current = dict(zip(colnames, row))

    # Check if the update would actually change anything
    if all(current.get(k) == v for k, v in data.items()):
        return row_id  # nothing changed, return existing id

    cur.execute(
        sql.SQL("UPDATE {} SET deprecated = true WHERE id = %s").format(
            sql.Identifier(table)
        ),
        [row_id]
    )

    new_data = {k: v for k, v in current.items() if k not in ("id",
                                                              "deprecated")}
    new_data.update(data)

    return insert(cur, table, new_data)


def delete(cur, table, row_id):
    """
    Soft-delete: just set deprecated = true.
    """
    cur.execute(
        sql.SQL("UPDATE {} SET deprecated = true WHERE id = %s").format(
            sql.Identifier(table)),
        [row_id]
    )
    return cur.rowcount > 0


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
