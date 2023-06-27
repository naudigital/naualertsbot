import argparse
import asyncio
import os
import sys
from logging import getLogger
from typing import NoReturn

import coloredlogs  # type: ignore
import dotenv

from airalertbot import main
from airalertbot.containers import Container

dotenv.load_dotenv()
coloredlogs.install(level="DEBUG")  # type: ignore

logger = getLogger("airalertbot")


async def bootstrap() -> NoReturn:
    """Bootstrap bot."""
    parser = argparse.ArgumentParser(description="AirAlertBot")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yml",
        help="Path to config file",
    )
    args = parser.parse_args(sys.argv[1:])
    logger.info("Loading config from %s", args.config)

    if not os.path.isfile(args.config):
        logger.error("Config file not found")
        sys.exit(1)

    container = Container()
    container.config.from_yaml(args.config)

    await container.init_resources()  # type: ignore

    logger.info("Wiring packages")
    container.wire(packages=["airalertbot"])

    await main.main()


def poetry_main() -> None:
    """Poetry entry point."""
    asyncio.run(bootstrap())


if __name__ == "__main__":
    asyncio.run(bootstrap())
