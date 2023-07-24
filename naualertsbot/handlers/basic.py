from logging import getLogger
from typing import TYPE_CHECKING, Any

from aiogram import F as _MF
from aiogram import Router, types
from aiogram.filters import Command
from dependency_injector.wiring import Provide, inject

from naualertsbot.stats import update_stats

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
        await message.answer(
            "👋 <b>Привіт!</b> Я бот, який буде надсилати сповіщення для НАУ в чатах. "
            "Сюди входять сповіщення про тривогу з інформацією про укриття та "
            "повідомлення про навчальні тижні.\n\n"
            "⚙️ Команди бота можна дізнатись через меню.\n\n"
            "🔽 Для того, щоб я почав надсилати повідомлення, додайте мене в групу через "
            "кнопку нижче.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="Додати в групу",
                            url=f"https://t.me/{me.username}?startgroup=true",
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

    # check if user is admin
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in {"administrator", "creator"}:
        return

    if await _is_subscribed(message.chat):
        await message.answer(
            "❌ <b>Помилка!</b>\n"
            "Ви вже підписані на розсилку бота. Щоб відписатись, використовуйте "
            "команду /stop.",
        )
        return

    await redis.sadd("subscribers:alerts", message.chat.id)
    await redis.sadd("subscribers:weeks", message.chat.id)

    text = (
        "🎉 <b>Успішно!</b>\n"
        "Щоб налаштувати сповіщення використовуйте /settings.\n"
        "Відписатись від розсилки - /stop.\n\n"
    )
    participant = await bot.get_chat_member(
        message.chat.id,
        (await bot.me()).id,
    )
    if not participant.can_delete_messages:
        text += (
            "💠 <b>Не забудьте призначити бота адміністратором з правом "  # noqa: WPS336
            "видалення повідомлень!</b> Без цього не будуть працювати "
            "команди /week та /calendar."
        )

    await message.answer(text)


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

    if await _is_subscribed(message.chat):
        await redis.srem("subscribers:alerts", message.chat.id)
        await redis.srem("subscribers:weeks", message.chat.id)
        await message.answer(
            "✅ <b>Ви відписались від розсилки!</b> Щоб підписатись, "
            "використовуйте команду /start.",
        )
        return

    await message.answer(
        "❌ <b>Помилка!</b>\nВи не були підписані на розсилку бота. Щоб "
        "підписатись, використовуйте команду /start.",
    )


# unsubscribe group when bot is removed from it
@router.message(_MF.left_chat_member)
@inject
async def group_leave(
    message: types.Message,
    bot: "Bot" = Provide["bot_context.bot"],
    redis: "Redis[Any]" = Provide["db.redis"],
) -> None:
    """Unsubscribe group when bot is removed from it.

    Args:
        message: Message instance.
        bot: Bot instance.
        redis: Redis instance.
    """
    if not message.left_chat_member:
        return

    if message.left_chat_member.id != (await bot.me()).id:
        return

    await redis.srem("subscribers:alerts", message.chat.id)
    await redis.srem("subscribers:weeks", message.chat.id)
    logger.info("Bot was removed from group %s", message.chat.id)
