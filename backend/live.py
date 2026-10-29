"""What is happening right now, for the admin dashboard.

- Presence: every request from a signed-in browser (and a heartbeat every 30 s while a TRACE tab is
  open) records when that person was last active and which page they have open.
- Work in progress: long requests (generating, refining, translating, 3D builds, ...) are listed
  from the moment they start until they finish, so the dashboard shows work being done, not only
  work that is finished.
- Changes: a counter bumped by every audit row and every task start/end; the dashboard listens
  on /api/admin/live (server-sent events) and refreshes the moment it moves.

All of this is in memory: it describes the present, the audit log remains the record.
"""

import asyncio
import re
import threading
import time
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.auth.deps import COOKIE_NAME, current_user, require_role
from backend.auth.security import decode_token
from backend.models import User

ACTIVE_S = 120  # seen within two minutes = active now
STREAM_S = 25  # each live stream ends after this; the browser reconnects at once (a server reload never waits on it)

TASKS = [
    (r"/cases/\d+/generate$", "Generating a sketch"),
    (r"/cases/\d+/refine$", "Refining the sketch"),
    (r"/cases/\d+/style$", "Applying a style"),
    (r"/cases/\d+/versions/\d+/photo$", "Making a realistic photo"),
    (r"/cases/\d+/versions/\d+/variants", "Drawing a disguise variant"),
    (r"/cases/\d+/interviews/\d+/generate$", "Sketching from the interview"),
    (r"/cases/\d+/interviews/\d+/assist$", "Checking the free account with AI"),
    (r"/cases/\d+/translate$", "Translating the witness's words"),
    (r"/cases/\d+/body$", "Drawing the full body"),
    (r"/cases/\d+/figure/realistic$", "Building the 3D body"),
    (r"/cases/\d+/figure/kaggle$", "Building 3D on the Kaggle GPU"),
    (r"/cases/\d+/figure/reconstruct$", "Reconstructing 3D from the image"),
    (r"/cases/\d+/figure/blender-jobs$", "Modelling in Blender"),
    (r"/cases/\d+/figure/prompt$", "Changing the 3D figure"),
    (r"/cases/\d+/export", "Exporting"),
]
PAGES = [
    (r"^/cases/\d+/details", "Details"),
    (r"^/cases/\d+/interview", "Interview"),
    (r"^/cases/\d+/styles", "Styles"),
    (r"^/cases/\d+/figure", "Figure"),
    (r"^/cases/\d+/sheet", "Case sheet"),
    (r"^/cases/\d+$", "Sketch"),
    (r"^/cases/?$", "Case list"),
    (r"^/records", "Criminal records"),
    (r"^/dashboard", "Dashboard"),
    (r"^/oversight", "Oversight"),
    (r"^/audit", "Audit log"),
]
CASE_IN = re.compile(r"/cases/(\d+)")


def task_label(method: str, path: str) -> str | None:
    if method not in ("POST", "PUT"):
        return None
    return next((label for pattern, label in TASKS if re.search(pattern, path)), None)


def page_label(path: str | None) -> str | None:
    if not path:
        return None
    return next((label for pattern, label in PAGES if re.search(pattern, path)), None)


def case_of(path: str | None) -> int | None:
    m = CASE_IN.search(path or "")
    return int(m.group(1)) if m else None


class Changes:
    """A counter that moves whenever something the dashboard shows has changed."""

    def __init__(self):
        self.version = 0
        self._cond = threading.Condition()

    def bump(self) -> None:
        with self._cond:
            self.version += 1
            self._cond.notify_all()

    def wait(self, after: int, timeout: float) -> int:
        with self._cond:
            self._cond.wait_for(lambda: self.version != after, timeout)
            return self.version


class Presence:
    def __init__(self):
        self.seen: dict[int, tuple[float, str | None]] = {}  # user id -> (last active, page path)
        self.tasks: dict[str, dict] = {}
        self._lock = threading.Lock()

    def touch(self, user_id: int, page: str | None) -> None:
        with self._lock:
            old = self.seen.get(user_id, (0, None))[1]
            self.seen[user_id] = (time.time(), page or old)

    def start(self, user_id: int, method: str, path: str) -> str | None:
        label = task_label(method, path)
        if label is None:
            return None
        key = uuid.uuid4().hex
        with self._lock:
            self.tasks[key] = {"user_id": user_id, "label": label, "case_id": case_of(path), "started": time.time()}
        return key

    def finish(self, key: str) -> None:
        with self._lock:
            self.tasks.pop(key, None)

    def forget(self, user_id: int) -> None:
        with self._lock:
            self.seen.pop(user_id, None)


async def track(request: Request, call_next):
    """Middleware: note who is active (and on which page), and list long requests while they run."""
    path = request.url.path
    state = request.app.state
    user_id = None
    token = request.cookies.get(COOKIE_NAME)
    if token and path.startswith("/api/") and path != "/api/admin/live":
        try:
            user_id = int(decode_token(token, state.settings)["sub"])
        except Exception:
            user_id = None
    if user_id is None:
        return await call_next(request)
    state.presence.touch(user_id, request.headers.get("x-trace-page"))
    key = state.presence.start(user_id, request.method, path)
    if key is None:
        return await call_next(request)
    state.changes.bump()
    try:
        return await call_next(request)
    finally:
        state.presence.finish(key)
        state.changes.bump()


router = APIRouter(tags=["live"])


class HeartbeatIn(BaseModel):
    page: str | None = Field(default=None, max_length=300)


@router.post("/api/auth/heartbeat", status_code=204)
def heartbeat(body: HeartbeatIn, request: Request, user: User = Depends(current_user)):
    """Sent every 30 s by an open TRACE tab; not audited (it is presence, not an action)."""
    request.app.state.presence.touch(user.id, body.page)
    request.app.state.changes.bump()
    return Response(status_code=204)


@router.get("/api/admin/live")
async def live(request: Request, limit: int = Query(0, ge=0), user: User = Depends(require_role("admin"))):
    """Server-sent events: one "data" line whenever the dashboard's data has changed."""
    changes: Changes = request.app.state.changes

    async def events():
        version, sent = changes.version, 1
        ends = time.monotonic() + STREAM_S
        yield f"retry: 1000\ndata: {version}\n\n"
        while (not limit or sent < limit) and time.monotonic() < ends:
            if await request.is_disconnected():
                return
            new = await asyncio.to_thread(changes.wait, version, 5)
            if new == version:
                yield ": still here\n\n"
                continue
            version, sent = new, sent + 1
            yield f"data: {version}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
