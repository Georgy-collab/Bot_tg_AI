"""Telegram-бот: диалог с контекстом и команда его очистки."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, Message

from api_client import ApiError, ask
from config import (
    BOT_TOKEN,
    MAX_COMPLETION_TOKENS,
    MAX_CONTEXT_MESSAGES,
    MODEL,
    missing_settings,
    proxy_label,
    telegram_proxy,
)
from context_manager import ContextManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("bot")

context = ContextManager(MAX_CONTEXT_MESSAGES)
dialog_lock = asyncio.Lock()
RESET_TEXT = "очистить контекст"
STATUS_TEXT = "справка"


def split_text(text: str, limit: int = 4000) -> list[str]:
    return [text[index : index + limit] for index in range(0, len(text), limit)] or [text]


async def send_text(message: Message, text: str) -> None:
    for part in split_text(text):
        await message.answer(part)


async def start(message: Message) -> None:
    name = message.from_user.first_name if message.from_user and message.from_user.first_name else ""
    greeting = f"Привет, {name}!" if name else "Привет!"
    await message.answer(
        f"{greeting}\n"
        "Напишите сообщение, и я отвечу с учётом предыдущих реплик этого чата.\n"
        "Контекст хранится в памяти, пока бот запущен. "
        f"В запрос попадают только последние {MAX_CONTEXT_MESSAGES} сообщений.\n"
        "Справка по диалогу: /context или «справка».\n"
        "Очистить историю: /reset или «очистить контекст»."
    )


async def context_status(message: Message) -> None:
    chat_id = message.chat.id
    async with dialog_lock:
        total, user_count, assistant_count, characters = context.stats(chat_id)
        limit = context.limit

    lines = [
        "Справка по диалогу",
        f"Сообщений в истории: {total} из {limit}",
        f"Ваших сообщений: {user_count}",
        f"Ответов бота: {assistant_count}",
        f"Символов в истории: {characters}",
        f"Модель: {MODEL}",
        f"Лимит ответа: {MAX_COMPLETION_TOKENS} токенов",
    ]
    if total == 0:
        lines.append("История пустая. Напишите сообщение, чтобы начать.")
    elif total >= limit:
        lines.append("Лимит заполнен: самые старые сообщения уже удалены.")
    else:
        lines.append(f"До удаления старых сообщений осталось мест: {limit - total}.")
    await message.answer("\n".join(lines))


async def reset(message: Message) -> None:
    chat_id = message.chat.id
    async with dialog_lock:
        context.reset(chat_id)
    logger.info("Контекст очищен: chat_id=%s", chat_id)
    await message.answer("Контекст очищен. Следующее сообщение начнёт новый диалог.")


async def dialog(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    if text.casefold() == RESET_TEXT:
        await reset(message)
        return
    if text.casefold() == STATUS_TEXT:
        await context_status(message)
        return

    chat_id = message.chat.id
    async with dialog_lock:
        stored = len(context.history(chat_id))
        messages = context.for_request(chat_id, text)
        dropped = stored + 1 - len(messages)
        if dropped:
            logger.info(
                "Из запроса удалены старые сообщения: chat_id=%s, удалено=%s",
                chat_id,
                dropped,
            )
        logger.info("Новое сообщение: chat_id=%s, сообщений в запросе=%s", chat_id, len(messages))
        try:
            answer = await asyncio.to_thread(ask, messages)
        except ApiError as error:
            logger.error("Ошибка диалога: chat_id=%s, %s", chat_id, error)
            await message.answer(str(error))
            return
        removed = context.add(chat_id, "user", text) + context.add(chat_id, "assistant", answer)
        if removed:
            logger.info(
                "Из истории удалены старые сообщения: chat_id=%s, удалено=%s, осталось=%s",
                chat_id,
                removed,
                len(context.history(chat_id)),
            )

    await send_text(message, answer)


async def main() -> None:
    missing = missing_settings()
    if missing:
        logger.error("В .env не заданы: %s", ", ".join(missing))
        raise SystemExit(f"В .env не заданы: {', '.join(missing)}")

    proxy = telegram_proxy()
    session = AiohttpSession(proxy=proxy) if proxy else AiohttpSession()
    if proxy:
        logger.info("Telegram через прокси %s", proxy_label(proxy))
    else:
        logger.info("Telegram без прокси")

    bot = Bot(BOT_TOKEN, session=session)
    dispatcher = Dispatcher()
    dispatcher.message.register(start, CommandStart())
    dispatcher.message.register(reset, Command("reset"))
    dispatcher.message.register(context_status, Command("context"))
    dispatcher.message.register(dialog, F.text)

    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Что умеет бот"),
                BotCommand(command="context", description="Справка по диалогу"),
                BotCommand(command="reset", description="Очистить контекст"),
            ]
        )
        logger.info("Бот запущен")
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
