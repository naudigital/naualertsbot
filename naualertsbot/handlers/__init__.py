"""Handlers for the bot."""
from aiogram import Router

from naualertsbot.handlers import basic, debug, settings, weeks

router = Router()
router.include_router(basic.router)
router.include_router(debug.router)
router.include_router(weeks.router)
router.include_router(settings.router)
