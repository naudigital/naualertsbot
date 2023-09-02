from aiogram import types


def check_bot_admin(
    participant: types.ChatMemberOwner  # noqa: W503, WPS320
    | types.ChatMemberAdministrator  # noqa: W503
    | types.ChatMemberMember  # noqa: W503
    | types.ChatMemberRestricted  # noqa: W503
    | types.ChatMemberLeft  # noqa: W503
    | types.ChatMemberBanned,  # noqa: W503
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
