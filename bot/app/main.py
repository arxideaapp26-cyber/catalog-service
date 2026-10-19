import asyncio
import logging

import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.handlers import router
from app.middleware import DedupMiddleware
from app.settings import Settings
from app.storage import ObjectStorage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("catalog-bot")

LEADER_LOCK = 81002
HEALTH_PORT = 8080


async def wait_schema(pool: asyncpg.Pool) -> None:
    for _ in range(40):
        try:
            await pool.fetchval("SELECT 1 FROM products LIMIT 1")
            return
        except Exception:
            await asyncio.sleep(1)
    raise SystemExit("Схема базы не готова. Сначала должен подняться API.")


async def health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def open_pool(settings: Settings) -> asyncpg.Pool:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            return await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1)
    raise RuntimeError("База недоступна") from last_error


async def open_bucket(storage: ObjectStorage) -> None:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            await asyncio.to_thread(storage.ensure_bucket)
            return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1)
    raise RuntimeError("MinIO недоступен") from last_error


def build_dispatcher(settings: Settings) -> Dispatcher:
    dispatcher = Dispatcher(settings=settings)
    dispatcher.update.outer_middleware(DedupMiddleware())
    dispatcher.include_router(router)
    return dispatcher


async def prepare(settings: Settings, dispatcher: Dispatcher) -> asyncpg.Pool:
    pool = await open_pool(settings)
    await wait_schema(pool)
    storage = ObjectStorage(settings)
    await open_bucket(storage)
    dispatcher.workflow_data["pool"] = pool
    dispatcher.workflow_data["object_storage"] = storage
    return pool


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть каталог"),
            BotCommand(command="create", description="Создать товар"),
        ]
    )


async def run_polling(settings: Settings) -> None:
    dispatcher = build_dispatcher(settings)
    await prepare(settings, dispatcher)
    leader = await asyncpg.connect(settings.database_url)
    locked = await leader.fetchval("SELECT pg_try_advisory_lock($1)", LEADER_LOCK)

    app = web.Application()
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", HEALTH_PORT).start()

    if not locked:
        await leader.close()
        log.info("Опрос уже ведёт другой инстанс. Этот отвечает только на /health.")
        while True:
            await asyncio.sleep(3600)

    bot = Bot(settings.bot_token)
    await set_commands(bot)
    log.info("Бот читает события через getUpdates.")
    await dispatcher.start_polling(bot)


def run_webhook(settings: Settings) -> None:
    if not settings.webhook_secret:
        raise SystemExit("Для webhook задайте один WEBHOOK_SECRET на все реплики.")
    if not settings.webhook_url.endswith("/webhook"):
        raise SystemExit("WEBHOOK_URL должен заканчиваться на /webhook.")

    bot = Bot(settings.bot_token)
    dispatcher = build_dispatcher(settings)

    async def on_startup(bot: Bot) -> None:
        await prepare(settings, dispatcher)
        await set_commands(bot)
        await bot.set_webhook(
            settings.webhook_url,
            secret_token=settings.webhook_secret,
            drop_pending_updates=False,
        )
        log.info("Webhook установлен: %s", settings.webhook_url)

    dispatcher.startup.register(on_startup)
    app = web.Application()
    app.router.add_get("/health", health)
    SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=settings.webhook_secret,
    ).register(app, path="/webhook")
    setup_application(app, dispatcher, bot=bot)
    web.run_app(app, host="0.0.0.0", port=HEALTH_PORT)


def main() -> None:
    settings = Settings()
    if not settings.bot_token.strip():
        raise SystemExit("Заполните BOT_TOKEN в файле .env")
    if settings.webhook_url.strip():
        run_webhook(settings)
        return
    asyncio.run(run_polling(settings))


if __name__ == "__main__":
    main()
