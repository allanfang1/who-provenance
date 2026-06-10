"""
demo_db.py - Database setup and utilities for the demo database.
Allows faking the current time for easier seeding and testing.
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


DEMO_USERS = {"allan", "riccardo", "miika"}
DEFAULT_EXEC_USER = "postgres"


def _resolve_exec_user(username):
    if username in DEMO_USERS:
        return username
    return DEFAULT_EXEC_USER


def _set_role(cur, username):
    resolved = _resolve_exec_user(username)
    cur.execute(sql.SQL("SET ROLE {};").format(sql.Identifier(resolved)))


def _reset_role(cur):
    cur.execute("RESET ROLE;")


def get_connection(host="localhost", port=5432, dbname="demo",
                   user="postgres", password="postgres"):
    conn = psycopg2.connect(host=host, port=port, dbname=dbname,
                            user=user, password=password)
    conn.autocommit = True
    return conn


def set_time(conn, time_str):
    """
    Sets a session-level config variable to mock the current time.
    Call this with a string like '2025-01-01 10:00:00Z'
    """
    cur = conn.cursor()
    res = cur.execute(
        "SELECT set_config('demo.time', %s, false);", (time_str,))
    cur.close()


def reset_time(conn):
    """
    Clears the mocked time, returning to normal wall-clock time.
    """
    cur = conn.cursor()
    cur.execute("SELECT set_config('demo.time', '', false);")
    cur.close()


def truncate_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        TRUNCATE people, memberships, audit_log;
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

    # Function to get the mocked time or the real time
    cur.execute("""
        CREATE OR REPLACE FUNCTION demo_now() RETURNS TIMESTAMPTZ AS $$
        DECLARE
            t TEXT;
        BEGIN
            t := current_setting('demo.time', true);
            IF t IS NULL OR t = '' THEN
                RETURN NOW();
            ELSE
                RETURN t::TIMESTAMPTZ;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
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
        CREATE TABLE IF NOT EXISTS audit_log (
            id          BIGSERIAL PRIMARY KEY,
            pos_neg     TEXT NOT NULL CHECK (pos_neg IN ('pos', 'neg')),
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
                
        CREATE UNIQUE INDEX IF NOT EXISTS people_active_uq
            ON people (x, y);

        CREATE UNIQUE INDEX IF NOT EXISTS memberships_active_uq
            ON memberships (y, z);
    """)

    # Create audit trigger
    cur.execute("""
        CREATE OR REPLACE FUNCTION audit_trigger() RETURNS trigger AS $$
        DECLARE
            op TEXT;
        BEGIN
            op := current_setting('demo.op', true);
            IF TG_OP = 'UPDATE' AND NEW.death != 'infinity' THEN             
                INSERT INTO audit_log (ts, pos_neg, db_user, action, table_name, row_id, query)
                VALUES (NEW.death, 'neg', current_user, op, TG_TABLE_NAME, NEW.id, current_query());
            ELSE
                INSERT INTO audit_log (ts, pos_neg, db_user, action, table_name, row_id, query)
                VALUES (demo_now(), 'pos', current_user, op, TG_TABLE_NAME, NEW.id, current_query()); 
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

    # Create demo users with top-level read/write permissions
    for username in DEMO_USERS:
        try:
            cur.execute(sql.SQL("CREATE ROLE {} LOGIN").format(
                sql.Identifier(username)))
        except psycopg2.errors.DuplicateObject:
            conn.rollback()

        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
            sql.Identifier(username)))
        cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
            sql.Identifier(username)))
        cur.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
            sql.Identifier(username)))

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

        CREATE OR REPLACE FUNCTION annotate(birth_id json, birth_ts TIMESTAMPTZ, death_id json, death_ts TIMESTAMPTZ) RETURNS jsonb AS $$
            SELECT jsonb_build_object(
                'interval', jsonb_build_array(
                    COALESCE(birth_ts, '-infinity'::timestamptz),
                    COALESCE(death_ts,  'infinity'::timestamptz)
                ),
                'birth', CASE WHEN birth_id IS NULL THEN '[]'::jsonb ELSE jsonb_build_array(birth_id) END,
                'death', CASE WHEN death_id IS NULL THEN '[]'::jsonb ELSE jsonb_build_array(death_id) END
            )
        $$ LANGUAGE sql;

        CREATE OR REPLACE FUNCTION annotate_trans(state jsonb, val jsonb, pos_neg text, ts timestamptz)
        RETURNS jsonb AS $$
        DECLARE
            last_entry jsonb;
            updated_last jsonb;
        BEGIN
            IF val IS NULL THEN
                RETURN state || jsonb_build_object(
                    'interval', jsonb_build_array('-infinity'::timestamptz, 'infinity'::timestamptz),
                    'birth',    '[]'::jsonb,
                    'death',    '[]'::jsonb
                );
            ELSIF pos_neg = 'pos' THEN
                RETURN state || jsonb_build_object(
                    'interval', jsonb_build_array(ts, 'infinity'::timestamptz),
                    'birth',    jsonb_build_array(val),
                    'death',    '[]'::jsonb
                );

            ELSIF jsonb_array_length(state) = 0 THEN
                RETURN state || jsonb_build_object(
                    'interval', jsonb_build_array('-infinity'::timestamptz, ts),
                    'birth',    '[]'::jsonb,
                    'death',    jsonb_build_array(val)
                );

            ELSE
                -- Update the last element: set interval[1] = ts and append val to death
                last_entry := state -> (jsonb_array_length(state) - 1);

                updated_last := last_entry
                    || jsonb_build_object('interval', jsonb_set(
                            last_entry -> 'interval',
                            '{1}',
                            to_jsonb(ts)
                    ))
                    || jsonb_build_object('death', jsonb_build_array(val))
                ;

                RETURN jsonb_set(state, ARRAY[(jsonb_array_length(state) - 1)::text], updated_last);
            END IF;
        END;
        $$ LANGUAGE plpgsql;

            
        CREATE OR REPLACE AGGREGATE annotate_agg(jsonb, text, timestamptz) (
            SFUNC = annotate_trans,
            STYPE = jsonb,
            INITCOND = '[]'
        );
        
        
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


