from __future__ import annotations

import os

from app.repositories.postgres import PostgresRepository


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        return 2
    repo = PostgresRepository(database_url)
    if repo.ping():
        print("PostgreSQL connection OK.")
        return 0
    print("PostgreSQL connection failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
