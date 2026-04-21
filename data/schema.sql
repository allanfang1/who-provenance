-- =========================
-- RELATION1
-- =========================

CREATE TABLE IF NOT EXISTS RELATION1 (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT
);

-- =========================
-- RELATION2
-- =========================

CREATE TABLE IF NOT EXISTS RELATION2 (
    email TEXT PRIMARY KEY,
    age INTEGER
);

-- =========================
-- USERS
-- =========================

CREATE TABLE IF NOT EXISTS USERS (
    id INTEGER PRIMARY KEY,
    name TEXT
);

-- =========================
-- QUERY LOG (audit trail)
-- =========================

CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('create', 'read', 'update', 'delete')),
    table_name TEXT,
    primary_key TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USERS(id)
);