def insert(conn, table, data, as_user=None, is_update=False):
    """
    Insert a new row into table. data is a dict of column->value.
    Returns nothing.
    """
    cur = conn.cursor()

    if not is_update:
        cur.execute("SELECT set_config('demo.op', 'INSERT', false)")
    _set_role(cur, as_user)

    columns = data.keys()
    values = list(data.values())

    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET death = 'infinity' WHERE {}.death != 'infinity'").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() * len(values)),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.Identifier(table)
    )

    try:
        cur.execute(query, values)
        if cur.rowcount == 0:
            print(table, data)
            raise RuntimeError("Insert affected 0 rows.")
    # except psycopg2.errors.UniqueViolation as exc:
    #     raise ValueError("Duplicate active row.") from exc
    finally:
        _reset_role(cur)
        cur.close()


def update(conn, table, current_data, new_data, as_user=None):
    """
    Soft-update: deprecate the old row, insert a new one with updated values.
    """
    if not current_data:
        raise ValueError("No WHERE values provided.")

    if all(current_data.get(k) == v for k, v in new_data.items()):
        raise ValueError("No changes provided.")

    cur = conn.cursor(cursor_factory=RealDictCursor)
    _set_role(cur, as_user)
    try:
        cur.execute("SELECT set_config('demo.op', 'UPDATE', false)")
        row = delete(conn, table, current_data,
                     as_user=as_user, is_update=True)
        full_data = {k: row[k] for k in row if k not in ("id", "death")}
        full_data.update(new_data)
        insert(conn, table, full_data, as_user=as_user, is_update=True)
    finally:
        _reset_role(cur)
        cur.close()


def delete(conn, table, current_data, as_user=None, is_update=False):
    """
    Soft-delete: just set death = demo_now(). Returns the deleted row.
    """
    if not current_data:
        raise ValueError("No WHERE values provided.")

    where_cols = [sql.SQL("{} = %s").format(sql.Identifier(k))
                  for k in current_data]
    where_clause = sql.SQL(" AND ").join(where_cols)
    where_values = list(current_data.values())

    cur = conn.cursor(cursor_factory=RealDictCursor)
    _set_role(cur, as_user)
    try:
        if not is_update:
            cur.execute("SELECT set_config('demo.op', 'DELETE', false)")
        cur.execute(
            sql.SQL(
                "UPDATE {} SET death = demo_now() WHERE {} AND death = 'infinity' RETURNING *"
            ).format(sql.Identifier(table), where_clause),
            where_values,
        )
        row = cur.fetchone()
        if row is None:
            raise LookupError("No active row matched the WHERE values.")
        return row
    finally:
        _reset_role(cur)
        cur.close()


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
