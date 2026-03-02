#!/usr/bin/env python3
"""
Create DB tables and ingest CISA KEV into the database.

Run from the backend directory:
  python scripts/init_and_ingest_kev.py

Requires DATABASE_URL (e.g. in .env) and a running PostgreSQL instance.
"""

import asyncio
import sys

# Add backend to path so "app" resolves when run as script
sys.path.insert(0, ".")


async def main() -> None:
    """Initialize DB and ingest KEV into the database."""

    from app.db.engine import (  # pylint: disable=import-outside-toplevel
        AsyncSessionLocal,
        close_db,
        init_db,
    )
    from app.ingestors.cisa_kev import ingest_cisa_kev  # pylint: disable=import-outside-toplevel

    await init_db()
    try:
        async with AsyncSessionLocal() as session:  # type: ignore[reportGeneralTypeIssues]
            n = await ingest_cisa_kev(session)
            print(f"KEV ingest complete: {n} KEV entries (new or updated).")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
