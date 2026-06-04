import argparse
import datetime
import demo_db
from ast_rewriter import rewrite_sql

QUERY = """
        SELECT r.x, r.y
        FROM people AS r
        JOIN memberships AS s ON r.y = s.y
        GROUP BY r.x, r.y
        """


def reset():
    """Reset the demo database (schema and data)."""
    conn = demo_db.get_connection()
    demo_db.setup(conn, reset=True)
    print("Demo database reset and recreated.")


def setup():
    """Seed the demo database with sample data, utilizing faked timestamps."""
    conn = demo_db.get_connection()

    print("Seeding sample data...")

    # # Example 1 - 2023
    # demo_db.set_time(conn, '2023-01-01 10:00:00Z')
    # demo_db.insert(conn, "people", {"x": "a", "y": "b"})

    # demo_db.set_time(conn, '2023-01-02 10:00:00Z')
    # demo_db.insert(conn, "memberships", {"y": "b", "z": "c"})

    # demo_db.set_time(conn, '2023-01-03 10:00:00Z')
    # demo_db.delete(conn, "people", {"x": "a", "y": "b"})

    # demo_db.set_time(conn, '2023-01-04 10:00:00Z')
    # demo_db.delete(conn, "memberships", {"y": "b", "z": "c"})

    # demo_db.set_time(conn, '2023-01-05 10:00:00Z')
    # demo_db.insert(conn, "people", {"x": "a", "y": "b"})

    # demo_db.set_time(conn, '2023-01-06 10:00:00Z')
    # demo_db.insert(conn, "memberships", {"y": "b", "z": "c"})

    # Example 2 2024-2025
    demo_db.set_time(conn, '2024-01-06 10:00:00Z')
    demo_db.insert(conn, "memberships", {"y": "b1", "z": "e"})

    demo_db.set_time(conn, '2025-01-01 10:00:00Z')
    demo_db.insert(conn, "people", {"x": "a", "y": "b"})

    demo_db.set_time(conn, '2025-01-02 10:00:00Z')
    demo_db.delete(conn, "people", {"x": "a", "y": "b"})

    demo_db.set_time(conn, '2025-01-03 10:00:00Z')
    demo_db.insert(conn, "people", {"x": "a", "y": "b1"})

    demo_db.set_time(conn, '2025-01-04 10:00:00Z')
    demo_db.insert(conn, "memberships", {"y": "b", "z": "c"})

    demo_db.set_time(conn, '2025-01-05 10:00:00Z')
    demo_db.update(conn, "memberships", {"y": "b", "z": "c"}, {"y": "b1"})

    demo_db.set_time(conn, '2025-01-05 10:00:00Z')
    demo_db.insert(conn, "memberships", {"y": "b1", "z": "d"})

    demo_db.set_time(conn, '2025-01-06 10:00:00Z')
    demo_db.delete(conn, "memberships", {"y": "b1", "z": "d"})

    # Stop faking time
    demo_db.reset_time(conn)
    print("Demo database seeded successfully.")


def run_query():
    """Run a sample query against the demo database."""
    conn = demo_db.get_connection()
    cur = conn.cursor()

    # rewritten_query = rewrite_sql(QUERY, window_start="2023-01-01 00:00:00Z", window_end="2023-12-31 23:59:59Z", schema={
    #     "people": ["x", "y"],
    #     "memberships": ["y", "z"]
    # })
    rewritten_query = rewrite_sql(QUERY, window_start="2024-12-01 00:00:00Z", window_end="2025-12-31 23:59:59Z", schema={
        "people": ["x", "y"],
        "memberships": ["y", "z"]
    })

    cur.execute(rewritten_query)
    return cur.fetchall(), [desc[0] for desc in cur.description]
    # results = cur.fetchall()
    # print("Query Results:")
    # print(type(results))
    # print(results)
    # for row in results:
    #     print(row)
    #     print(type(row))


def full_provenance():
    """Run a full provenance demonstration, showing the annotations for each result."""
    result, column_names = run_query()
    # print(result)
    print(column_names)
    for row in result:
        print(row)
    return result


def pos_neg_blame():
    """Run a positive/negative query demonstration."""
    result, column_names = run_query()
    # print(result)
    cleaned_results = []
    for row in result:
        *cols, annotation = row

        blames = []
        if any(
            lineage[-1]['interval'][1] == 'infinity'
            for lineage in annotation
        ):
            cols.insert(0, "+")
            for lineage in annotation:
                if lineage[-1]['interval'][1] == 'infinity':
                    blames.append(lineage[-1]['birth'])
        else:
            cols.insert(0, "-")
            for lineage in annotation:
                blames.append(lineage[-1]['death'])
        cols.append(blames)
        cleaned_results.append(cols)
    # print(column_names)
    print(["exists"] + column_names[:-1] + ["blame"])
    for row in cleaned_results:
        print(row)
    return cleaned_results


def pos_neg():
    """Run a positive/negative query demonstration."""
    result, column_names = run_query()
    # print(result)
    cleaned_results = []
    for row in result:
        *cols, annotation = row

        if any(
            lineage[-1]['interval'][1] == 'infinity'
            for lineage in annotation
        ):
            cols.insert(0, "+")
        else:
            cols.insert(0, "-")
        cleaned_results.append(cols)
    # print(column_names)
    print(["exists"] + column_names[:-1])
    for row in cleaned_results:
        print(row)
    return cleaned_results


def classic():
    """Run a classic query demonstration."""
    result, column_names = run_query()
    print(result)
    cleaned_results = []
    for row in result:
        *cols, annotation = row

        if any(
            lineage[-1]['interval'][1] == 'infinity'
            for lineage in annotation
        ):
            cleaned_results.append(cols)
    # print(column_names)
    print(column_names[:-1])
    for row in cleaned_results:
        print(row)
    return cleaned_results


def check():
    conn = demo_db.get_connection()
    overview = demo_db.get_db_overview(conn, 20)
    for table in overview:
        print(f"Schema: {table['schema']}, Table: {table['table']}")
        print("Columns:", table['columns'])
        print("Rows:")
        for row in table['rows']:
            print("  ", row)
    print("check")


COMMANDS = {
    "reset": reset,
    "setup": setup,
    "check": check,
    "classic": classic,
    "pos_neg": pos_neg,
    "pos_neg_blame": pos_neg_blame,
    "full_provenance": full_provenance
}


def main():
    parser = argparse.ArgumentParser(description="Run the demo program.")
    parser.add_argument("command", choices=COMMANDS.keys(),
                        help="The command to run.")
    args = parser.parse_args()

    if args.command in COMMANDS:
        COMMANDS[args.command]()


if __name__ == "__main__":
    main()
