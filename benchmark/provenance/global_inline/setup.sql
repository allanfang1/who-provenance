--

-- audit log
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

-- insert
CREATE OR REPLACE FUNCTION insert_audit() RETURNS trigger AS $$
BEGIN
    INSERT INTO audit_log (
        ts, pos_neg, db_user, action, table_name, row_id, query
    )
    VALUES (
        NOW(),
        'pos',
        current_user,
        TG_OP,
        TG_TABLE_NAME,
        OLD.id,
        current_query()
    );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- update OUR BENCHMARK HAS NO UPDATES HAHA

-- soft delete
CREATE OR REPLACE FUNCTION soft_delete() RETURNS trigger AS $$
BEGIN
    EXECUTE format(
        'UPDATE %I SET is_current = false WHERE id = $1',
        TG_TABLE_NAME
    )
    USING OLD.id;

    INSERT INTO audit_log (
        ts, pos_neg, db_user, action, table_name, row_id, query
    )
    VALUES (
        NOW(),
        'neg',
        current_user,
        TG_OP,
        TG_TABLE_NAME,
        OLD.id,
        current_query()
    );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;