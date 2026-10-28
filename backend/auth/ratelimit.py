import time
from collections import defaultdict

from backend.errors import AppError

WINDOW_SECONDS = 600
MAX_FAILURES = 5


class LoginLimiter:
    def __init__(self):
        self._failures: dict[str, list[float]] = defaultdict(list)

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

    def reset(self, username: str) -> None:
        self._failures.pop(username, None)
