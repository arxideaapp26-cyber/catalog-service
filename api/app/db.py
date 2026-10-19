from pathlib import Path

import asyncpg

SCHEMA_LOCK = 81001
SCHEMA_SQL = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


async def migrate(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", SCHEMA_LOCK)
        try:
            await conn.execute(SCHEMA_SQL)
            await conn.execute(
                """
                DELETE FROM processed_updates
                WHERE processed_at < now() - interval '7 days'
                """
            )
            await conn.execute(
                """
                DELETE FROM admin_requests
                WHERE requested_at < now() - interval '1 day'
                """
            )
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", SCHEMA_LOCK)
