from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from dependency_injector import containers, providers

from naualertsbot.db import init_redis
from naualertsbot.services import alerts, weeks, worker


class Services(containers.DeclarativeContainer):
    config = providers.Configuration()

    alerts = providers.Singleton(
        alerts.AlertsService,
        base_url=config.alerts.base_url,
        api_token=config.alerts.api_token,
        region=config.alerts.region,
    )
    worker = providers.Singleton(worker.WorkerService)
    weeks = providers.Singleton(weeks.WeeksService)


class Databases(containers.DeclarativeContainer):
    config = providers.Configuration()

    redis = providers.Resource(
        init_redis,
        url=config.redis_url,
    )


class BotContext(containers.DeclarativeContainer):
    config = providers.Configuration()

    bot = providers.Singleton(
        Bot,
        token=config.token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    dispatcher = providers.Singleton(
        Dispatcher,
        bot=bot,
    )


class HttpContext(containers.DeclarativeContainer):
    config = providers.Configuration()

    app = providers.Singleton(web.Application)


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    cself = providers.Self()  # type: ignore
    db = providers.Container(Databases, config=config.db)
    bot_context = providers.Container(BotContext, config=config.bot)
    http = providers.Container(HttpContext, config=config.http)
    services = providers.Container(Services, config=config.services)
