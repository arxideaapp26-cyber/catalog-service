import asyncio
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.db import migrate
from app.settings import Settings
from app.storage import ObjectStorage

settings = Settings()


class ProductOut(BaseModel):
    id: int
    title: str
    image_url: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await _connect()
    storage = ObjectStorage(settings)
    await migrate(pool)
    await asyncio.to_thread(storage.ensure_bucket)
    app.state.pool = pool
    app.state.storage = storage
    yield
    await pool.close()


app = FastAPI(title="Каталог", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/products", response_model=list[ProductOut])
async def list_products() -> list[ProductOut]:
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title
            FROM products
            ORDER BY created_at DESC, id DESC
            """
        )
    base = settings.public_base
    return [
        ProductOut(
            id=row["id"],
            title=row["title"],
            image_url=f"{base}/products/{row['id']}/image",
        )
        for row in rows
    ]


@app.get("/products/{product_id}/image")
async def product_image(product_id: int) -> Response:
    async with app.state.pool.acquire() as conn:
        key = await conn.fetchval(
            "SELECT image_key FROM products WHERE id = $1",
            product_id,
        )
    if key is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    try:
        payload = await asyncio.to_thread(app.state.storage.download, key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Файл не найден") from exc
    return Response(content=payload, media_type="image/jpeg")


async def _connect() -> asyncpg.Pool:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            return await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1)
    raise RuntimeError("База недоступна") from last_error
