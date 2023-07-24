from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, cast

from aiogram import Router, types
from aiogram.filters import Command
from dependency_injector.wiring import Provide, inject

from naualertsbot.models import AlarmType, Alert, Status
from naualertsbot.stats import get_stats
from naualertsbot.texts import get_text

if TYPE_CHECKING:
    from aiogram import Bot
    from dependency_injector.providers import Configuration

    from naualertsbot.services.alerts import AlertsService

logger = getLogger(__name__)

router = Router()
IMGFILE = types.FSInputFile("assets/map.jpg")

DEBUG_PUSH_ALLOWED = False

if DEBUG_PUSH_ALLOWED:
    debug_types = {"push", "message"}
else:
    debug_types = {"message"}


@router.message(Command("trigger"))
@inject
async def trigger(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
    alerts_service: "AlertsService" = Provide["services.alerts"],
    config: "Configuration" = Provide["bot_context.config"],
) -> None:
    """Trigger alert.

    Args:
        message: Message instance.
        bot: Bot instance.
        alerts_service: Alerts service instance.
        config: Bot configuration instance.
    """
    if not message.from_user:
        return

    if message.from_user.id not in cast(list[int], config["admins"]):
        return

    if not message.text:
        return

    args = message.text.split(" ")

    if len(args) != 4:
        await message.answer("Неправильний формат команди")
        return

    alert_status = args[1]
    alarm_type = args[2]
    debug_type = args[3]

    if debug_type not in debug_types:
        await message.answer("Invalid debug type")
        return

    if debug_type == "push":
        await alerts_service.trigger_alert(
            Alert(
                status=Status(alert_status),
                regionId=alerts_service.region,
                alarmType=AlarmType(alarm_type),
                createdAt=datetime.utcnow(),
            ),
        )
        return

    try:
        alert = Alert(
            status=Status(alert_status),
            regionId=alerts_service.region,
            alarmType=AlarmType(alarm_type),
            createdAt=datetime.utcnow(),
        )
    except ValueError:
        await message.answer("Invalid alert type")
        return

    if alert.status == Status.ACTIVATE:
        await bot.send_photo(
            message.chat.id,
            IMGFILE,
            caption=get_text(alert, None),
        )
    else:
        await bot.send_message(
            message.chat.id,
            get_text(alert, None),
        )


@router.message(Command("stats"))
@inject
async def stats(
    message: types.Message,
    config: "Configuration" = Provide["bot_context.config"],
) -> None:
    """Get stats.

    Args:
        message: Message instance.
        config: Bot configuration instance.
    """
    if not message.from_user:
        return

    if message.from_user.id not in cast(list[int], config["admins"]):
        return

    chat_stats = await get_stats()

    lines: list[str] = []

    for chat_stat in chat_stats.values():
        lines.append(f"- <b>{chat_stat.name}</b> (<code>{chat_stat.chat_id}</code>): ")
        lines.append(f"  | <b>Учасників:</b> <code>{chat_stat.members}</code>")
        if chat_stat.username:
            username = f"@{chat_stat.username}"
        else:
            username = "<i>немає</i>"
        lines.append(f"  | <b>Нік:</b> {username}")
        lines.append(f"  | <b>Адмін:</b> <code>{chat_stat.admin_rights}</code>")
        lines.append("")

    await message.answer("\n".join(lines))
