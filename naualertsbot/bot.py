from logging import getLogger
from typing import TYPE_CHECKING, cast
from urllib.parse import urljoin, urlparse

from aiogram import types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dependency_injector.wiring import Provide, inject

from naualertsbot.handlers import router

if TYPE_CHECKING:
    from aiogram import Bot, Dispatcher
    from aiohttp.web import Application
    from dependency_injector.providers import Configuration

logger = getLogger(__name__)


@inject
async def init(
    bot: "Bot" = Provide["bot_context.bot"],
    dp: "Dispatcher" = Provide["bot_context.dispatcher"],
    app: "Application" = Provide["http.app"],
    config: "Configuration" = Provide["http.config"],
) -> None:
    """Initialize bot.

    This function is called on startup.

    Args:
        bot: Bot instance.
        dp: Dispatcher instance.
        app: Application instance.
        config: Configuration instance.
    """
    bot.parse_mode = "HTML"
    dp.include_router(router)

    base_url = cast(str, config["base_url"])
    rpath = f"/webhook/bot{bot.token}"
    parsed_url = urlparse(base_url)
    if parsed_url.path:
        # if base_url has path, append webhook path to it
        webhook_path = parsed_url.path + rpath
        parsed_url = parsed_url._replace(path=webhook_path)  # noqa: WPS437
        webhook_url = parsed_url.geturl()
    else:
        # if base_url has no path, use webhook path as is
        webhook_path = rpath
        webhook_url = urljoin(base_url, webhook_path)

    await bot.delete_webhook()
    logger.debug("Listening at webhook path: %s", webhook_path)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    setup_application(app, dp)

    await bot.set_webhook(webhook_url, allowed_updates=dp.resolve_used_update_types())
    logger.info("Registered webhook: %s", webhook_url)

    await bot.set_my_commands(
        [
            types.BotCommand(command="/start", description="Підписатися на сповіщення"),
            types.BotCommand(command="/stop", description="Відписатися від сповіщень"),
            types.BotCommand(
                command="/week",
                description="Переглянути поточний тиждень",
            ),
            types.BotCommand(
                command="/calendar",
                description="Переглянути календар семестру",
            ),
            types.BotCommand(
                command="/settings",
                description="Налаштування сповіщень",
            ),
        ],
    )
