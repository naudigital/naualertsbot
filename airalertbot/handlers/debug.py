from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, cast

from aiogram import Router, types
from aiogram.filters import Command
from dependency_injector.wiring import Provide, inject

from airalertbot.models import AlarmType, Alert, Status
from airalertbot.texts import get_text

if TYPE_CHECKING:
    from aiogram import Bot
    from dependency_injector.providers import Configuration

    from airalertbot.services.alerts import AlertsService

logger = getLogger(__name__)

router = Router()
IMGFILE = types.FSInputFile("assets/map.jpg")


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

    if not message.text or len(message.text.split(" ")) != 3:
        await message.answer("Неправильний формат команди")
        return

    alert_status = message.text.split(" ")[1]
    alarm_type = message.text.split(" ")[2]

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
            caption=get_text(alert),
        )
    else:
        await bot.send_message(
            message.chat.id,
            get_text(alert),
        )
