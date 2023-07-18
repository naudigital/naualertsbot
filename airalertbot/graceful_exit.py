import asyncio
import os
import signal
import sys
from logging import getLogger
from typing import TYPE_CHECKING, Any, Awaitable, Callable, NoReturn, cast

if TYPE_CHECKING:
    from airalertbot.containers import Container

logger = getLogger(__name__)

CB_WAIT_TIMEOUT = 5
TASK_WAIT_TIMEOUT = 5


class GracefulExitManager:  # noqa: WPS306
    """Graceful exit manager."""

    _container: "Container"
    _exit_cbs: list[Callable[[], Awaitable[None]]]  # noqa: WPS234
    _trackings: list[asyncio.Task[None]]
    _cancel_on_exit: list[asyncio.Task[None]]
    _exiting: bool
    _exit_future: asyncio.Future[None]

    def __init__(
        self: "GracefulExitManager",
        container: "Container",
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Initialize manager.

        Args:
            container: Container instance.
            loop: Event loop instance.
        """
        self._container = container
        self._loop = loop
        self._exit_cbs = []
        self._trackings = []
        self._cancel_on_exit = []
        self._exiting = False
        self._exit_future = loop.create_future()

    def add_exit_callback(
        self: "GracefulExitManager",
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        """Add exit callback.

        Args:
            callback: Callback to add.
        """
        self._exit_cbs.append(callback)

    def track_task(
        self: "GracefulExitManager",
        task: asyncio.Task[None],
        cancel_on_exit: bool = True,
    ) -> None:
        """Track task.

        Args:
            task: Task to track.
            cancel_on_exit: Cancel task on exit.
        """
        self._trackings.append(task)
        if cancel_on_exit:
            self._cancel_on_exit.append(task)

    def setup_signal_handlers(self: "GracefulExitManager") -> None:
        """Configure signal handlers."""
        self._loop.add_signal_handler(signal.SIGTERM, self.trigger)
        self._loop.add_signal_handler(signal.SIGINT, self.trigger)
        self._loop.add_signal_handler(signal.SIGHUP, self.trigger)
        self._loop.add_signal_handler(signal.SIGQUIT, self.trigger)

        self._loop.set_exception_handler(self._handle_exception)

    def trigger(self: "GracefulExitManager") -> None:
        """Trigger graceful exit."""
        if self._exiting:
            logger.critical("Got second exit signal. Exiting immediately.")
            os._exit(1)  # noqa: WPS437; intended  # type: ignore

        logger.info("Got exit signal. Exiting gracefully.")
        self._exiting = True

        self._exit_future.set_result(None)

    async def wait(
        self: "GracefulExitManager",
        exit_on_failure: bool = False,
    ) -> NoReturn:  # noqa: WPS213
        """Wait for exit signals.

        Args:
            exit_on_failure: Exit on task failure.
        """
        while True:  # noqa: WPS457
            done, pending = await asyncio.wait(
                self._trackings + [self._exit_future],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if self._exit_future in done:
                await self._exit()

            for task in cast(list[asyncio.Task[None]], done):
                self._trackings.remove(task)
                if task.exception():
                    logger.critical(
                        "Task '%s' finished with exception",
                        task.get_name(),
                        exc_info=task.exception(),
                    )
                    if exit_on_failure:
                        logger.critical("Unrecoverable error. Exiting.")  # noqa: WPS220
                        await self._exit()  # noqa: WPS220
                else:
                    logger.info("Task '%s' finished", task.get_name())

            pending.remove(self._exit_future)

            logger.info(
                "Tasks left: %s",
                ", ".join(
                    [
                        pending_task.get_name()
                        for pending_task in cast(list[asyncio.Task[None]], pending)
                    ],
                ),
            )

    def _handle_exception(
        self: "GracefulExitManager",
        loop: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> None:
        """Handle exception.

        Args:
            loop: Event loop instance.
            context: Exception context.
        """
        exception = context.get("exception")
        logger.exception("Unhandled exception", exc_info=exception)

    async def _call_exit_callbacks(self: "GracefulExitManager") -> None:
        for exit_cb in self._exit_cbs:
            task: asyncio.Task[None] = self._loop.create_task(exit_cb())  # type: ignore
            _done, pending = await asyncio.wait(
                [task],
                timeout=CB_WAIT_TIMEOUT,
            )
            if pending:
                logger.warning(
                    "Exit action %s did not finish in %s seconds. Cancelling.",
                    exit_cb,
                    CB_WAIT_TIMEOUT,
                )
                for pending_task in pending:
                    pending_task.cancel()

    async def _wait_tasks(self: "GracefulExitManager") -> None:  # noqa: WPS231
        for task in self._cancel_on_exit:
            task.cancel()
        done, pending = await asyncio.wait(
            self._trackings,
            return_when=asyncio.ALL_COMPLETED,
            timeout=TASK_WAIT_TIMEOUT,
        )
        if pending:
            logger.warning(
                "Tasks (%s) did not finish in %s seconds. Cancelling.",
                ", ".join([pending_task.get_name() for pending_task in pending]),
            )
            for pending_task in pending:
                pending_task.cancel()
            pdone, ppending = await asyncio.wait(
                pending,
                return_when=asyncio.ALL_COMPLETED,
                timeout=TASK_WAIT_TIMEOUT,
            )
            if ppending:
                logger.critical(
                    "Tasks (%s) did not finish in %s seconds after cancelling.",
                    ", ".join(
                        [
                            pending_task.get_name()  # noqa: WPS441
                            for pending_task in pending
                        ],
                    ),
                )
            done |= pdone

        for done_task in done:
            if not done_task.cancelled():
                exc = done_task.exception()
                if exc:
                    logger.critical(
                        "Task '%s' finished with exception",
                        done_task.get_name(),
                        exc_info=exc,
                    )
                    continue
            logger.debug("Task '%s' finished", done_task.get_name())

    async def _exit(self: "GracefulExitManager") -> NoReturn:
        """Exit application."""
        logger.info("Waiting for exit actions to complete")
        await self._call_exit_callbacks()

        logger.info("Waiting for tasks to complete")
        await self._wait_tasks()

        logger.info("Shutting down resources")
        await self._container.shutdown_resources()  # type: ignore
        sys.exit(0)
