"""
log.py - Postgres log file utilities.

Provides:
- delete_log_files: remove existing log files
- ingest_log_files: load log lines into a database table
"""

import os
from glob import glob

import psycopg2.extras


def delete_log_files(log_dir="/var/lib/postgresql/data/log", pattern="postgresql*"):
    """
    Delete log files matching pattern in log_dir.
    Returns list of deleted file paths.
    """
    deleted = []
    for path in sorted(glob(os.path.join(log_dir, pattern))):
        if os.path.isfile(path):
            os.remove(path)
            deleted.append(path)
    return deleted


def drop_log_table(conn):
    """
    Drop the postgres_logs table.
    """
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS postgres_logs;")
    cur.close()


def ingest_log_files(conn, log_dir="/logs", pattern="postgresql*.csv",
                     truncate=False, batch_size=1000):
    """
    Load log file lines into a table. Returns counts by file.
    """
    cur = conn.cursor()
    cur.execute(
        """
                CREATE TABLE IF NOT EXISTS postgres_logs (
                        id          SERIAL PRIMARY KEY,
                        file_name   TEXT NOT NULL,
                        line_no     INTEGER NOT NULL,
                        line_text   TEXT NOT NULL,
                        loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
    )

    if truncate:
        cur.execute("TRUNCATE TABLE IF EXISTS postgres_logs;")

    counts = {}
    for path in sorted(glob(os.path.join(log_dir, pattern))):
        if not os.path.isfile(path):
            continue

        file_name = os.path.basename(path)
        counts[file_name] = 0

        rows = []
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line_no, line_text in enumerate(handle, start=1):
                rows.append((file_name, line_no, line_text.rstrip("\n")))
                if len(rows) >= batch_size:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                                                INSERT INTO postgres_logs (file_name, line_no, line_text)
                                                VALUES %s
                                                """,
                        rows,
                    )
                    counts[file_name] += len(rows)
                    rows = []

        if rows:
            psycopg2.extras.execute_values(
                cur,
                """
                                INSERT INTO postgres_logs (file_name, line_no, line_text)
                                VALUES %s
                                """,
                rows,
            )
            counts[file_name] += len(rows)

    cur.close()
    return counts
