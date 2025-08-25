from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Set
from zoneinfo import ZoneInfo
from datetime import time

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from weather import build_moscow_weather_message


DATA_DIR = Path(__file__).parent / "data"
SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SUBSCRIBERS_FILE.exists():
        SUBSCRIBERS_FILE.write_text("[]", encoding="utf-8")


def _load_subscribers() -> Set[int]:
    _ensure_storage()
    try:
        data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
        return {int(x) for x in data}
    except Exception:
        return set()


def _save_subscribers(chat_ids: Set[int]) -> None:
    _ensure_storage()
    SUBSCRIBERS_FILE.write_text(json.dumps(sorted(chat_ids)), encoding="utf-8")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    subs = _load_subscribers()
    is_new = chat_id not in subs
    subs.add(chat_id)
    _save_subscribers(subs)
    if is_new:
        await update.effective_message.reply_text(
            "Готово! Я буду присылать погоду в Москве каждый день в 09:00 по Москве.\n"
            "Команды: /stop — отписаться, /now — прислать сейчас."
        )
    else:
        await update.effective_message.reply_text("Вы уже подписаны. Команда /stop — чтобы отписаться.")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    subs = _load_subscribers()
    if chat_id in subs:
        subs.remove(chat_id)
        _save_subscribers(subs)
        await update.effective_message.reply_text("Окей, больше не буду присылать.")
    else:
        await update.effective_message.reply_text("Вы не были подписаны.")


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        message = build_moscow_weather_message()
    except Exception as exc:
        await update.effective_message.reply_text(f"Не удалось получить погоду: {exc}")
        return
    await update.effective_message.reply_text(message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def broadcast_weather(context: ContextTypes.DEFAULT_TYPE) -> None:
    subs = _load_subscribers()
    if not subs:
        return
    try:
        message = build_moscow_weather_message()
    except Exception as exc:
        # If weather fetch failed, avoid spamming users. Log to console.
        print(f"Weather fetch failed: {exc}")
        return

    for chat_id in list(subs):
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as send_exc:
            # If bot was blocked or chat is invalid, remove from list
            print(f"Failed to send to {chat_id}: {send_exc}")
            if "Forbidden" in str(send_exc) or "chat not found" in str(send_exc).lower():
                subs.discard(chat_id)
                _save_subscribers(subs)


def schedule_daily_job(app: Application) -> None:
    # Run everyday at 09:00 Moscow time
    # PTB v21 expects a naive time here + timezone kwarg
    app.job_queue.run_daily(
        broadcast_weather,
        time=time(hour=9, minute=0),
        name="daily_weather_moscow",
        timezone=MOSCOW_TZ,
    )


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN в окружении или .env")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("now", cmd_now))

    schedule_daily_job(application)

    print("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()

