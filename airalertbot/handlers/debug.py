from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, cast

from aiogram import Router, types
from aiogram.filters import Command
from dependency_injector.wiring import Provide, inject

from airalertbot.models import AlarmType, Alert, Status

if TYPE_CHECKING:
    from dependency_injector.providers import Configuration

    from airalertbot.services.alerts import AlertsService

logger = getLogger(__name__)

router = Router()


@router.message(Command("trigger"))
@inject
async def trigger(
    message: types.Message,
    alerts_service: "AlertsService" = Provide["services.alerts"],
    config: "Configuration" = Provide["bot_context.config"],
) -> None:
    """Trigger alert.

    Args:
        message: Message instance.
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

    await alerts_service.trigger_alert(alert)
