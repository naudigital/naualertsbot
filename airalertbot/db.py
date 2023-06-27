from typing import Any, AsyncGenerator

from redis.asyncio import Redis


async def init_redis(url: str) -> AsyncGenerator["Redis[Any]", None]:
    """Initialize Redis connection.

    Args:
        url: Redis URL.

    Yields:
        Redis connection.
    """
    client = Redis.from_url(url)  # type: ignore
    yield client
    await client.close()
