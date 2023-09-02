from enum import StrEnum
from logging import getLogger
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from aiogram import Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dependency_injector.wiring import Provide, inject

from naualertsbot.stats import update_stats

if TYPE_CHECKING:
    from aiogram import Bot
    from redis.asyncio import Redis

logger = getLogger(__name__)

router = Router()


class SettingsAction(StrEnum):
    """Settings action."""

    subscribe = "subscribe"
    unsubscribe = "unsubscribe"


class SettingsTarget(StrEnum):
    """Settings target."""

    alerts = "alerts"
    weeks = "weeks"


class SettingsActionData(CallbackData, prefix="settings"):
    """Settings action callback data class."""

    action: SettingsAction
    target: SettingsTarget


STATUS_SIGNS = MappingProxyType(
    {
        True: "✅",
        False: "❌",
    },
)

ACTIONS = MappingProxyType(
    {
        True: SettingsAction.unsubscribe,
        False: SettingsAction.subscribe,
    },
)


@router.message(Command("settings"))
@inject
async def settings(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Show notification settings.

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

    alerts_sub = await redis.sismember("subscribers:alerts", message.chat.id)
    weeks_sub = await redis.sismember("subscribers:weeks", message.chat.id)

    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{STATUS_SIGNS[alerts_sub]} Тривога",
        callback_data=SettingsActionData(
            action=ACTIONS[alerts_sub],
            target=SettingsTarget.alerts,
        ),
    )
    builder.button(
        text=f"{STATUS_SIGNS[weeks_sub]} Навчальні тижні",
        callback_data=SettingsActionData(
            action=ACTIONS[weeks_sub],
            target=SettingsTarget.weeks,
        ),
    )

    await message.answer(
        "🔧 <b>Налаштування</b>\n\n"
        "Ви можете налаштувати, які повідомлення ви хочете отримувати в цій групі. "
        "Використовуйте кнопки нижче.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(SettingsActionData.filter())
@inject
async def settings_action(
    query: types.CallbackQuery,
    callback_data: SettingsActionData,
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Handle settings action.

    Args:
        query: CallbackQuery instance.
        callback_data: Callback data instance.
        bot: Bot instance.
        redis: Redis instance.
    """
    if not query.message:
        await query.answer("❌ Помилка!\nЦя команда доступна тільки в групах.")
        return

    if query.message.chat.type not in {"group", "supergroup"}:
        await query.answer("❌ Помилка!\nЦя команда доступна тільки в групах.")
        return

    if not query.from_user:
        await query.answer(
            "❌ Помилка!\nЦя команда доступна тільки користувачам.",
        )
        return

    await update_stats(query.message.chat)

    try:
        chat_member = await bot.get_chat_member(
            query.message.chat.id,
            query.from_user.id,
        )
    except TelegramForbiddenError:
        await query.answer("❌ Помилка!\nЯ не можу знайти вас в цій групі.")
        logger.debug("Ignoring callback action from unregistered chat")
        return

    if chat_member.status not in {"administrator", "creator"}:
        await query.answer(
            "❌ Помилка!\nЦя команда доступна тільки адміністраторам.",
        )
        return

    if callback_data.action == SettingsAction.subscribe:
        await redis.sadd(f"subscribers:{callback_data.target}", query.message.chat.id)
    elif callback_data.action == SettingsAction.unsubscribe:
        await redis.srem(f"subscribers:{callback_data.target}", query.message.chat.id)

    alerts_sub = await redis.sismember("subscribers:alerts", query.message.chat.id)
    weeks_sub = await redis.sismember("subscribers:weeks", query.message.chat.id)

    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"{STATUS_SIGNS[alerts_sub]} Тривога",
        callback_data=SettingsActionData(
            action=ACTIONS[alerts_sub],
            target=SettingsTarget.alerts,
        ),
    )
    builder.button(
        text=f"{STATUS_SIGNS[weeks_sub]} Навчальні тижні",
        callback_data=SettingsActionData(
            action=ACTIONS[weeks_sub],
            target=SettingsTarget.weeks,
        ),
    )

    await query.answer()
    await query.message.edit_text(
        "🔧 <b>Налаштування</b>\n\n"
        "Ви можете налаштувати, які повідомлення ви хочете отримувати в цій групі. "
        "Використовуйте кнопки нижче.",
        reply_markup=builder.as_markup(),
    )
