"""Model layer PostgreSQL APIs for blame-provenance experiment runner
"""

import psycopg2
from psycopg2 import sql
from pathlib import Path
from time import perf_counter
import csv
from line_stripper import GenFile
import re
import os

TABLES = ["dbgen_version",
          "customer_address",
          "customer_demographics",
          "date_dim",
          "warehouse",
          "ship_mode",
          "time_dim",
          "reason",
          "income_band",
          "item",
          "store",
          "call_center",
          "customer",
          "web_site",
          "store_returns",
          "household_demographics",
          "web_page",
          "promotion",
          "catalog_page",
          "inventory",
          "catalog_returns",
          "web_returns",
          "web_sales",
          "catalog_sales",
          "store_sales",
          ]

STAGING_TABLES = {
    "s_purchase_lineitem",
    "s_purchase",
    "s_catalog_order_lineitem",
    "s_catalog_order",
    "s_web_order_lineitem",
    "s_web_order",
    "s_store_returns",
    "s_catalog_returns",
    "s_inventory",
    "s_web_returns",
}


def connect(dbname="postgres"):
    """Returns connection object to the target Postgres DB"""
    conn = psycopg2.connect(host="localhost", port=5432, dbname=dbname,
                            user="postgres", password="postgres")
    conn.autocommit = True
    return conn


def reset_database(dbname):
    """Reset the database (including schema + permissions) and reseed the demo database."""  # I don't think it reseeds?
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(dbname)))
            cur.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(dbname)))
    finally:
        conn.close()
        print(f"Database {dbname} reset")


def create_schema(dbname, type="baseline"):
    """Create tables and staging tables from schema"""
    path = f"benchmark/schema/{type}/tpcds.sql"
    with open(path, "r") as f:
        with connect(dbname) as conn:
            with conn.cursor() as cur:
                cur.execute(f.read())
    print(f"Schema created in database {dbname} from {path}")
    staging_path = f"benchmark/schema/{type}/tpcds_source.sql"
    with open(staging_path, "r") as f:
        with connect(dbname) as conn:
            with conn.cursor() as cur:
                cur.execute(f.read())
    print(f"Staging schema created in database {dbname} from {staging_path}")


def provenance_init(dbname, provenance_type="none"):
    """Initialize insert and delete triggers for each (non-staging) table"""
    if (provenance_type != 'none'):
        setup_path = f"benchmark/provenance/{provenance_type}/setup.sql"
        prop_path = f"benchmark/provenance/propagation.sql"
        insert_trigger_path = f"benchmark/provenance/{provenance_type}/insert_trigger_template.sql"
        delete_trigger_path = f"benchmark/provenance/{provenance_type}/delete_trigger_template.sql"
        with connect(dbname) as conn:
            with conn.cursor() as cur:
                with open(setup_path) as a:
                    cur.execute(a.read())
                with open(prop_path) as p:
                    cur.execute(p.read())
                with open(insert_trigger_path) as it:
                    with open(delete_trigger_path) as dt:
                        for table in TABLES:
                            query = dt.read().format(
                                trigger_name=f"{table}_soft_delete",
                                table_name=table,)
                            cur.execute(query)
                            query = it.read().format(
                                trigger_name=f"{table}_insert_audit",
                                table_name=table,)
                            cur.execute(query)
    print(f"Initialized provenance infrastructure")


def transform_load_update(dbname, path="benchmark/maintenance.sql"):
    """Execute update cycle"""
    with open(path, "r") as f:
        with connect(dbname) as conn:
            with conn.cursor() as cur:
                cur.execute(f.read())


