"""A small in-memory request limit, per running instance (the writers are one small team)."""

import math
import time
from collections import deque
from collections.abc import Callable

from app.core.errors import RateLimitedError


class RateLimiter:
    def __init__(
        self,
        max_calls: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_calls = max_calls
        self._window = window_seconds
        self._clock = clock
        self._calls: deque[float] = deque()

    def check(self) -> None:
        """Record one call, or raise `RateLimitedError` if the window is already full."""
        now = self._clock()
        while self._calls and now - self._calls[0] >= self._window:
            self._calls.popleft()
        if len(self._calls) >= self._max_calls:
            raise RateLimitedError(math.ceil(self._window - (now - self._calls[0])))
        self._calls.append(now)
