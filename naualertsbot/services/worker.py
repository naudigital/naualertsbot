import asyncio
from logging import getLogger
from typing import TYPE_CHECKING, Any

from aiogram import types
from aiogram.exceptions import TelegramForbiddenError, TelegramMigrateToChat
from dependency_injector.wiring import Provide, inject

from naualertsbot.models import Alert, Status
from naualertsbot.stats import migrate_chat, update_stats
from naualertsbot.texts import get_text

if TYPE_CHECKING:
    from aiogram import Bot
    from redis.asyncio import Redis

    from naualertsbot.services.alerts import AlertsService


logger = getLogger(__name__)

IMGFILE = types.FSInputFile("assets/map.jpg")


class WorkerService:  # noqa: WPS306
    """Worker service."""

    def __init__(
        self: "WorkerService",
    ) -> None:
        """Initialize service."""
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
            await self._send_alert(alert, alerts_service.previous_alert)
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
            await self._send_alert(alert, alerts_service.previous_alert)
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
        previous_alert: "Alert | None",
        redis: "Redis[Any]" = Provide["db.redis"],
        bot: "Bot" = Provide["bot_context.bot"],
    ) -> None:
        """Send alert to all subscribed groups.

        Args:
            alert: Alert instance.
            previous_alert: Previous alert instance.
            redis: Redis client instance.
            bot: Bot instance.
        """
        text = get_text(alert, previous_alert)

        for chat_id in await redis.smembers("subscribers:alerts"):
            try:
                await self._send_alert_to_chat(chat_id, text, alert.status)
            except TelegramMigrateToChat as err:
                logger.info("Chat %s migrated to %s", chat_id, err.migrate_to_chat_id)
                await migrate_chat(chat_id, err.migrate_to_chat_id)
                await redis.srem("subscribers:alerts", chat_id)
                await redis.sadd("subscribers:alerts", err.migrate_to_chat_id)
                await self._send_alert_to_chat(
                    err.migrate_to_chat_id,
                    text,
                    alert.status,
                )
            except TelegramForbiddenError:
                logger.info("Chat %s blocked bot", chat_id)
                await redis.srem("subscribers:alerts", chat_id)
                await redis.srem("subscribers:weeks", chat_id)
                await update_stats(types.Chat(id=chat_id, type="supergroup"))
            await asyncio.sleep(0.5)

    @inject
    async def _send_alert_to_chat(
        self: "WorkerService",
        chat_id: int,
        text: str,
        alert_status: Status,
        bot: "Bot" = Provide["bot_context.bot"],
    ) -> None:
        """Send alert to chat.

        Args:
            chat_id: Chat id.
            text: Alert text.
            alert_status: Alert status.
            bot: Bot instance.
        """
        if alert_status == Status.ACTIVATE:
            await bot.send_photo(
                chat_id,
                IMGFILE,
                caption=text,
            )
        else:
            await bot.send_message(
                chat_id,
                text,
            )
