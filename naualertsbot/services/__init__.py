"""Services."""
from naualertsbot.services import alerts


async def init() -> None:
    """Initialize services.

    This function is called on startup.
    """
    await alerts.init()
