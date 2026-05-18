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


def test_seeding():
    conn = get_connection()

    # optional
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


def validate(result, expected):
    if result == expected:
        print("PASS")
    else:
        print("FAIL")
        print("Expected:", expected)


def test_positive():
    """Make time travel work, 3 cases:
    1) x = a included: birth before window_end and no death
    2) x = a1 not included: birth after window_end
    3) x = a2 included: death after window_end
    """
    print("test_positive")
    conn = get_connection()
    cur = conn.cursor()
    test_seeding()

    # insert x = a2
    tmp_id = insert(conn, "people", {"x": "a2", "y": "b1"})["id"]

    # set window_end to now
    window_end = datetime.datetime.now(datetime.timezone.utc)

    # x = a1
    insert(conn, "people", {"x": "a1", "y": "b1"})

    # test the death after window_end case
    delete(conn, "people", tmp_id)

    cur.execute(
        """
        SELECT r.x, r.y
        FROM people AS r
        JOIN memberships AS s ON r.y = s.y
        WHERE r.death > %s
            AND r.birth <= %s
            AND s.death > %s
            AND s.birth <= %s
        GROUP BY r.x, r.y
        """, (window_end, window_end, window_end, window_end))

    result = print_query_results(cur)
    expected = [('a2', 'b1'), ('a', 'b1')]
    validate(result, expected)


# def run_test():
#     conn = get_connection()
#     cur = conn.cursor()

#     reset()

#     # --- seed data ---
#     insert(conn, "memberships", {"y": "b1", "z": "e"})

#     r0_id = insert(
#         conn, "people", {"x": "a", "y": "b"})
#     delete(conn, "people", r0_id)

#     r1_id = insert(
#         conn, "people", {"x": "a", "y": "b"})
#     update(conn, "people", r1_id, {"y": "b1"})

#     s1_id = insert(conn, "memberships", {
#         "y": "b", "z": "c"})
#     update(conn, "memberships", s1_id, {"y": "b1"})

#     s3_id = insert(conn, "memberships", {
#         "y": "b1", "z": "d"})
#     s4_id = update(conn, "memberships", s3_id, {"z": "d1"})

#     delete(conn, "memberships", s4_id)

#     # check()

#     # --- run test query ---
#     columns_people = get_table_columns_no_annotation(conn, 'people')
#     columns_memberships = get_table_columns_no_annotation(conn, 'memberships')

#     columns_people_no_id_annotation = get_table_columns_no_id_annotation(
#         conn, 'people')
#     columns_memberships_no_id_annotation = get_table_columns_no_id_annotation(
#         conn, 'memberships')

#     my_query = Rewriter.build_cte([
#         ("step1", Rewriter.scan("memberships", columns_memberships, "2", "99")),
#         ("step2", Rewriter.scan("people", columns_people, "2", "99")),
#         ("step3", Rewriter.join("step2", columns_people_no_id_annotation,
#          "step1", columns_memberships_no_id_annotation, "t1.y = t2.y")),
#         ("final", Rewriter.aggregate_min(
#             "step3", ["t1_x", "t1_y"]))
#     ], "SELECT * FROM final")

#     cur.execute(my_query)
#     print_query_results(cur)

#     print("run_test")


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
    # "run_test": run_test,
    "test_seeding": test_seeding,
    "test_classic": test_classic,
    "test_positive": test_positive,
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
