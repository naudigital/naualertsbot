"""Main module."""
import asyncio
from logging import getLogger
from typing import TYPE_CHECKING, Any, NoReturn, cast

from aiohttp import web
from dependency_injector.wiring import Provide, inject
from pydantic import ValidationError

from airalertbot import bot, services
from airalertbot.graceful_exit import GracefulExitManager
from airalertbot.models import Alert

if TYPE_CHECKING:
    from dependency_injector.providers import Configuration
    from redis.asyncio import Redis

    from airalertbot.containers import Container
    from airalertbot.services.alerts import AlertsService
    from airalertbot.services.worker import WorkerService


logger = getLogger(__name__)


@inject
async def save_alerts_state(
    alerts_service: "AlertsService" = Provide["services.alerts"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Save alerts state to Redis.

    Args:
        alerts_service: Alerts service instance.
        redis: Redis client instance.
    """
    if alerts_service.qsize == 0:
        return

    logger.info("Saving alerts state to Redis")

    alerts: list[Alert] = []
    while alerts_service.qsize > 0:
        alert = alerts_service.next_alert()
        if alert is not None:
            alerts.append(alert)

    for alert in alerts:  # noqa: WPS440
        await redis.lpush("alerts", alert.json())


@inject
async def load_alerts_state(
    alerts_service: "AlertsService" = Provide["services.alerts"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Load alerts state from Redis.

    Args:
        alerts_service: Alerts service instance.
        redis: Redis client instance.
    """
    alerts = await redis.lrange("alerts", 0, -1)
    for alert in alerts:
        try:
            await alerts_service.trigger_alert(Alert.parse_raw(alert))
        except (ValidationError, TypeError):
            logger.warning("Invalid alert in Redis: %s", alert)

    await redis.delete("alerts")


@inject
async def main(  # noqa: WPS210, WPS213
    app: "web.Application" = Provide["http.app"],
    config: "Configuration" = Provide["http.config"],
    container: "Container" = Provide["cself"],
    alert_service: "AlertsService" = Provide["services.alerts"],
    worker_service: "WorkerService" = Provide["services.worker"],
) -> NoReturn:
    """Run application.

    Args:
        app: Application instance.
        config: Configuration instance.
        container: Container instance.
        alert_service: Alert service instance.
        worker_service: Worker service instance.
    """
    logger.info("Initializing services")
    await services.init()

    logger.info("Initializing bot")
    await bot.init()

    logger.info("Loading alerts state")
    await load_alerts_state()

    host = cast(str, config.get("host") or "127.0.0.1")
    port = cast(int, config["port"])

    logger.info("Starting application on %s:%s", host, port)

    server_task = asyncio.create_task(
        web._run_app(  # noqa: WPS437; intented  # type: ignore
            app,
            host=host,
            port=port,
            print=lambda *args: None,
            handle_signals=False,
        ),
        name="webserver",
    )

    worker_task = asyncio.create_task(
        worker_service.run(),
        name="worker",
    )

    loop = asyncio.get_event_loop()

    manager = GracefulExitManager(container, loop)

    manager.add_exit_callback(app.shutdown)
    manager.add_exit_callback(worker_service.shutdown)
    manager.add_exit_callback(alert_service.shutdown)
    manager.add_exit_callback(save_alerts_state)

    manager.track_task(worker_task, cancel_on_exit=False)
    manager.track_task(server_task)

    manager.setup_signal_handlers()

    await manager.wait(exit_on_failure=True)
