"""Throttle for `last_seen_at`: one write per user per hour, not one per request."""

import time
import uuid
from collections.abc import Callable

TOUCH_INTERVAL_SECONDS = 3600
MAX_TRACKED = 10_000


class ActivityThrottle:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._last: dict[uuid.UUID, float] = {}

    def due(self, user_id: uuid.UUID) -> bool:
        """True at most once per interval for each user; counts the call as the touch."""
        now = self._clock()
        last = self._last.get(user_id)
        if last is not None and now - last < TOUCH_INTERVAL_SECONDS:
            return False
        if len(self._last) >= MAX_TRACKED:
            self._last.clear()
        self._last[user_id] = now
        return True


throttle = ActivityThrottle()
