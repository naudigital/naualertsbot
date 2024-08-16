from logging import getLogger
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.filters.chat_member_updated import (
    IS_ADMIN,
    IS_MEMBER,
    IS_NOT_MEMBER,
    MEMBER,
    RESTRICTED,
    ChatMemberUpdatedFilter,
)
from dependency_injector.wiring import Provide, inject

from naualertsbot.stats import update_pm_stats, update_stats
from naualertsbot.texts import get_raw_text
from naualertsbot.utils import check_bot_admin, check_settings

if TYPE_CHECKING:
    from aiogram import Bot
    from redis.asyncio import Redis

logger = getLogger(__name__)

router = Router()


@inject
async def _is_subscribed(
    chat: types.Chat,
    redis: "Redis[Any]" = Provide["db.redis"],
) -> bool:
    """Check if chat is subscribed to bot.

    Args:
        chat: Chat instance.
        redis: Redis instance.

    Returns:
        True if chat is subscribed to bot.
    """
    subscribed_to_alerts = await redis.sismember("subscribers:alerts", chat.id)
    subscribed_to_weeks = await redis.sismember("subscribers:weeks", chat.id)
    return subscribed_to_alerts or subscribed_to_weeks


@router.message(Command("start"))
@inject
async def start(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Start bot.

    Args:
        message: Message instance.
        bot: Bot instance.
        redis: Redis instance.
    """
    me = await bot.me()
    if message.chat.type == "private":
        await update_pm_stats(message.chat)
        await message.answer(
            get_raw_text("basic.start"),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="Додати в групу",
                            url=f"https://t.me/{me.username}?startgroup&admin=delete_messages",
                        ),
                    ],
                ],
            ),
        )
        return

    if message.chat.type not in {"group", "supergroup"}:
        return

    await update_stats(message.chat)

    if not message.from_user:
        return


@router.message(Command("stop"))
@inject
async def stop(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Stop bot.

    Args:
        message: Message instance.
        bot: Bot instance.
        redis: Redis instance.
    """
    if message.chat.type == "private":
        await message.answer("❌ <b>Помилка!</b>\nЦя команда доступна тільки в групах.")
        return

    if message.chat.type not in {"group", "supergroup"}:
        return

    await update_stats(message.chat)

    if not message.from_user:
        return

    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in {"administrator", "creator"}:
        return

    await redis.srem("subscribers:alerts", message.chat.id)
    await redis.srem("subscribers:weeks", message.chat.id)

    await message.answer(
        "✅ <b>Ви відписались від розсилки!</b>\nВсього найкращого🫡",
    )
    await message.chat.leave()


@inject
async def subscribe_all(
    handler: Callable[  # noqa: WPS221, WPS110, WPS320
        [types.Update, Dict[str, Any]],
        Awaitable[Any],
    ],
    event: types.Update,
    data: Dict[str, Any],  # noqa: WPS110
    redis: "Redis[Any]" = Provide["db.redis"],
) -> Any:
    """Subscribe all groups to alerts and weeks.

    Args:
        handler: Handler.
        event: Update instance.
        data: Data.
        redis: Redis instance.

    Returns:
        Result of handler.
    """
    if event.message and event.message.chat:
        if event.message.chat.type == "private":
            await update_pm_stats(event.message.chat)
            return await handler(event, data)

        if event.message.chat.type not in {"group", "supergroup"}:
            return await handler(event, data)

        await update_stats(event.message.chat)

        if await check_settings("subscribe_all"):
            if not await _is_subscribed(event.message.chat):
                await redis.sadd("subscribers:alerts", event.message.chat.id)
                await redis.sadd("subscribers:weeks", event.message.chat.id)
                logger.info(
                    "Group %s was subscribed according to global autosubscribe rule",
                    event.message.chat.id,
                )

    return await handler(event, data)


router.message.outer_middleware(subscribe_all)  # type: ignore


@router.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> IS_ADMIN),
)
@inject
async def added_as_admin(
    event: types.ChatMemberUpdated,
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Add group to subscribers when bot is added as admin.

    Args:
        event: ChatMemberUpdated instance.
        bot: Bot instance.
        redis: Redis instance.
    """
    if event.chat.type not in {"group", "supergroup"}:
        return

    await update_stats(event.chat)

    me_member = event.new_chat_member
    if not check_bot_admin(me_member):
        await bot.send_message(
            event.chat.id,
            (
                "❌ <b>Упс!</b>\n"
                "Схоже я не маю права видаляти повідомлення. "
                "Не змінюйте дозволи в меню додавання боту. Спробуйте ще раз "
                "через особисті повідомлення зі мною."
            ),
        )
        await event.chat.leave()
        return

    if await _is_subscribed(event.chat):
        logger.critical("Propably missed leave event for %s", event.chat.id)
    else:
        await redis.sadd("subscribers:alerts", event.chat.id)
        await redis.sadd("subscribers:weeks", event.chat.id)
        logger.info("Bot was added to group %s", event.chat.id)

    await bot.send_message(
        event.chat.id,
        (
            "🎉 <b>Успішно!</b>\n"
            "Щоб налаштувати сповіщення використовуйте /settings.\n"
            "Відписатись від розсилки - /stop.\n\n"
        ),
    )


@router.my_chat_member(
    ChatMemberUpdatedFilter(
        member_status_changed=IS_NOT_MEMBER >> (MEMBER | +RESTRICTED),
    ),
)
@inject
async def added_as_member(
    event: types.ChatMemberUpdated,
    bot: "Bot" = Provide["bot_context.bot"],
) -> None:
    """Add group to subscribers when bot is added as member.

    Args:
        event: ChatMemberUpdated instance.
        bot: Bot instance.
    """
    if event.chat.type not in {"group", "supergroup"}:
        return

    await bot.send_message(
        event.chat.id,
        (
            "❌ <b>Помилочка!</b>\n"
            "Боту необхідні права адміністратора з правом видалення повідомлень. "
            "Додайте мене в чат за допомогою кнопки яку я надішлю в особисті повідомлення."
        ),
    )
    await event.chat.leave()


@router.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=IS_MEMBER >> IS_NOT_MEMBER),
)
@inject
async def removed_from_group(
    event: types.ChatMemberUpdated,
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Unsubscribe group when bot is removed from it.

    Args:
        event: ChatMemberUpdated instance.
        redis: Redis instance.
    """
    if event.chat.type not in {"group", "supergroup"}:
        return

    await update_stats(event.chat)

    if await _is_subscribed(event.chat):
        await redis.srem("subscribers:alerts", event.chat.id)
        await redis.srem("subscribers:weeks", event.chat.id)
        logger.info("Bot was removed from group %s", event.chat.id)
