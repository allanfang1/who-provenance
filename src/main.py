import argparse
from db import get_connection, setup, get_db_overview, insert, update, delete
# from log import ingest_log_files, delete_log_files, drop_log_table


def reset():
    conn = get_connection()
    # delete_log_files()
    # drop_log_table(conn)
    setup(conn, reset=True)
    print("reset")


def check():
    conn = get_connection()
    overview = get_db_overview(conn)
    for table in overview:
        print(f"Schema: {table['schema']}, Table: {table['table']}")
        print("Columns:", table['columns'])
        print("Rows:")
        for row in table['rows']:
            print("  ", row)
    print("check")


def test_insert():
    conn = get_connection()
    cur = conn.cursor()
    print(insert(cur, "people", {
          "name": "Alice", "email": "alice@example.com"}))
    print(insert(cur, "people", {"name": "Bob", "email": "bob@example.com"}))
    print("test_insert")


def test_update():
    conn = get_connection()
    cur = conn.cursor()
    print(update(cur, "people", 1, {"name": "Alison"}))
    print("test_update")


def test_delete():
    conn = get_connection()
    cur = conn.cursor()
    print(delete(cur, "people", 2))
    print("test_delete")

# def ingest_logs():
#     conn = get_connection()
#     counts = ingest_log_files(conn)
#     for file_name, count in counts.items():
#         print(f"{file_name}: {count} lines ingested")
#     print("ingest_logs")


COMMANDS = {
    "reset": reset,
    "check": check,
    # "ingest_logs": ingest_logs
    "test_insert": test_insert,
    "test_update": test_update,
    "test_delete": test_delete,
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
