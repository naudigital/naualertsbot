import asyncio
from logging import getLogger
from typing import TYPE_CHECKING, Any, Literal

import pytz
import yaml
from aiogram import types
from dependency_injector.wiring import Provide, inject

from airalertbot.models import Alert, Status

if TYPE_CHECKING:
    from aiogram import Bot
    from redis.asyncio import Redis

    from airalertbot.services.alerts import AlertsService


logger = getLogger(__name__)

texts: dict[str, dict[Literal["activate"] | Literal["deactivate"], str]]

with open("assets/texts.yaml") as texts_file:
    texts = yaml.safe_load(texts_file)


def get_text(model: "Alert") -> str:
    """Get text for alert.

    Args:
        model: Alert model.

    Returns:
        Text for alert.
    """
    # convert datetime to UTC+3 timezone
    utcmoment_naive = model.created_at
    utcmoment = utcmoment_naive.replace(tzinfo=pytz.utc)
    local_datetime = utcmoment.astimezone(pytz.timezone("Europe/Kiev"))

    text = texts.get(model.alarm_type.value, {}).get(
        model.status.value,
        None,
    )
    if text is None:
        text = texts["unknown"][model.status.value]

    return text.format(
        time=local_datetime.strftime("%H:%M:%S"),
    )


class WorkerService:  # noqa: WPS306
    """Worker service."""

    def __init__(
        self: "WorkerService",
    ) -> None:
        """Initialize service."""
        self._imgfile = types.FSInputFile("assets/map.jpg")
        self._shutting_down = False

    async def run(  # noqa: WPS213, WPS231
        self: "WorkerService",
        alerts_service: "AlertsService" = Provide["services.alerts"],
    ) -> None:
        """Run worker.

        Args:
            alerts_service: Alerts service instance.
        """
        logger.info("Waiting for alerts")

        while not self._shutting_down:
            alert = await alerts_service.wait_alert()
            if alert is None:
                alerts_service.processing_done()
                break

            logger.info("Got alert: %s", alert)
            await self._send_alert(alert)
            alerts_service.processing_done()

        if alerts_service.qsize < 1:
            logger.info("No more alerts, exiting")
            return

        logger.info("Sending remaining alerts")
        while True:
            try:
                alert = alerts_service.next_alert()
            except asyncio.QueueEmpty:
                break

            if alert is None:
                continue

            logger.info("Got alert: %s", alert)
            await self._send_alert(alert)
            alerts_service.processing_done()

        logger.info("Worker stopped")

    async def shutdown(self: "WorkerService") -> None:
        """Shutdown worker."""
        logger.info("Shutting down worker")
        self._shutting_down = True

    @inject
    async def _send_alert(
        self: "WorkerService",
        alert: "Alert",
        redis: "Redis[Any]" = Provide["db.redis"],
        bot: "Bot" = Provide["bot_context.bot"],
    ) -> None:
        """Send alert to all subscribed groups.

        Args:
            alert: Alert instance.
            redis: Redis client instance.
            bot: Bot instance.
        """
        text = get_text(alert)

        for chat_id in await redis.smembers("subscribers"):
            if alert.status == Status.ACTIVATE:
                await bot.send_photo(
                    chat_id,
                    self._imgfile,
                    caption=text,
                )
            else:
                await bot.send_message(
                    chat_id,
                    text,
                )
