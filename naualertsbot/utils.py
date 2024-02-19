import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from dependency_injector.wiring import Provide, inject

if TYPE_CHECKING:
    from redis.asyncio import Redis


def check_bot_admin(
    participant: (  # noqa: WPS320
        types.ChatMemberOwner  # noqa: W503, WPS320
        | types.ChatMemberAdministrator  # noqa: W503
        | types.ChatMemberMember  # noqa: W503
        | types.ChatMemberRestricted  # noqa: W503
        | types.ChatMemberLeft  # noqa: W503
        | types.ChatMemberBanned  # noqa: W503
    ),
) -> bool:
    """Check if bot has delete message permission.

    Args:
        participant: Participant instance.

    Returns:
        True if bot has delete message permission.
    """
    if isinstance(  # noqa: WPS337
        participant,
        (
            types.ChatMemberMember,
            types.ChatMemberRestricted,
            types.ChatMemberLeft,
            types.ChatMemberBanned,
        ),
    ):
        return False

    return (
        isinstance(participant, types.ChatMemberOwner)
        or participant.can_delete_messages  # noqa: W503
    )


async def delete_delayed(messages: list[types.Message], delay: int) -> None:
    """Delete messages after delay.

    Args:
        messages: List of messages to delete.
        delay: Delay in seconds.
    """
    await asyncio.sleep(delay)
    for message in messages:
        with suppress(TelegramBadRequest, TelegramForbiddenError):
            await message.delete()


@inject
async def check_settings(name: str, redis: "Redis[Any]" = Provide["db.redis"]) -> bool:
    """Check setting.

    Args:
        redis: Redis instance.
        name: Setting name.

    Returns:
        True if setting is enabled.
    """
    return (await redis.hget("settings", name)) == b"true"
