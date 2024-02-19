import asyncio
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, Any

import pytz
from aiogram import types
from aiogram.exceptions import TelegramForbiddenError, TelegramMigrateToChat
from dependency_injector.wiring import Provide, inject

from naualertsbot.models import WeekNumber
from naualertsbot.stats import migrate_chat, update_stats
from naualertsbot.utils import check_settings

if TYPE_CHECKING:
    from aiogram import Bot
    from redis.asyncio import Redis


logger = getLogger(__name__)


def get_current_date() -> datetime:
    """Get current date.

    Returns:
        Current date.
    """
    return datetime.now(pytz.timezone("Europe/Kiev"))


def get_week_number(date: datetime) -> int:
    """Get current week number.

    Args:
        date: Date.

    Returns:
        Week number.
    """
    return date.isocalendar()[1]


def get_studying_week_number(date: datetime, invert: bool = False) -> WeekNumber:
    """Get current studying week number.

    Args:
        date: Date.
        invert: Invert week number.

    Returns:
        Week number.
    """
    week_number = date.isocalendar()[1]
    return WeekNumber((week_number + 1 * invert) % 2 + 1)  # noqa: WPS345


class WeeksService:  # noqa: WPS306
    def __init__(self: "WeeksService") -> None:
        """Initialize service."""
        self._shutting_down = False

    async def run(
        self: "WeeksService",
    ) -> None:
        """Run service."""
        logger.info("Waiting for new week")

        last_week_number = get_week_number(get_current_date())
        while not self._shutting_down:
            date = get_current_date()
            week_number = get_week_number(date)
            if week_number != last_week_number:
                if await check_settings("weeks"):
                    await self._send_week(await self.get_week_number())
                else:
                    logger.info(
                        "Got new week, but weeks notifications are disabled by global settings",
                    )
                last_week_number = week_number
            await asyncio.sleep(1)

    async def shutdown(self: "WeeksService") -> None:
        """Shutdown service."""
        logger.info("Shutting down weeks service")
        self._shutting_down = True

    @inject
    async def get_week_number(
        self: "WeeksService",
        redis: "Redis[Any]" = Provide["db.redis"],
    ) -> WeekNumber:
        """Get current week number.

        Args:
            redis: Redis client.

        Returns:
            Current week number.
        """
        invert = await redis.get("invert_weeks")
        if invert is None:
            invert = False
        else:
            invert = bool(int(invert))

        return get_studying_week_number(get_current_date(), invert)

    @inject
    async def toggle_invert(
        self: "WeeksService",
        redis: "Redis[Any]" = Provide["db.redis"],
    ) -> bool:
        """Toggle invert weeks.

        Args:
            redis: Redis client.

        Returns:
            Current invert weeks value.
        """
        invert = await redis.get("invert_weeks")
        if invert is None:
            invert = False
        else:
            invert = bool(int(invert))

        await redis.set("invert_weeks", int(not invert))
        return not invert

    @inject
    async def _send_week(
        self: "WeeksService",
        week_number: WeekNumber,
        bot: "Bot" = Provide["bot_context.bot"],
        redis: "Redis[Any]" = Provide["db.redis"],
    ) -> None:
        text = (
            f"🚩 <b>З понеділка починається {week_number.value}-й тиждень</b>\n"
            "\n"
            "\n"
            "⚙️ <i>Щоб вимкнути сповіщення у ніч перед понеділком - використовуйте "
            "команду /settings.</i>\n"
            "\n"
            "• • • • • • • • • • • • • • • • • • •\n"
            "🤖 Надіслано ботом <b>@naualerts_bot</b>\n"
        )
        for chat_id in await redis.smembers("subscribers:weeks"):
            try:
                await bot.send_message(chat_id, text)
            except TelegramMigrateToChat as err:
                logger.info("Chat %s migrated to %s", chat_id, err.migrate_to_chat_id)
                await migrate_chat(chat_id, err.migrate_to_chat_id)
                await redis.srem("subscribers:weeks", chat_id)
                await redis.sadd("subscribers:weeks", err.migrate_to_chat_id)
                await bot.send_message(err.migrate_to_chat_id, text)
            except TelegramForbiddenError:
                logger.info("Chat %s blocked bot", chat_id)
                await redis.srem("subscribers:alerts", chat_id)
                await redis.srem("subscribers:weeks", chat_id)
                await update_stats(types.Chat(id=chat_id, type="supergroup"))
            await asyncio.sleep(0.5)
