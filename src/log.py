"""
log.py - Postgres log file utilities.

Provides:
- delete_log_files: remove existing log files
- ingest_log_files: load log lines into a database table
"""

import csv
import datetime as dt
import os
import re
from glob import glob

import psycopg2.extras


WRITE_COMMANDS = {"INSERT", "UPDATE", "DELETE"}


def _parse_audit_message(message):
    """
    Parse a pgaudit CSV message into components.
    Returns dict with keys: audit_class, command_tag, statement_id,
    statement_subid, statement_text.
    """
    if not message or not message.startswith("AUDIT: "):
        return None

    payload = message[len("AUDIT: "):]
    try:
        fields = next(csv.reader([payload], delimiter=",", quotechar='"'))
    except csv.Error:
        return None

    if not fields or fields[0] != "SESSION":
        return None

    def _to_int(value):
        return int(value) if value and value.isdigit() else None

    audit_class = fields[3] if len(fields) > 3 else None
    command_tag = fields[4] if len(fields) > 4 else None
    statement_id = _to_int(fields[1]) if len(fields) > 1 else None
    statement_subid = _to_int(fields[2]) if len(fields) > 2 else None

    statement_text = None
    for field in reversed(fields):
        if re.match(r"^(INSERT|UPDATE|DELETE)\b", field or "", re.IGNORECASE):
            statement_text = field
            break

    return {
        "audit_class": audit_class,
        "command_tag": command_tag,
        "statement_id": statement_id,
        "statement_subid": statement_subid,
        "statement_text": statement_text,
    }


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
                    id               SERIAL PRIMARY KEY,
                    log_time         TIMESTAMPTZ NOT NULL,
                    user_name        TEXT NOT NULL,
                    database_name    TEXT NOT NULL,
                    session_id       TEXT NOT NULL,
                    statement_index  INTEGER,
                    statement_subidx INTEGER,
                    statement_text   TEXT NOT NULL
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
                line_text = line_text.rstrip("\n")
                if not line_text:
                    continue

                try:
                    fields = next(csv.reader(
                        [line_text], delimiter=",", quotechar='"'))
                except csv.Error:
                    continue

                if len(fields) < 14:
                    continue

                raw_time = fields[0]
                user_name = fields[1]
                database_name = fields[2]
                session_id = fields[5]
                command_tag = fields[7]
                message = fields[13]

                if raw_time.endswith(" UTC"):
                    raw_time = raw_time[:-4] + "+00:00"

                try:
                    log_time = dt.datetime.fromisoformat(raw_time)
                except ValueError:
                    continue

                audit = _parse_audit_message(message)
                if audit:
                    audit_class = audit.get("audit_class")
                    audit_command = audit.get("command_tag")
                    statement_text = audit.get("statement_text")
                    statement_index = audit.get("statement_id")
                    statement_subidx = audit.get("statement_subid")
                else:
                    audit_class = None
                    audit_command = None
                    statement_text = None
                    statement_index = None
                    statement_subidx = None

                is_write = False
                if audit_class == "WRITE":
                    is_write = True
                elif (audit_command or command_tag) in WRITE_COMMANDS:
                    is_write = True

                if not is_write or not statement_text:
                    continue

                rows.append((
                    log_time,
                    user_name,
                    database_name,
                    session_id,
                    statement_index,
                    statement_subidx,
                    statement_text,
                ))
                if len(rows) >= batch_size:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                                                INSERT INTO postgres_logs (
                                                    log_time,
                                                    user_name,
                                                    database_name,
                                                    session_id,
                                                    statement_index,
                                                    statement_subidx,
                                                    statement_text
                                                )
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
                                INSERT INTO postgres_logs (
                                    log_time,
                                    user_name,
                                    database_name,
                                    session_id,
                                    statement_index,
                                    statement_subidx,
                                    statement_text
                                )
                                VALUES %s
                                """,
                rows,
            )
            counts[file_name] += len(rows)

    cur.close()
    return counts
