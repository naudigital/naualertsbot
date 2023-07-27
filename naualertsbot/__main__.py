import argparse
import asyncio
import os
import sys
from importlib.metadata import version
from logging import getLogger
from typing import NoReturn, cast

import coloredlogs  # type: ignore
import dotenv
import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from naualertsbot import main
from naualertsbot.containers import Container

dotenv.load_dotenv()

logger = getLogger("naualertsbot")


async def bootstrap() -> NoReturn:
    """Bootstrap bot."""
    parser = argparse.ArgumentParser(description="NAU Alerts Bot")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path to config file",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Log level",
    )
    args = parser.parse_args(sys.argv[1:])
    coloredlogs.install(level=args.log_level)  # type: ignore

    logger.info("Running naualertsbot version %s", version(__package__))
    logger.info("Loading config from %s", args.config)

    if not os.path.isfile(args.config):
        logger.error("Config file not found")
        sys.exit(1)

    container = Container()
    container.config.from_yaml(args.config)

    if container.config.get("sentry_dsn"):
        logger.info("Initializing Sentry")
        sentry_sdk.init(
            cast(str, container.config.get("sentry_dsn")),
            integrations=[
                AioHttpIntegration(),
                RedisIntegration(),
            ],
        )

    await container.init_resources()  # type: ignore

    logger.info("Wiring packages")
    container.wire(packages=["naualertsbot"])

    await main.main()


def poetry_main() -> None:
    """Poetry entry point."""
    asyncio.run(bootstrap())


if __name__ == "__main__":
    asyncio.run(bootstrap())
