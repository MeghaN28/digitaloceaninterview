import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Deque, Dict, List, Optional

_MAX_SAMPLES = 500  # ring buffer per key, keeps memory bounded


def _percentile(sorted_values: List[float], pct: float) -> Optional[float]:
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if f == c:
        return round(sorted_values[f], 2)
    return round(sorted_values[f] * (c - k) + sorted_values[c] * (k - f), 2)


class Metrics:
    """In-memory latency/count tracking, keyed by an arbitrary label (e.g.
    "POST /v1/images" or "local_repo.add_thumbnail"). Single-process only -
    same tradeoff as the rate limiter, no shared store. Good enough to see
    where latency is going without pulling in Prometheus/OTel for this
    phase."""

    def __init__(self, max_samples: int = _MAX_SAMPLES):
        self._samples: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=max_samples))
        self._counts: Dict[str, int] = defaultdict(int)
        self._errors: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record(self, key: str, duration_ms: float, is_error: bool = False) -> None:
        with self._lock:
            self._samples[key].append(duration_ms)
            self._counts[key] += 1
            if is_error:
                self._errors[key] += 1

    def snapshot(self) -> Dict[str, dict]:
        with self._lock:
            out = {}
            for key, samples in self._samples.items():
                values = sorted(samples)
                out[key] = {
                    "count": self._counts[key],
                    "errors": self._errors[key],
                    "p50_ms": _percentile(values, 50),
                    "p95_ms": _percentile(values, 95),
                    "p99_ms": _percentile(values, 99),
                    "max_ms": values[-1] if values else None,
                }
            return out

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._counts.clear()
            self._errors.clear()


@contextmanager
def timed(metrics: Metrics, key: str):
    start = time.monotonic()
    is_error = False
    try:
        yield
    except Exception:
        is_error = True
        raise
    finally:
        metrics.record(key, (time.monotonic() - start) * 1000, is_error=is_error)


# Two separate registries so "how slow are my endpoints" and "how slow is the
# storage layer under them" can be read independently - a slow POST with a
# fast db op points at image processing (Pillow), a slow db op points at
# lock contention/Mongo latency.
http_metrics = Metrics()
db_metrics = Metrics()