def load_delete_dates(dbname, scale=1, update=1):
    """Creates and loads two tables containing the deletion date parameters of an update cycle"""
    data_dir = Path(f"tpcds/data/{scale}/{update}")
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            for file in data_dir.glob("delete*.dat"):
                with open(file, "r", encoding="utf-8") as f:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS delete_dates (
                            start_date DATE,
                            end_date DATE
                        );
                    """)
                    cur.copy_from(GenFile(f),
                                  "delete_dates", sep="|", null="")
            for file in data_dir.glob("inventory_delete*.dat"):
                with open(file, "r", encoding="utf-8") as f:
                    cur.execute("""
                                    CREATE TABLE IF NOT EXISTS inventory_delete_dates (
                                        start_date DATE,
                                        end_date DATE
                                    );
                                """)
                    cur.copy_from(GenFile(f), "inventory_delete_dates",
                                  sep="|", null="")


def extract_staging_data(dbname, scale=1, update=1):
    """Populate staging tables for update cycle"""
    data_dir = Path(f"tpcds/data/{scale}/{update}")
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            for file in data_dir.glob("s_*.dat"):
                table = re.sub(r"_\d+_\d+$", "", file.stem)
                if table not in STAGING_TABLES:
                    continue
                with open(file, "r", encoding="utf-8") as f:
                    cur.copy_from(GenFile(f), table, sep="|", null="")

def load_data(dbname, scale, cur):
    """Populate DB with seed data (update 0)"""
    data_dir = Path(f"tpcds/data/{scale}/0")
    for file in data_dir.glob("*.dat"):
        table = file.stem
        with open(file, "r", encoding="utf-8") as f:
            cur.copy_from(GenFile(f, False), table, sep="|", null="") #TODO automatic False for baseline no is_current col
    print(f"Data loaded into database {dbname} from {data_dir}")

def split_sql_statements(query_stream: str) -> list[str]:
    # Matches how rewriter.process_file wrote the file: ";\n".join(...) + ";\n"
    return [s for s in query_stream.split(";\n") if s.strip()]

def execute_query_stream(cur, path, experiment, run, update):
    with open(path, "r") as f:
        query_stream = f.read()

    statements = split_sql_statements(query_stream)

    for stmt_count, stmt in enumerate(statements):
        stmt = stmt.strip()
        if not stmt:
            continue
        cur.execute(stmt)
        print(f"stmt {stmt_count}: rowcount={cur.rowcount}, description={cur.description is not None}")
        if cur.description is not None:
            rows = cur.fetchall()
            print(f"  fetched {len(rows)} rows")
            filename = f"benchmark/results/query_results/{experiment}_{run}_{update}_{stmt_count}.csv"
            with open(filename, "w", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerows(rows)


def run_benchmark(dbname, experiment, run, scale, updates, is_provenanced=False):
    """Run benchmark"""
    filename = f"benchmark/results/{experiment}.csv"
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            load_start = perf_counter()
            load_data(dbname, scale, cur)
            load_elapsed = perf_counter() - load_start

            cur.execute("SELECT pg_database_size(%s)", (dbname,))
            current_size = cur.fetchone()[0]

            print(f"Running benchmark {experiment}, run {run}, scale {scale}, update 0")

            query_start = perf_counter()
            if is_provenanced:
                execute_query_stream(cur, f"tpcds/data/{scale}/queries_annotated/query_0.sql", experiment, run, 0)
            else:
                execute_query_stream(cur, f"tpcds/data/{scale}/queries_baseline/query_0.sql", experiment, run, 0)
            query_elapsed = perf_counter() - query_start

            write_result(filename, experiment, run, 0, current_size, load_elapsed, query_elapsed)
            
            for update in range(1, updates + 1):
                """1 data maintenance cycle"""
                
                print(f"Running benchmark {experiment}, run {run}, scale {scale}, update {update}")
                start = perf_counter()

                extract_staging_data(dbname, scale, update)
                load_delete_dates(dbname, scale, update)
                transform_load_update(dbname)

                elapsed = perf_counter() - start

                query_start = perf_counter()
                if is_provenanced:
                    execute_query_stream(cur, f"tpcds/data/{scale}/queries_annotated/query_0.sql", experiment, run, update)
                else:
                    execute_query_stream(cur, f"tpcds/data/{scale}/queries_baseline/query_0.sql", experiment, run, update)
                query_elapsed = perf_counter() - query_start

                cur.execute("SELECT pg_database_size(%s)", (dbname,))
                new_size = cur.fetchone()[0]

                write_result(filename, experiment, run, update, new_size, elapsed, query_elapsed)

def write_result(filename, experiment, run, update, size, maintenance_elapsed, query_elapsed):
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(
                ["experiment", "run", "update", "size_B", "maintenance_elapsed", "query_elapsed"])
        writer.writerow(
            [experiment, run, update, size, maintenance_elapsed, query_elapsed])
