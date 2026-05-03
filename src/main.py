import argparse
from db import get_connection, setup, get_db_overview
from log import ingest_log_files


def reset():
    conn = get_connection()
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


def ingest_logs():
    conn = get_connection()
    counts = ingest_log_files(conn)
    for file_name, count in counts.items():
        print(f"{file_name}: {count} lines ingested")
    print("ingest_logs")


COMMANDS = {
    "reset": reset,
    "check": check,
    "ingest_logs": ingest_logs
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
