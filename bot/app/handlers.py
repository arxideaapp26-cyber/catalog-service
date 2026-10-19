import asyncio
import uuid
from io import BytesIO

import asyncpg
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.settings import Settings
from app.storage import ObjectStorage

router = Router()
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TITLE = 200


def catalog_keyboard(settings: Settings, user_id: int) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="Каталог", web_app=WebAppInfo(url=settings.webapp_url))]]
    if user_id in settings.admins:
        rows.append([KeyboardButton(text="Создать товар")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def invite(message: Message, settings: Settings) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await message.answer(
        "У меня есть товар",
        reply_markup=catalog_keyboard(settings, user_id),
    )


@router.message(CommandStart())
async def start(message: Message, settings: Settings) -> None:
    await invite(message, settings)


@router.message(Command("create"))
@router.message(F.text == "Создать товар")
async def ask_product(message: Message, settings: Settings, pool: asyncpg.Pool) -> None:
    user = message.from_user
    if user is None or user.id not in settings.admins:
        await invite(message, settings)
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO admin_requests (telegram_user_id)
            VALUES ($1)
            ON CONFLICT (telegram_user_id)
            DO UPDATE SET requested_at = now()
            """,
            user.id,
        )
    await message.answer("Отправьте название и фото одним сообщением.")


@router.message(F.photo)
async def save_product(
    message: Message,
    bot: Bot,
    settings: Settings,
    pool: asyncpg.Pool,
    object_storage: ObjectStorage,
    update_id: int,
) -> None:
    user = message.from_user
    if user is None or user.id not in settings.admins:
        await invite(message, settings)
        return

    title = (message.caption or "").strip()
    async with pool.acquire() as conn:
        already = await conn.fetchval(
            "SELECT id FROM products WHERE source_update_id = $1",
            update_id,
        )
        pending = await conn.fetchval(
            """
            SELECT telegram_user_id
            FROM admin_requests
            WHERE telegram_user_id = $1
              AND requested_at > now() - interval '1 day'
            """,
            user.id,
        )

    if already:
        await message.answer("Товар добавлен.", reply_markup=catalog_keyboard(settings, user.id))
        return
    if not pending:
        await message.answer("Сначала нажмите «Создать товар».")
        return
    if message.media_group_id:
        await message.answer("Нужны название и одно фото в одном сообщении.")
        return
    if not title:
        await message.answer("Нужны название и фото в одном сообщении: добавьте подпись к фото.")
        return
    if len(title) > MAX_TITLE:
        await message.answer("Название длиннее 200 символов.")
        return

    buffer = BytesIO()
    await bot.download(message.photo[-1], destination=buffer)
    payload = buffer.getvalue()
    if not payload or len(payload) > MAX_IMAGE_BYTES:
        await message.answer("Фото пустое или больше 10 МБ.")
        return

    key = f"{uuid.uuid4().hex}.jpg"
    await asyncio.to_thread(object_storage.upload_jpeg, key, payload)

    async with pool.acquire() as conn:
        async with conn.transaction():
            inserted = await conn.fetchval(
                """
                INSERT INTO products (title, image_key, source_update_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (source_update_id) DO NOTHING
                RETURNING id
                """,
                title,
                key,
                update_id,
            )
            await conn.execute(
                "DELETE FROM admin_requests WHERE telegram_user_id = $1",
                user.id,
            )
    if inserted is None:
        await message.answer("Товар добавлен.", reply_markup=catalog_keyboard(settings, user.id))
        return
    await message.answer("Товар добавлен.", reply_markup=catalog_keyboard(settings, user.id))


@router.message()
async def anything(message: Message, settings: Settings) -> None:
    await invite(message, settings)
