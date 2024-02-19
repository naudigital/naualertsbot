import json
from typing import TYPE_CHECKING, Any

from aiogram.exceptions import TelegramForbiddenError
from dependency_injector.wiring import Provide, inject

from naualertsbot.models import ChatStats, PMChatStats
from naualertsbot.utils import check_bot_admin

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Chat
    from redis.asyncio import Redis


@inject
async def update_stats(
    chat: "Chat",
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Update stats in Redis.

    Args:
        chat: Chat instance.
        bot: Bot instance.
        redis: Redis instance.
    """
    try:
        me_participant = await bot.get_chat_member(chat.id, (await bot.me()).id)
    except TelegramForbiddenError:
        # bot was kicked from chat
        await redis.hdel("stats", str(chat.id))
        return

    await redis.hset(
        "stats",
        str(chat.id),
        json.dumps(
            {
                "name": chat.title,
                "username": chat.username,
                "members": (await chat.get_member_count()),
                "admin_rights": check_bot_admin(me_participant),
            },
        ),
    )


@inject
async def update_pm_stats(
    chat: "Chat",
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Update stats in Redis.

    Args:
        chat: Chat instance.
        bot: Bot instance.
        redis: Redis instance.
    """
    if chat.type != "private":
        return

    await redis.hset(
        "pm_stats",
        str(chat.id),
        json.dumps(
            {
                "name": chat.first_name,
                "username": chat.username,
            },
        ),
    )


@inject
async def get_stats(
    redis: "Redis[Any]" = Provide["db.redis"],
) -> dict[int, ChatStats]:
    """Get stats from Redis.

    Args:
        redis: Redis instance.

    Returns:
        Stats dict.
    """
    stats: dict[str, str] = await redis.hgetall("stats")
    stats_obj: dict[int, ChatStats] = {}
    for key, value in stats.items():  # noqa: WPS110
        stats_dict = json.loads(value)
        stats_dict["chat_id"] = int(key)
        stats_obj[int(key)] = ChatStats(**stats_dict)

    return stats_obj


@inject
async def get_pm_stats(
    redis: "Redis[Any]" = Provide["db.redis"],
) -> dict[int, PMChatStats]:
    """Get stats from Redis.

    Args:
        redis: Redis instance.

    Returns:
        Stats dict.
    """
    stats: dict[str, str] = await redis.hgetall("pm_stats")
    stats_obj: dict[int, PMChatStats] = {}
    for key, value in stats.items():  # noqa: WPS110
        stats_dict = json.loads(value)
        stats_dict["chat_id"] = int(key)
        stats_obj[int(key)] = PMChatStats(**stats_dict)

    return stats_obj


@inject
async def migrate_chat(
    old_chat_id: int,
    new_chat_id: int,
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Migrate chat stats to new chat id.

    Args:
        old_chat_id: Old chat id.
        new_chat_id: New chat id.
        redis: Redis instance.
    """
    await redis.hset(
        "stats",
        str(new_chat_id),
        await redis.hget("stats", str(old_chat_id)) or "{}",
    )
    await redis.hdel("stats", str(old_chat_id))
