"""Async runtime wrapper for Qt apps."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from typing import Any


class AsyncRuntime:
    """独立 asyncio 事件循环线程，避免阻塞 Qt UI 线程。"""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro: Any) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self) -> None:
        def _shutdown() -> None:
            self._loop.stop()

        self._loop.call_soon_threadsafe(_shutdown)
        self._thread.join(timeout=1.5)

