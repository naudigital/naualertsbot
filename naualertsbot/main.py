"""Main module."""

import asyncio
from logging import getLogger
from typing import TYPE_CHECKING, Any, NoReturn, cast

from aiohttp import web
from dependency_injector.wiring import Provide, inject
from pydantic import ValidationError

from naualertsbot import bot, services
from naualertsbot.graceful_exit import GracefulExitManager
from naualertsbot.models import Alert

if TYPE_CHECKING:
    from dependency_injector.providers import Configuration
    from redis.asyncio import Redis

    from naualertsbot.containers import Container
    from naualertsbot.services.alerts import AlertsService
    from naualertsbot.services.weeks import WeeksService
    from naualertsbot.services.worker import WorkerService


logger = getLogger(__name__)

HTTP_PORT = 8080


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
        await redis.lpush("alerts", alert.model_dump_json())


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
            await alerts_service.trigger_alert(Alert.model_validate_json(alert))
        except (ValidationError, TypeError):
            logger.warning("Invalid alert in Redis: %s", alert)

    await redis.delete("alerts")

# implement healthcheck endpoint

HTTP_STATUS_OK = 200


async def healthcheck(request: web.Request) -> web.Response:
    """Healthcheck endpoint.

    Args:
        request: Request instance.

    Returns:
        Response instance.
    """
    return web.Response(text="OK", status=HTTP_STATUS_OK)


@inject
async def main(  # noqa: WPS210, WPS213
    app: "web.Application" = Provide["http.app"],
    config: "Configuration" = Provide["http.config"],
    container: "Container" = Provide["cself"],
    alerts_service: "AlertsService" = Provide["services.alerts"],
    worker_service: "WorkerService" = Provide["services.worker"],
    weeks_service: "WeeksService" = Provide["services.weeks"],
) -> NoReturn:
    """Run application.

    Args:
        app: Application instance.
        config: Configuration instance.
        container: Container instance.
        alerts_service: Alert service instance.
        worker_service: Worker service instance.
        weeks_service: Weeks service instance.
    """
    logger.info("Initializing services")
    await services.init()

    logger.info("Initializing bot")
    await bot.init()

    logger.info("Loading alerts state")
    await load_alerts_state()

    app.router.add_get("/healthcheck", healthcheck)

    host = cast(str, config.get("host") or "127.0.0.1")
    port = HTTP_PORT

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

    weeks_task = asyncio.create_task(
        weeks_service.run(),
        name="weeks",
    )

    loop = asyncio.get_event_loop()

    manager = GracefulExitManager(container, loop)

    # setup exit callbacks
    manager.add_exit_callback(app.shutdown)
    manager.add_exit_callback(weeks_service.shutdown)
    manager.add_exit_callback(worker_service.shutdown)
    manager.add_exit_callback(alerts_service.shutdown)
    manager.add_exit_callback(save_alerts_state)

    # setup main bot tasks
    # task 'worker_task' will not be cancelled on exit
    # because it must finish all internal jobs
    manager.track_task(worker_task, cancel_on_exit=False)
    manager.track_task(server_task)
    manager.track_task(weeks_task)

    manager.setup_signal_handlers()

    await manager.wait(exit_on_failure=True)
