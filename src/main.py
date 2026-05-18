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
          "x": "Alice", "y": "alice@example.com"}))
    print(insert(conn, "people", {"x": "Bob", "y": "bob@example.com"}))
    print("test_insert")


def test_update():
    conn = get_connection()
    print(update(conn, "people", 1, {"x": "Alison"}))
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


def test_classic():
    conn = get_connection()

    reset()

    # --- seed data ---
    insert(conn, "memberships", {"y": "b1", "z": "e"})

    r0_id = insert(
        conn, "people", {"x": "a", "y": "b"})
    delete(conn, "people", r0_id)

    r1_id = insert(
        conn, "people", {"x": "a", "y": "b"})
    update(conn, "people", r1_id, {"y": "b1"})

    s1_id = insert(conn, "memberships", {
        "y": "b", "z": "c"})
    update(conn, "memberships", s1_id, {"y": "b1"})

    s3_id = insert(conn, "memberships", {
        "y": "b1", "z": "d"})
    s4_id = update(conn, "memberships", s3_id, {"z": "d1"})

    delete(conn, "memberships", s4_id)

    print("test_classic")


def run_test():
    conn = get_connection()
    cur = conn.cursor()

    reset()

    # --- seed data ---
    insert(conn, "memberships", {"y": "b1", "z": "e"})

    r0_id = insert(
        conn, "people", {"x": "a", "y": "b"})
    delete(conn, "people", r0_id)

    r1_id = insert(
        conn, "people", {"x": "a", "y": "b"})
    update(conn, "people", r1_id, {"y": "b1"})

    s1_id = insert(conn, "memberships", {
        "y": "b", "z": "c"})
    update(conn, "memberships", s1_id, {"y": "b1"})

    s3_id = insert(conn, "memberships", {
        "y": "b1", "z": "d"})
    s4_id = update(conn, "memberships", s3_id, {"z": "d1"})

    delete(conn, "memberships", s4_id)

    # check()

    # --- run test query ---
    columns_people = get_table_columns_no_annotation(conn, 'people')
    columns_memberships = get_table_columns_no_annotation(conn, 'memberships')

    columns_people_no_id_annotation = get_table_columns_no_id_annotation(
        conn, 'people')
    columns_memberships_no_id_annotation = get_table_columns_no_id_annotation(
        conn, 'memberships')

    my_query = Rewriter.build_cte([
        ("step1", Rewriter.scan("memberships", columns_memberships, "2", "99")),
        ("step2", Rewriter.scan("people", columns_people, "2", "99")),
        ("step3", Rewriter.join("step2", columns_people_no_id_annotation,
         "step1", columns_memberships_no_id_annotation, "t1.y = t2.y")),
        ("final", Rewriter.aggregate_min(
            "step3", ["t1_x", "t1_y"]))
    ], "SELECT * FROM final")

    cur.execute(my_query)
    column_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    print(column_names)
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
    "test_classic": test_classic,
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
