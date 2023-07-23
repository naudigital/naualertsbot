import json
from typing import TYPE_CHECKING, Any

from dependency_injector.wiring import Provide, inject

from airalertbot.models import ChatStats

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
    me_participant = await bot.get_chat_member(chat.id, (await bot.me()).id)

    await redis.hset(
        "stats",
        str(chat.id),
        json.dumps(
            {
                "name": chat.title,
                "username": chat.username,
                "members": (await chat.get_member_count()),
                "admin_rights": bool(me_participant.can_delete_messages),
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
