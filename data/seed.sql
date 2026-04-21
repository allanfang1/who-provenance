-- =========================
-- RELATION1 SEED DATA
-- =========================

INSERT INTO RELATION1 (first_name, last_name, email) VALUES
('Allan', 'Fang', 'allan.fang@example.com'),
('Bill', 'Murray', 'bill.murray@example.com'),
('Tom', 'Hanks', 'tom.hanks@example.com'),
('Serena', 'Williams', 'serena.williams@wrong.com'),
('James', 'Taylor', 'james.taylor@wrong.com');

-- =========================
-- RELATION2 SEED DATA
-- =========================

INSERT INTO RELATION2 (email, age) VALUES
('allan.fang@example.com', 30),
('bill.murray@example.com', 45),
('tom.hanks@example.com', 45),
('serena.williams@example.com', 35),
('james.taylor@example.com', 50);

-- =========================
-- USERS SEED DATA
-- =========================

INSERT INTO USERS (name) VALUES
('Bot'),
('Human'),
('Jonathan'),
('Test');

-- =========================
-- QUERY_LOG SEED DATA (with timestamps)
-- =========================

INSERT INTO query_log (user_id, action, table_name, primary_key, timestamp) VALUES
(1, 'create', 'RELATION1', 'allan.fang@example.com', '2026-04-20 09:12:00'),
(2, 'read',   'RELATION2', 'bill.murray@example.com', '2026-04-20 09:15:30'),
(3, 'update', 'RELATION2', 'bill.murray@example.com', '2026-04-20 09:18:10'),
(3, 'update', 'RELATION1', 'bill.murray@example.com', '2026-04-20 09:17:10'),
(4, 'delete', 'RELATION1', 'serena.williams@wrong.com', '2026-04-20 09:22:45');