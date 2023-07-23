import asyncio
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, Any

import pytz
from dependency_injector.wiring import Provide, inject

from airalertbot.models import WeekNumber

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
                await self._send_week(await self.get_week_number())
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
            f"❇️ Починається {week_number.value}-й тиждень\n"
            "\n"
            "• • • • • • • • • • • • • • • • • • •\n"
            "⏰ Початок та кінець пар:\n"
            "• 1 пара - 8.00 - 9.35\n"
            "• 2 пара - 9.50 - 11.25\n"
            "• 3 пара - 11.40 - 13.15\n"
            "• 4 пара - 13.30 - 15.05\n"
            "• 5 пара - 15.20 - 16.55\n"
            "• 6 пара - 17.10 - 18.45\n"
        )
        for chat_id in await redis.smembers("subscribers"):
            await bot.send_message(chat_id, text)
