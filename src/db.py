"""
db.py - Database setup and utilities.
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


def get_connection(host="localhost", port=5432, dbname="postgres",
                   user="postgres", password="postgres"):
    conn = psycopg2.connect(host=host, port=port, dbname=dbname,
                            user=user, password=password)
    conn.autocommit = True
    return conn


def truncate_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        TRUNCATE people, memberships, audit_log_pos, audit_log_neg;
    """)


def setup(conn, reset=False):
    """
    Create tables and permissions only.
    """
    cur = conn.cursor()
    if reset:
        cur.execute("""
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
        """)

    # Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id          SERIAL PRIMARY KEY,
            x           TEXT NOT NULL,
            y           TEXT NOT NULL,
            death       TIMESTAMPTZ default 'infinity'
        );
        CREATE TABLE IF NOT EXISTS memberships (
            id          SERIAL PRIMARY KEY,
            y           TEXT NOT NULL,
            z           TEXT NOT NULL,
            death       TIMESTAMPTZ default 'infinity'
        );
        CREATE TABLE IF NOT EXISTS audit_log_pos (
            id          BIGSERIAL PRIMARY KEY,
            ts          TIMESTAMPTZ NOT NULL,
            db_user     TEXT NOT NULL,
            action      TEXT NOT NULL,
            table_name  TEXT NOT NULL,
            row_id      INTEGER NOT NULL,
            query       TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log_neg (
            id          BIGSERIAL PRIMARY KEY,
            ts          TIMESTAMPTZ NOT NULL,
            db_user     TEXT NOT NULL,
            action      TEXT NOT NULL,
            table_name  TEXT NOT NULL,
            row_id      INTEGER NOT NULL,
            query       TEXT
        );
    """)

    # Create indexes TODO
    cur.execute("""
        CREATE INDEX ON memberships(death);
        CREATE INDEX ON people(death);
    """)
    #     CREATE UNIQUE INDEX IF NOT EXISTS people_y_active_uq
    #         ON people (y)
    #         WHERE alive = true;

    #     CREATE UNIQUE INDEX IF NOT EXISTS memberships_active_uq
    #         ON memberships (y, z)
    #         WHERE alive = true;
    # """)

    # Create audit trigger
    cur.execute("""
        CREATE OR REPLACE FUNCTION audit_trigger() RETURNS trigger AS $$
        DECLARE
            ts TIMESTAMPTZ;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO audit_log_pos (ts, db_user, action, table_name, row_id, query)
                VALUES (NOW(), current_user, TG_OP, TG_TABLE_NAME, NEW.id, current_query());
            ELSIF TG_OP = 'UPDATE' THEN -- soft deletes are also updates
                INSERT INTO audit_log_neg (ts, db_user, action, table_name, row_id, query)
                VALUES (NEW.death, current_user, TG_OP, TG_TABLE_NAME, NEW.id, current_query());
            END IF;
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

    # # Init permissions
    # cur.execute("""
    #     GRANT SELECT, INSERT, UPDATE, DELETE ON people      TO audit_tracker;
    #     GRANT SELECT, INSERT, UPDATE, DELETE ON memberships TO audit_tracker;
    #     GRANT INSERT                          ON audit_log_pos   TO audit_tracker;
    #     GRANT USAGE, SELECT ON SEQUENCE people_id_seq       TO audit_tracker;
    #     GRANT USAGE, SELECT ON SEQUENCE memberships_id_seq  TO audit_tracker;
    #     GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq    TO audit_tracker;
    # """)

    # Create custom annotation functions
    cur.execute("""     
        CREATE OR REPLACE FUNCTION annotate(birth_id BIGINT, birth_ts TIMESTAMPTZ, death_id BIGINT, death_ts TIMESTAMPTZ) RETURNS jsonb AS $$
            SELECT jsonb_build_object(
                'interval', jsonb_build_array(
                    COALESCE(birth_ts, '-infinity'::timestamptz),
                    COALESCE(death_ts,  'infinity'::timestamptz)
                ),
                'birth', CASE WHEN birth_id IS NULL THEN '[]'::jsonb ELSE jsonb_build_array(birth_id) END,
                'death', CASE WHEN death_id IS NULL THEN '[]'::jsonb ELSE jsonb_build_array(death_id) END
            )
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
            SELECT CASE
                WHEN EXISTS (
                    SELECT 1 
                    FROM jsonb_array_elements(state) AS elem,
                        jsonb_array_elements(elem) AS inner_elem
                    WHERE inner_elem = to_jsonb(9223372036854775807::bigint)
                )
                THEN (
                    SELECT jsonb_agg(DISTINCT sorted_elem)
                    FROM (
                        SELECT (SELECT jsonb_agg(n ORDER BY n::numeric) 
                                FROM jsonb_array_elements(elem) AS n) AS sorted_elem
                        FROM jsonb_array_elements(state) AS elem
                        WHERE elem @> to_jsonb(9223372036854775807::bigint)
                    ) s
                )
                ELSE state
            END;
        $$ LANGUAGE sql;
        
        -- Annotation +: Custom aggregate
        CREATE OR REPLACE AGGREGATE add_annotations(jsonb) (
            SFUNC = annotations_union_trans,
            STYPE = jsonb,
            -- FINALFUNC = annotations_union_final,
            INITCOND = '[]'
        );

        -- Annotation +: Custom aggregate that keeps only elements with MAXVALUE 
        CREATE OR REPLACE AGGREGATE add_annotations_min(jsonb) (
            SFUNC = annotations_union_trans,
            STYPE = jsonb,
            FINALFUNC = annotations_union_final_min,
            INITCOND = '[]'
        );

        -- ANNOTATION *: Custom function to combine annotations from joins
        --      Intersect the intervals
        --          If intervals merge, union birth and death sets
        CREATE OR REPLACE FUNCTION join_annotations(a jsonb, b jsonb) RETURNS jsonb AS $$
        DECLARE
            result      jsonb := '[]'::jsonb;
            a_group     jsonb;
            b_group     jsonb;
            a_elem      jsonb;
            b_elem      jsonb;
            a_start     timestamptz;
            a_end       timestamptz;
            b_start     timestamptz;
            b_end       timestamptz;
            merged_group jsonb;
            i           int;
            j           int;
            k           int;
            l           int;
        BEGIN
            IF jsonb_array_length(a) > 0 AND jsonb_array_length(b) > 0 THEN
                FOR i IN 0 .. jsonb_array_length(a) - 1 LOOP
                    a_group := a -> i;

                    FOR j IN 0 .. jsonb_array_length(b) - 1 LOOP
                        b_group := b -> j;
                        merged_group := '[]'::jsonb;
                        
                        k := 0;
                        l := 0;
                        WHILE k < jsonb_array_length(a_group) AND l < jsonb_array_length(b_group) LOOP
                            a_elem  := a_group -> k;
                            a_start := (a_elem -> 'interval' ->> 0)::timestamptz;
                            a_end   := (a_elem -> 'interval' ->> 1)::timestamptz;

                            b_elem  := b_group -> l;
                            b_start := (b_elem -> 'interval' ->> 0)::timestamptz;
                            b_end   := (b_elem -> 'interval' ->> 1)::timestamptz;

                            IF a_start < b_end AND b_start < a_end THEN
                                merged_group := merged_group || jsonb_build_object(
                                    'birth',   (SELECT jsonb_agg(DISTINCT v) FROM jsonb_array_elements(
                                                    (a_elem -> 'birth') || (b_elem -> 'birth')
                                                ) AS v),
                                    'death',    (SELECT jsonb_agg(DISTINCT v) FROM jsonb_array_elements(
                                                    (a_elem -> 'death') || (b_elem -> 'death')
                                                ) AS v),
                                    'interval', jsonb_build_array(
                                                    GREATEST(a_start, b_start),
                                                    LEAST(a_end, b_end)
                                                )
                                );
                            END IF;

                            IF a_end <= b_end THEN
                                k := k + 1;
                            ELSE
                                l := l + 1;
                            END IF;
                        END LOOP;

                        IF jsonb_array_length(merged_group) > 0 THEN
                            result := result || jsonb_build_array(merged_group);
                        END IF;
                    END LOOP;
                END LOOP;
            END IF;
            
            RETURN result;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
    """)
    cur.close()


def insert(conn, table, data):
    """
    Insert a new row into table. data is a dict of column->value.
    Returns dict with id, or None if failed.
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)

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
    return row if row else None


def update(conn, table, row_id, data):
    """
    Soft-update: deprecate the old row, insert a new one with updated values.
    Returns the new row id, or None if the row doesn't exist or is already deprecated.
    """
    cur = conn.cursor()
    cur.execute(
        sql.SQL("SELECT * FROM {} WHERE id = %s AND death = 'infinity'").format(
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

    # Soft-delete the old row by setting death timestamp
    cur.execute(
        sql.SQL("UPDATE {} SET death = now() WHERE id = %s").format(
            sql.Identifier(table)
        ),
        [row_id]
    )

    # Get full current data
    new_data = {k: v for k, v in current.items() if k not in ("id", "death")}
    new_data.update(data)  # overwrite with updated values
    # insert new row with same data + updates, returns new id
    res = insert(conn, table, new_data)
    cur.close()
    return res


def delete(conn, table, row_id):
    """
    Soft-delete: just set death = now().
    Returns dict with id and death timestamp, or None if failed.
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        sql.SQL("UPDATE {} SET death = now() WHERE id = %s RETURNING id, death").format(
            sql.Identifier(table)),
        [row_id]
    )
    res = cur.fetchone()
    cur.close()
    return res if res else None


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


def get_table_columns_clean(conn, table_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
            AND column_name != 'id' 
            AND column_name != 'annotation'
            AND column_name != 'death'
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    columns = [row[0] for row in cur.fetchall()]
    cur.close()
    return columns
