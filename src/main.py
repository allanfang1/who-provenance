import argparse
import datetime
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


def validate(result, expected):
    if result == expected:
        print("PASS")
    else:
        print("FAIL")
        print("Expected:", expected)


def test_seeding(truncate=False):
    conn = get_connection()

    # optional
    if truncate:
        print("Truncate tables")
        truncate_tables(conn)

    insert(conn, "memberships", {"y": "b1", "z": "e"})

    r0_id = insert(
        conn, "people", {"x": "a", "y": "b"})["id"]
    delete(conn, "people", r0_id)

    r1_id = insert(
        conn, "people", {"x": "a", "y": "b"})["id"]
    update(conn, "people", r1_id, {"y": "b1"})

    s1_id = insert(conn, "memberships", {
        "y": "b", "z": "c"})["id"]
    update(conn, "memberships", s1_id, {"y": "b1"})

    s3_id = insert(conn, "memberships", {
        "y": "b1", "z": "d"})["id"]
    s4_id = update(conn, "memberships", s3_id, {"z": "d1"})["id"]

    delete(conn, "memberships", s4_id)

    print("test_seeding")


def test_classic():
    """The frame of reference"""
    print("test_classic")
    conn = get_connection()
    cur = conn.cursor()

    test_seeding()

    cur.execute(
        """
        SELECT r.x, r.y
        FROM people AS r
        JOIN memberships AS s ON r.y = s.y
        WHERE r.death = 'infinity' AND s.death = 'infinity'
        GROUP BY r.x, r.y
        """
    )

    result = print_query_results(cur)
    expected = [('a', 'b1')]
    validate(result, expected)


def test_annotate():
    print("test_annotate")
    conn = get_connection()
    cur = conn.cursor()
    truncate_tables(conn)

    insert(conn, "people", {"x": "b_before", "y": "b_before"})
    tmp_id = insert(conn, "people", {"x": "d_before", "y": "b_before"})["id"]
    delete(conn, "people", tmp_id)

    window_start = datetime.datetime.now(datetime.timezone.utc)

    test_seeding()

    window_end = datetime.datetime.now(datetime.timezone.utc)

    insert(conn, "people", {"x": "b_after", "y": "b_after"})

    columns = get_table_columns_clean(conn, 'people')

    my_query = Rewriter.scan("people", columns, window_start, window_end)
    cur.execute(my_query)
    result = print_query_results(cur)


def test_join():
    print("test_join")
    conn = get_connection()
    cur = conn.cursor()
    truncate_tables(conn)

    window_start = datetime.datetime.now(datetime.timezone.utc)
    test_seeding()
    window_end = datetime.datetime.now(datetime.timezone.utc)

    # check()

    # --- run test query ---

    columns_people = get_table_columns_clean(conn, 'people')
    columns_memberships = get_table_columns_clean(conn, 'memberships')

    my_query = Rewriter.build_cte([
        ("step1", Rewriter.scan("memberships",
         columns_memberships, window_start, window_end)),
        ("step2", Rewriter.scan("people", columns_people, window_start, window_end)),
        ("step3", Rewriter.join("step2", columns_people,
         "step1", columns_memberships, "t2.y = t1.y")),
        ("final", Rewriter.aggregate(
            "step3", ["t1_x", "t1_y"]))
    ], "SELECT * FROM final")

    cur.execute(my_query)
    print_query_results(cur)

    print("run_test")


def print_query_results(cur, limit=None):
    column_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall() if limit is None else cur.fetchall()[:limit]
    print(column_names)
    for row in rows:
        print(row)
    return rows


COMMANDS = {
    "reset": reset,
    "check": check,
    "test_seeding": test_seeding,
    "test_classic": test_classic,
    "test_annotate": test_annotate,
    "test_join": test_join,
    # "test_positive": test_positive,
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
