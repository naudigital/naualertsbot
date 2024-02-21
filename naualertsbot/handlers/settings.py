from enum import StrEnum
from logging import getLogger
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from aiogram import Router, types
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dependency_injector.wiring import Provide, inject

from naualertsbot.stats import update_stats
from naualertsbot.utils import delete_delayed

if TYPE_CHECKING:
    from aiogram import Bot
    from dependency_injector.providers import Configuration
    from redis.asyncio import Redis

logger = getLogger(__name__)

router = Router()

AVAILABLE_FEATURES = MappingProxyType(
    {
        "deactivation_banger": "Жосткий бенгер на відбій тривоги",
    },
)


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

    if isinstance(query.message, types.InaccessibleMessage):
        await query.answer("❌ Помилка!\nЦе повідомлення недоступне.")
        return

    await query.answer()
    await query.message.edit_text(
        "🔧 <b>Налаштування</b>\n\n"
        "Ви можете налаштувати, які повідомлення ви хочете отримувати в цій групі. "
        "Використовуйте кнопки нижче.",
        reply_markup=builder.as_markup(),
    )


@router.message(Command("globalsettings"))
@inject
async def global_settings(
    message: types.Message,
    redis: "Redis[Any]" = Provide["db.redis"],
    config: "Configuration" = Provide["bot_context.config"],
) -> None:
    """Manage global settings. For admins only.

    Args:
        message: Message instance.
        redis: Redis instance.
        config: Configuration instance.
    """
    if not message.from_user:
        return

    if message.from_user.id not in cast(list[int], config["admins"]):
        return

    if not message.text:
        return

    args = message.text.split(" ")

    match args[1:]:
        case ["show"]:
            text = "🔧 <b>Глобальні налаштування</b>\n\n"

            for name, value in (  # noqa: WPS519, WPS352, WPS110
                await redis.hgetall("settings")
            ).items():
                text += f"{name}: {value}\n"  # noqa: WPS336

            await message.answer(text)
            return
        case ["enable", setting_name]:
            await redis.hset("settings", setting_name, "true")
            logger.info("Enabled setting: %s", setting_name)
            await message.answer("✅ Успішно")
            return
        case ["disable", setting_name]:
            await redis.hset("settings", setting_name, "false")
            logger.info("Disabled setting: %s", setting_name)
            await message.answer("✅ Успішно")
            return
        case _:
            await message.answer("❌ Помилка!\nНевідома команда.")
            return


@router.message(Command("feat"))
@inject
async def feat(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Show available AB features.

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

    if not message.text:
        return

    if not message.from_user:
        return

    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in {"administrator", "creator"}:
        return

    args = message.text.split(maxsplit=2)
    if len(args) != 3:
        await message.delete()
        return

    action = args[1].strip().lower()
    feature = args[2].strip().lower()

    if action not in {"enable", "disable"}:
        await message.delete()
        return

    if feature not in AVAILABLE_FEATURES:
        await message.delete()
        return

    if action == "enable":
        await redis.sadd(f"features:{feature}", message.chat.id)
    elif action == "disable":
        await redis.srem(f"features:{feature}", message.chat.id)

    answer = await message.answer("✅ Успішно")

    await delete_delayed([message, answer], 5)
