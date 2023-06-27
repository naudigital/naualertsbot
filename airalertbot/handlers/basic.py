from logging import getLogger
from typing import TYPE_CHECKING, Any

from aiogram import F as _MF
from aiogram import Router, types
from aiogram.filters import Command
from dependency_injector.wiring import Provide, inject

if TYPE_CHECKING:
    from aiogram import Bot
    from redis.asyncio import Redis

logger = getLogger(__name__)

router = Router()


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
            "Привіт! Я бот, який буде надсилати повідомлення про повітряну тривогу в Києві. "
            "Для того, щоб я почав надсилати повідомлення, додайте мене в групу через "
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

    if not message.from_user:
        return

    # check if user is admin
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in {"administrator", "creator"}:
        return

    if await redis.sismember("subscribers", message.chat.id):
        await message.answer("Ви вже підписані на повідомлення про повітряну тривогу.")
        return

    await redis.sadd("subscribers", message.chat.id)
    await message.answer("Ви підписались на повідомлення про повітряну тривогу.")


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
        await message.answer("Ця команда доступна тільки в групах.")
        return

    if message.chat.type not in {"group", "supergroup"}:
        return

    if not message.from_user:
        return

    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in {"administrator", "creator"}:
        return

    if await redis.sismember("subscribers", message.chat.id):
        await redis.srem("subscribers", message.chat.id)
        await message.answer("Ви відписались від повідомлень про повітряну тривогу.")
        return

    await message.answer("Ви не підписані на повідомлення про повітряну тривогу.")


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

    await redis.srem("subscribers", message.chat.id)
    logger.info("Bot was removed from group %s", message.chat.id)
