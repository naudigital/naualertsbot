import asyncio
from json.decoder import JSONDecodeError
from logging import getLogger
from typing import TYPE_CHECKING, Any, cast

from aiohttp import ClientSession, web
from dependency_injector.wiring import Provide, inject
from pydantic import ValidationError

from airalertbot import models

if TYPE_CHECKING:
    from dependency_injector.providers import Configuration

logger = getLogger(__name__)


RANDOM_SALT_LENGTH = 16


class AlertsService:  # noqa: WPS306
    """Service for getting alerts from ukrainealarm.com API."""

    _queue: asyncio.Queue[models.Alert | None]
    region: int

    def __init__(
        self: "AlertsService",
        base_url: str,
        region: int,
        secret: str,
    ) -> None:
        """Initialize service.

        Args:
            base_url: Base URL for API.
            region: Region ID.
            secret: Secret for webhook.
        """
        self._loop = asyncio.get_event_loop()
        self._session = ClientSession(base_url=base_url)
        self.region = region
        self._webhook_path = f"/webhook/alerts/{secret}"
        self._queue = asyncio.Queue()
        self._shutting_down = False

    async def setup_for_app(
        self: "AlertsService",
        app: "web.Application",
        base_url: str,
    ) -> None:
        """Configure application.

        Args:
            app: Application instance.
            base_url: Base URL for API.
        """
        # append random data to webhook path for security reasons
        app.router.add_post(self._webhook_path, self._handle_webhook)

        await self._setup_webhook(f"{base_url}{self._webhook_path}")

    @property
    def qsize(self: "AlertsService") -> int:
        """Queue size.

        Returns:
            Queue size.
        """
        return self._queue.qsize()

    async def wait_alert(self: "AlertsService") -> models.Alert | None:
        """Wait for alerts from API.

        Returns:
            Alerts from API or None if shutting down.
        """
        if self._shutting_down:
            return None
        return await self._queue.get()

    def next_alert(self: "AlertsService") -> models.Alert | None:
        """Immediately get next alert.

        Returns:
            Alerts from API.
        """
        return self._queue.get_nowait()

    def processing_done(self: "AlertsService") -> None:
        """Mark alert as processed."""
        self._queue.task_done()

    async def trigger_alert(self: "AlertsService", alert: models.Alert) -> None:
        """Manually trigger alert.

        Args:
            alert: Alert to trigger.
        """
        self._queue.put_nowait(alert)

    async def shutdown(self: "AlertsService") -> None:
        """Shutdown service."""
        self._shutting_down = True
        self._queue.put_nowait(None)
        await self._remove_webhook(self._webhook_path)
        await self._session.close()

        await self._queue.join()

    async def _handle_webhook(
        self: "AlertsService",
        request: web.Request,
    ) -> web.Response:
        if self._shutting_down:
            logger.debug("Ignoring webhook request during shutdown")
            return web.json_response({"status": "ok"})
        try:
            request_data = await request.json()
        except JSONDecodeError as err:
            logger.error("Invalid JSON data in request: %s", err.doc)
            return web.json_response({"status": "error"}, status=400)  # noqa: WPS432

        try:
            model = models.Alert(**request_data)
        except ValidationError:
            logger.error("Invalid data in request: %s", request_data)
            return web.json_response({"status": "error"}, status=400)  # noqa: WPS432

        if model.region_id == self.region:
            self._queue.put_nowait(model)
        else:
            logger.debug(
                "Ignoring alert for another region (%d): %s",
                model.region_id,
                model,
            )

        return web.json_response({"status": "ok"})

    async def _request(
        self: "AlertsService",
        method: str,
        url: str,
        *,
        ignore_response: bool = False,
        ignore_errors: bool = False,
        **kwargs: Any,
    ) -> Any:
        logger.debug("Making request: %s %s (%s)", method, url, kwargs)
        async with self._session.request(method, url, **kwargs) as response:
            if not ignore_response:
                json_data = await response.json()
                if not ignore_errors:
                    response.raise_for_status()
                return json_data
            await response.read()

    async def _setup_webhook(self: "AlertsService", url: str) -> None:
        await self._request(
            "POST",
            "/api/v3/webhook",
            json={"webHookUrl": url},
            ignore_response=True,
        )
        logger.info("Registered webhook: %s", url)

    async def _remove_webhook(self: "AlertsService", url: str) -> None:
        await self._request(
            "DELETE",
            "/api/v3/webhook",
            json={"webHookUrl": url},
            ignore_response=True,
        )
        logger.info("Removed webhook")


@inject
async def init(
    app: "web.Application" = Provide["http.app"],
    config: "Configuration" = Provide["http.config"],
    alerts_service: "AlertsService" = Provide["services.alerts"],
) -> None:
    """Initialize alerts service.

    This function is called on startup.

    Args:
        app: Application instance.
        config: Configuration instance.
        alerts_service: Alerts service instance.
    """
    await alerts_service.setup_for_app(app, cast(str, config["base_url"]))
