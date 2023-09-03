import shlex
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, Any, cast

from aiogram import Router, types
from aiogram.filters import Command
from dependency_injector.wiring import Provide, inject

from naualertsbot.models import AlarmType, Alert, Status
from naualertsbot.stats import get_pm_stats, get_stats
from naualertsbot.texts import get_text

if TYPE_CHECKING:
    from aiogram import Bot
    from dependency_injector.providers import Configuration
    from redis.asyncio import Redis

    from naualertsbot.services.alerts import AlertsService

logger = getLogger(__name__)

router = Router()
IMGFILE = types.FSInputFile("assets/map.jpg")

PAGER_MAX_PAGES = 25

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
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Get stats.

    Args:
        message: Message instance.
        config: Bot configuration instance.
        redis: Redis instance.
    """
    if not message.from_user:
        return

    if message.from_user.id not in cast(list[int], config["admins"]):
        return

    if not message.text:
        return

    match shlex.split(message.text.strip().lower())[1:]:
        case ["chat"]:
            await _send_chat_stats(message)
            return
        case ["pm"]:
            await _send_pm_stats(message)
            return
        case _:
            pass  # noqa: WPS420

    chat_stats = await get_stats()
    pm_stats = await get_pm_stats()

    alerts_subscription_count = await redis.scard("subscribers:alerts")
    weeks_subscription_count = await redis.scard("subscribers:weeks")

    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👤 <b>Приватні чати:</b> <code>{len(pm_stats)}</code>"
        f"👥 <b>Групи:</b> <code>{len(chat_stats)}</code>\n"
        "\n"
        "🔔 <b>Підписки:</b>\n"
        f"  | <b>Тривога:</b> <code>{alerts_subscription_count}</code>\n"
        f"  | <b>Тижні:</b> <code>{weeks_subscription_count}</code>\n",
    )


@inject
async def _send_chat_stats(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
) -> None:
    """Send chat stats.

    Args:
        message: Message instance.
        bot: Bot instance.
    """
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

    if not lines:
        lines.append("Немає активних груп")

    if len(lines) > PAGER_MAX_PAGES:
        chunks = [
            lines[i : i + PAGER_MAX_PAGES]  # noqa: E203
            for i in range(0, len(lines), PAGER_MAX_PAGES)  # noqa: WPS111
        ]
        for chunk in chunks:
            await message.answer("\n".join(chunk))
    else:
        await message.answer("\n".join(lines))


@inject
async def _send_pm_stats(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
) -> None:
    """Send PM stats.

    Args:
        message: Message instance.
        bot: Bot instance.
    """
    pm_stats = await get_pm_stats()

    lines: list[str] = []

    for pm_stat in pm_stats.values():
        lines.append(f"- <b>{pm_stat.name}</b> (<code>{pm_stat.chat_id}</code>): ")
        if pm_stat.username:
            username = f"@{pm_stat.username}"
        else:
            username = "<i>немає</i>"
        lines.append(f"  | <b>Нік:</b> {username}")
        lines.append(f"  | <b>Ім'я:</b> {pm_stat.name}")
        lines.append("")

    if not lines:
        lines.append("Немає активних приватних чатів")

    if len(lines) > PAGER_MAX_PAGES:
        chunks = [
            lines[i : i + PAGER_MAX_PAGES]  # noqa: E203
            for i in range(0, len(lines), PAGER_MAX_PAGES)  # noqa: WPS111
        ]
        for chunk in chunks:
            await message.answer("\n".join(chunk))
    else:
        await message.answer("\n".join(lines))
