import asyncpg
from aiogram import BaseMiddleware
from aiogram.types import Update


class DedupMiddleware(BaseMiddleware):
    """Один update_id обрабатывается один раз на все реплики бота."""

    async def __call__(self, handler, event: Update, data):
        pool: asyncpg.Pool = data["pool"]
        data["update_id"] = event.update_id
        async with pool.acquire() as conn:
            inserted = await conn.fetchval(
                """
                INSERT INTO processed_updates (update_id)
                VALUES ($1)
                ON CONFLICT DO NOTHING
                RETURNING update_id
                """,
                event.update_id,
            )
        if inserted is None:
            return None
        try:
            return await handler(event, data)
        except Exception:
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM processed_updates WHERE update_id = $1",
                    event.update_id,
                )
            raise
