import sqlite3
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent

def create_connection(db_file):
    if db_file.exists():
        db_file.unlink()
    connection = sqlite3.connect(db_file)
    connection.row_factory = sqlite3.Row
    return connection

def setup_database(cursor, path):
    cursor.executescript(open(path / "schema.sql").read())
    cursor.executescript(open(path / "seed.sql").read())

def query_r1_r2_with_logs(connection, begin_timestamp, end_timestamp, projection):
    cursor = connection.cursor()

    
    query_log_sql = """
        SELECT
            ql.primary_key,
            ql.id,
            ql.timestamp,
            ROW_NUMBER() OVER (
                PARTITION BY ql.primary_key
                ORDER BY ql.timestamp DESC
            ) AS rn
        FROM query_log ql
        WHERE ql.timestamp BETWEEN ? AND ?
        AND ql.table_name IN ('RELATION1', 'RELATION2')
    """

    final_sql = """
        WITH latest_query_log AS (
            SELECT
                ql.primary_key,
                ql.id,
                ql.timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY ql.primary_key
                    ORDER BY ql.timestamp DESC
                ) AS rn
            FROM query_log ql
            WHERE ql.timestamp BETWEEN ? AND ?
            AND ql.table_name IN ('RELATION1', 'RELATION2')
        )

        SELECT
            r1.first_name,
            r1.last_name,
            r2.age AS age,
            lql.id AS query_log_id
        FROM RELATION1 r1
        JOIN RELATION2 r2 ON r1.email = r2.email
        LEFT JOIN latest_query_log lql
            ON lql.primary_key = r1.email
        AND lql.rn = 1
        WHERE r2.age = ?;
    """

    query_log_rows = cursor.execute(query_log_sql, (begin_timestamp, end_timestamp)).fetchall()

    joined_rows = cursor.execute(
        final_sql,
        (begin_timestamp, end_timestamp, projection),
    ).fetchall()

    return {
        "joined_rows": [dict(row) for row in joined_rows],
        "query_log_sql": [dict(row) for row in query_log_rows],
    }

def main():
    poc_db = create_connection(BASE_DIR / "data" / "poc.db")
    poc_db.execute("PRAGMA foreign_keys = ON;")

    cursor = poc_db.cursor()
    setup_database(cursor, BASE_DIR / "data")

    result = query_r1_r2_with_logs(
        poc_db,
        "2026-04-20 09:10:00",
        "2026-04-20 09:20:00",
        projection=45,
    )
    print(json.dumps(result, indent=2))

    poc_db.close()

if __name__ == "__main__":
    main()