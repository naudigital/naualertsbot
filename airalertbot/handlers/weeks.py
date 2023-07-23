import asyncio
from contextlib import suppress
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, cast

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from dependency_injector.wiring import Provide, inject

if TYPE_CHECKING:
    from aiogram import Bot
    from dependency_injector.providers import Configuration

    from airalertbot.services.weeks import WeeksService

logger = getLogger(__name__)

router = Router()

CALENDAR_FILE = types.FSInputFile("assets/calendar.jpg")


async def delete_delayed(messages: list[types.Message], delay: int) -> None:
    """Delete messages after delay.

    Args:
        messages: List of messages to delete.
        delay: Delay in seconds.
    """
    await asyncio.sleep(delay)
    for message in messages:
        with suppress(TelegramBadRequest):
            await message.delete()


@router.message(Command("week"))
@inject
async def getweek(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
    weeks_service: "WeeksService" = Provide["services.weeks"],
) -> None:
    """Get current week number.

    Args:
        message: Message instance.
        bot: Bot instance.
        weeks_service: Weeks service instance.
    """
    if message.chat.type != "private":
        # check if bot has delete message permission
        participant = await bot.get_chat_member(
            message.chat.id,
            (await bot.me()).id,
        )
        if not participant.can_delete_messages:
            await message.answer(
                "❌ <b>Помилка!</b>\nБот не має права для видалення повідомлень.",
            )
            return

    week_number = await weeks_service.get_week_number()
    weekday = datetime.now().weekday()

    if weekday == 4:
        response = await message.answer(
            f"📒 <b>Закінчується {week_number.value}-й тиждень.</b>\n"
            "\n"
            "• • • • • • • • • • • • • • • • • • •\n"
            "⏰ Початок та кінець пар:\n"
            "• 1 пара - 8.00 - 9.35\n"
            "• 2 пара - 9.50 - 11.25\n"
            "• 3 пара - 11.40 - 13.15\n"
            "• 4 пара - 13.30 - 15.05\n"
            "• 5 пара - 15.20 - 16.55\n"
            "• 6 пара - 17.10 - 18.45\n",
        )
    elif weekday in {5, 6}:
        response = await message.answer(
            f"📒 <b>Закінчується {week_number.value}-й тиждень.</b>\n"
            f"З понеділка - {week_number.invert().value}-й.",
        )
    else:
        response = await message.answer(
            f"📗 <b>Триває {week_number.value}-й тиждень.</b>\n"
            "\n"
            "• • • • • • • • • • • • • • • • • • •\n"
            "⏰ Початок та кінець пар:\n"
            "• 1 пара - 8.00 - 9.35\n"
            "• 2 пара - 9.50 - 11.25\n"
            "• 3 пара - 11.40 - 13.15\n"
            "• 4 пара - 13.30 - 15.05\n"
            "• 5 пара - 15.20 - 16.55\n"
            "• 6 пара - 17.10 - 18.45\n",
        )

    asyncio.ensure_future(delete_delayed([message, response], 60))


@router.message(Command("calendar"))
@inject
async def getcalendar(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
) -> None:
    """Get calendar.

    Args:
        message: Message instance.
        bot: Bot instance.
    """
    if message.chat.type != "private":
        # check if bot has delete message permission
        participant = await bot.get_chat_member(
            message.chat.id,
            (await bot.me()).id,
        )
        if not participant.can_delete_messages:
            await message.answer(
                "❌ <b>Помилка!</b>\nБот не має права для видалення повідомлень.",
            )
            return

    response = await message.answer_photo(
        CALENDAR_FILE,
        caption="📅 <b>Календар II семестру 2022-2023 навчального року</b>",
    )

    asyncio.ensure_future(delete_delayed([message, response], 60))


@router.message(Command("invert_weeks"))
@inject
async def invert_weeks(
    message: types.Message,
    weeks_service: "WeeksService" = Provide["services.weeks"],
    config: "Configuration" = Provide["bot_context.config"],
) -> None:
    """Invert weeks.

    Args:
        message: Message instance.
        weeks_service: Weeks service instance.
        config: Configuration instance.
    """
    if not message.from_user:
        return

    if message.from_user.id not in cast(list[int], config["admins"]):
        return

    if not message.text:
        return

    await weeks_service.toggle_invert()
    await message.answer("✅ <b>Тижні інвертовано!</b>")
