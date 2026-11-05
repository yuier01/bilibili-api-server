"""上游请求闸门：并发上限 + 超时。

M1 只做这两件事；熔断/令牌桶按 PLAN.md §6.4 在 M2 补。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class Gate:
    def __init__(self, concurrency: int = 6, timeout: float = 12.0) -> None:
        if concurrency < 1:
            raise ValueError("concurrency 必须 >= 1")
        self._sem = asyncio.Semaphore(concurrency)
        self._timeout = timeout
        self.inflight = 0

    async def run(self, factory: Callable[[], Awaitable[T]]) -> T:
        """factory 是零参可调用对象，返回协程。

        传工厂而不是协程，是为了在排队/超时取消时不产生 "never awaited" 警告。
        """
        async with self._sem:
            self.inflight += 1
            try:
                return await asyncio.wait_for(factory(), timeout=self._timeout)
            finally:
                self.inflight -= 1
