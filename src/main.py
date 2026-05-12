import argparse
import json
from db import *
from rewriter import Rewriter


def reset():
    conn = get_connection()
    # delete_log_files()
    # drop_log_table(conn)
    setup(conn, reset=True)
    print("reset")


def check():
    conn = get_connection()
    overview = get_db_overview(conn, 20)
    for table in overview:
        print(f"Schema: {table['schema']}, Table: {table['table']}")
        print("Columns:", table['columns'])
        print("Rows:")
        for row in table['rows']:
            print("  ", row)
    print("check")


def test_insert():
    conn = get_connection()
    print(insert(conn, "people", {
          "name": "Alice", "email": "alice@example.com"}))
    print(insert(conn, "people", {"name": "Bob", "email": "bob@example.com"}))
    print("test_insert")


def test_update():
    conn = get_connection()
    print(update(conn, "people", 1, {"name": "Alison"}))
    print("test_update")


def test_delete():
    conn = get_connection()
    print(delete(conn, "people", 2))
    print("test_delete")

# def ingest_logs():
#     conn = get_connection()
#     counts = ingest_log_files(conn)
#     for file_name, count in counts.items():
#         print(f"{file_name}: {count} lines ingested")
#     print("ingest_logs")


def run_test():
    conn = get_connection()
    cur = conn.cursor()

    reset()

    # --- seed data ---
    insert(conn, "memberships", {"email": "b1", "role": "e"})

    r0_id = insert(
        conn, "people", {"name": "a", "email": "b"})
    delete(conn, "people", r0_id)
    
    r1_id = insert(
        conn, "people", {"name": "a", "email": "b"})
    update(conn, "people", r1_id, {"email": "b1"})

    s1_id = insert(conn, "memberships", {
        "email": "b", "role": "c"})
    update(conn, "memberships", s1_id, {"email": "b1"})

    s3_id = insert(conn, "memberships", {
        "email": "b1", "role": "d"})
    s4_id = update(conn, "memberships", s3_id, {"role": "d1"})

    delete(conn, "memberships", s4_id)

    # check()

    # --- run test query ---
    columns_people = get_table_columns_no_annotation(conn, 'people')
    columns_memberships = get_table_columns_no_annotation(conn, 'memberships')

    # my_query = Rewriter.build_cte([
    #     # ("step1", Rewriter.scan("memberships", "2", "99")),
    #     # ("buh", Rewriter.aggregate("step1", columns_memberships)),
    #     ("final", Rewriter.scan("people", get_table_columns(conn, 'people'), "2", "99")),
    #     # ("fdf", Rewriter.aggregate("step3", columns_people)),
    #     # ("final", Rewriter.join("step4", columns_people, "step2", columns_memberships, "t1.email = t2.email"))
    # ], "SELECT * FROM final")

    my_query = Rewriter.build_cte([
        ("step1", Rewriter.scan("memberships", columns_memberships, "2", "99")),
        ("step2", Rewriter.scan("people", columns_people, "2", "99")),
        ("final", Rewriter.join("step2", get_table_columns_no_id_annotation(conn, 'people'), "step1", get_table_columns_no_id_annotation(conn, 'memberships'), "t1.email = t2.email"))
    ], "SELECT * FROM final")

    cur.execute(my_query)
    rows = cur.fetchall()
    for row in rows:
        print(row)
    print("run_test")


COMMANDS = {
    "reset": reset,
    "check": check,
    # "ingest_logs": ingest_logs
    "test_insert": test_insert,
    "test_update": test_update,
    "test_delete": test_delete,
    "run_test": run_test,
}


def main():
    parser = argparse.ArgumentParser(description="Run the main program.")
    parser.add_argument("command", choices=COMMANDS.keys(),
                        help="The command to run.")
    args = parser.parse_args()

    if args.command in COMMANDS:
        COMMANDS[args.command]()


if __name__ == "__main__":
    main()
