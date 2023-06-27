"""Handlers for the bot."""
from aiogram import Router

from airalertbot.handlers import basic, debug

router = Router()
router.include_router(basic.router)
router.include_router(debug.router)
