from typing import TYPE_CHECKING

from aiogram import types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dependency_injector.wiring import Provide, inject

from airalertbot.handlers import router

if TYPE_CHECKING:
    from aiogram import Bot, Dispatcher
    from aiohttp.web import Application
    from dependency_injector.providers import Configuration


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

    webhook_path = f"/webhook/bot{bot.token}"
    webhook_url = f"{config['base_url']}{webhook_path}"

    await bot.delete_webhook()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
    setup_application(app, dp)

    await bot.set_webhook(webhook_url)

    await bot.set_my_commands(
        [
            types.BotCommand(command="/start", description="Підписатися на сповіщення"),
            types.BotCommand(command="/stop", description="Відписатися від сповіщень"),
        ],
    )
