import psycopg2
from psycopg2 import sql
from pathlib import Path
from time import perf_counter
import csv
from line_stripper import GenFile
import re
import os


def connect(dbname="postgres"):
    conn = psycopg2.connect(host="localhost", port=5432, dbname=dbname,
                            user="postgres", password="postgres")
    conn.autocommit = True
    return conn


def reset_database(dbname):
    """Reset the database (including schema + permissions) and reseed the demo database."""
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


def create_schema(dbname, path="tpcds/DSGen-software-code-4.0.0/tools/tpcds.sql"):
    # "tpcds/DSGen-software-code-4.0.0/tools/tpcds_source.sql"
    with open(path, "r") as f:
        with connect(dbname) as conn:
            with conn.cursor() as cur:
                cur.execute(f.read())
    print(f"Schema created in database {dbname} from {path}")


def create_staging_schema(dbname, path="tpcds/DSGen-software-code-4.0.0/tools/tpcds_source.sql"):
    with open(path, "r") as f:
        with connect(dbname) as conn:
            with conn.cursor() as cur:
                cur.execute(f.read())
    print(f"Staging schema created in database {dbname} from {path}")


def load_data(dbname, scale=1):
    data_dir = Path(f"tpcds/data/{scale}/0")
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            for file in data_dir.glob("*.dat"):
                table = file.stem
                with open(file, "r", encoding="utf-8") as f:
                    cur.copy_from(GenFile(f), table, sep="|", null="")
    print(f"Data loaded into database {dbname} from {data_dir}")


def load_delete_dates(dbname, scale=1, update=1):
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
                    cur.copy_from(GenFile(f), "delete_dates", sep="|", null="")
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


def extract_staging_data(dbname, scale=1, update=1):
    data_dir = Path(f"tpcds/data/{scale}/{update}")
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            for file in data_dir.glob("s_*.dat"):
                table = re.sub(r"_\d+_\d+$", "", file.stem)
                if table not in STAGING_TABLES:
                    continue
                with open(file, "r", encoding="utf-8") as f:
                    cur.copy_from(GenFile(f), table, sep="|", null="")


def install_provenance(provenance_type):
    pass


def transform_load_update(dbname, path="benchmark/maintenance.sql"):
    with open(path, "r") as f:
        with connect(dbname) as conn:
            with conn.cursor() as cur:
                cur.execute(f.read())


def run_benchmark(dbname, experiment, run, scale, update):
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_database_size(%s)", (dbname,))
            current_size = cur.fetchone()[0]

            print(
                f"Running benchmark {experiment}, run {run}, scale {scale}, update {update}")
            start = perf_counter()

            extract_staging_data(dbname, scale, update)
            load_delete_dates(dbname, scale, update)
            transform_load_update(dbname)

            elapsed = perf_counter() - start

            cur.execute("SELECT pg_database_size(%s)", (dbname,))
            new_size = cur.fetchone()[0]

            filename = f"benchmark/results/{experiment}.csv"
            file_exists = os.path.isfile(filename)
            with open(filename, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(
                        ["experiment", "run", "update", "current_size_B", "new_size_B", "elapsed"])
                writer.writerow(
                    [experiment, run, update, current_size, new_size, elapsed])
