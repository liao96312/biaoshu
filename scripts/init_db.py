from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        return 2
    try:
        import psycopg
    except ImportError:
        print("psycopg is not installed. Install postgres extras before running this script.")
        return 2

    schema = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    sql = schema.read_text(encoding="utf-8")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
    print(f"Initialized database schema from {schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
