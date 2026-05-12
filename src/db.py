"""
db.py - Database setup and utilities.
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
            DROP FUNCTION IF EXISTS join_annotations(jsonb, jsonb);
            DROP FUNCTION IF EXISTS annotate(BIGINT, BOOLEAN);
        """)

    # Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            alive       BOOLEAN NOT NULL DEFAULT true
        );
        CREATE TABLE IF NOT EXISTS memberships (
            id          SERIAL PRIMARY KEY,
            email       TEXT NOT NULL,
            role        TEXT NOT NULL,
            alive       BOOLEAN NOT NULL DEFAULT true
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id          BIGSERIAL PRIMARY KEY,
            ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
            db_user     TEXT NOT NULL,
            action      TEXT NOT NULL,
            table_name  TEXT NOT NULL,
            row_id      INTEGER NOT NULL,
            query       TEXT
        );
    """)

    # Create indexes
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS people_email_active_uq
            ON people (email)
            WHERE alive = true;

        CREATE UNIQUE INDEX IF NOT EXISTS memberships_active_uq
            ON memberships (email, role)
            WHERE alive = true;
    """)

    # Create audit trigger
    cur.execute("""
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
    """)

    # Init permissions
    cur.execute("""
        GRANT SELECT, INSERT, UPDATE, DELETE ON people      TO audit_tracker;
        GRANT SELECT, INSERT, UPDATE, DELETE ON memberships TO audit_tracker;
        GRANT INSERT                          ON audit_log   TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE people_id_seq       TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE memberships_id_seq  TO audit_tracker;
        GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq    TO audit_tracker;
    """)

    # Create custom annotation functions
    cur.execute("""     
        CREATE OR REPLACE FUNCTION annotate(id BIGINT, alive BOOLEAN) RETURNS jsonb AS $$
            SELECT CASE
                WHEN id IS NULL AND alive           THEN jsonb_build_array(0, 9223372036854775807::bigint)
                WHEN id IS NULL                     THEN jsonb_build_array(0)
                WHEN alive                          THEN jsonb_build_array(id, 9223372036854775807::bigint)
                ELSE                                    jsonb_build_array(id)
            END;
        $$ LANGUAGE sql;
        
        -- Annotation +: Simple concatenation of annotation arrays
        CREATE OR REPLACE FUNCTION annotations_union_trans(state jsonb, val jsonb) RETURNS jsonb AS $$
            SELECT state || val;
        $$ LANGUAGE sql;
        
        -- Annotation +: Final function to remove duplicates and sort inner arrays
        CREATE OR REPLACE FUNCTION annotations_union_final(state jsonb) RETURNS jsonb AS $$
            SELECT jsonb_agg(DISTINCT sorted_elem ORDER BY sorted_elem ASC)
            FROM (
                SELECT (SELECT jsonb_agg(n ORDER BY n::numeric) 
                        FROM jsonb_array_elements(elem) AS n) AS sorted_elem
                FROM jsonb_array_elements(state) AS elem
            ) s;
        $$ LANGUAGE sql;
        
        -- Annotation +: Final function to remove duplicates and sort inner arrays, keeping only the those with a MAXVALUE
        CREATE OR REPLACE FUNCTION annotations_union_final_min(state jsonb) RETURNS jsonb AS $$
            SELECT jsonb_agg(DISTINCT sorted_elem)
            FROM (
                SELECT (SELECT jsonb_agg(n ORDER BY n::numeric) 
                        FROM jsonb_array_elements(elem) AS n) AS sorted_elem
                FROM jsonb_array_elements(state) AS elem
                WHERE elem @> to_jsonb(9223372036854775807::bigint)
            ) s;
        $$ LANGUAGE sql;
        
        -- Annotation +: Custom aggregate
        CREATE OR REPLACE AGGREGATE add_annotations(jsonb) (
            SFUNC = annotations_union_trans,
            STYPE = jsonb,
            FINLFUNC = annotations_union_final,
            INITCOND = '[]'
        );

        -- Annotation +: Custom aggregate that keeps only elements with MAXVALUE 
        CREATE OR REPLACE AGGREGATE add_annotations_min(jsonb) (
            SFUNC = annotations_union_trans,
            STYPE = jsonb,
            FINLFUNC = annotations_union_final_min,
            INITCOND = '[]'
        );

        -- ANNOTATION *: Custom function to combine annotations from joins, filtering out elements greater than least upper bound, may contain duplicates?
        CREATE OR REPLACE FUNCTION join_annotations(a jsonb, b jsonb) RETURNS jsonb AS $$
            SELECT jsonb_agg(DISTINCT filtered_elem)
            FROM (
                SELECT (
                    SELECT jsonb_agg(DISTINCT n ORDER BY n)
                    FROM jsonb_array_elements(elems_a || elems_b) AS n
                    WHERE (n::numeric) <= LEAST(
                        (SELECT max(e::numeric) FROM jsonb_array_elements(elems_a) AS e),
                        (SELECT max(e::numeric) FROM jsonb_array_elements(elems_b) AS e)
                    )
                ) AS filtered_elem
                FROM jsonb_array_elements(a) AS elems_a, -- pairs every element from the 2 tables
                    jsonb_array_elements(b) AS elems_b
            ) s;
        $$ LANGUAGE sql;        
    """)
    cur.close()


def insert(conn, table, data):
    """
    Insert a new row into table. data is a dict of column->value.
    """
    cur = conn.cursor()
    columns = data.keys()
    values = list(data.values())
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING RETURNING id").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() * len(values))
    )

    cur.execute(query, values)
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None


def update(conn, table, row_id, data):
    """
    Soft-update: deprecate the old row, insert a new one with updated values.
    Returns the new row id, or None if the row doesn't exist or is already deprecated.
    """
    cur = conn.cursor()
    cur.execute(
        sql.SQL("SELECT * FROM {} WHERE id = %s AND alive = true").format(
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
        sql.SQL("UPDATE {} SET alive = false WHERE id = %s").format(
            sql.Identifier(table)
        ),
        [row_id]
    )

    new_data = {k: v for k, v in current.items() if k not in ("id",
                                                              "alive")}
    new_data.update(data)
    res = insert(conn, table, new_data)
    cur.close()
    return res


def delete(conn, table, row_id):
    """
    Soft-delete: just set 'alive' = false.
    """
    cur = conn.cursor()
    cur.execute(
        sql.SQL("UPDATE {} SET alive = false WHERE id = %s").format(
            sql.Identifier(table)),
        [row_id]
    )
    res = cur.rowcount > 0
    cur.close()
    return res


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


def get_table_columns(conn, table_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    columns = [row[0] for row in cur.fetchall()]
    cur.close()
    return columns

def get_table_columns_no_annotation(conn, table_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
            AND column_name != 'annotation'
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    columns = [row[0] for row in cur.fetchall()]
    cur.close()
    return columns

def get_table_columns_no_id(conn, table_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
            AND column_name != 'id'
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    columns = [row[0] for row in cur.fetchall()]
    cur.close()
    return columns

def get_table_columns_no_id_annotation(conn, table_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
            AND column_name != 'id' 
            AND column_name != 'annotation'
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    columns = [row[0] for row in cur.fetchall()]
    cur.close()
    return columns