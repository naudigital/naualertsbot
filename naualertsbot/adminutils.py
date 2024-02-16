import asyncio
from contextlib import suppress

from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError


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
