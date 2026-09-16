import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict


class RateLimiter:
    """Simple in-memory fixed-window-ish limiter, keyed by an arbitrary
    string (typically client IP). Single-process only - there's no shared
    Redis/store, so this limits each app instance independently rather than
    the deployment as a whole. That's a reasonable default for this phase;
    revisit if/when multiple instances need a shared limit."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
