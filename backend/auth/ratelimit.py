import time
from collections import defaultdict

from backend.errors import AppError

WINDOW_SECONDS = 600
MAX_FAILURES = 5
SWEEP_EVERY = 1000  # failures between sweeps of usernames whose window has passed


class LoginLimiter:
    def __init__(self):
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._since_sweep = 0

    def _recent(self, username: str) -> list[float]:
        cutoff = time.monotonic() - WINDOW_SECONDS
        recent = [t for t in self._failures[username] if t > cutoff]
        self._failures[username] = recent
        return recent

    def check(self, username: str) -> None:
        if len(self._recent(username)) >= MAX_FAILURES:
            raise AppError("RATE_LIMITED", "Too many failed logins. Try again in 10 minutes.", 429)

    def fail(self, username: str) -> None:
        self._failures[username].append(time.monotonic())
        self._since_sweep += 1
        if self._since_sweep >= SWEEP_EVERY:
            self._sweep()

    def _sweep(self) -> None:
        # without this, every username ever tried stays in memory
        self._since_sweep = 0
        cutoff = time.monotonic() - WINDOW_SECONDS
        for name in [n for n, times in self._failures.items() if not times or times[-1] <= cutoff]:
            del self._failures[name]

    def reset(self, username: str) -> None:
        self._failures.pop(username, None)
