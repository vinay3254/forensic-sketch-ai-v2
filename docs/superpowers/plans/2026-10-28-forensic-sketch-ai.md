# AI Crime Scene Sketch Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a secure web app where an officer turns a witness description into a realistic face, refines it by chat, exports photo and sketch versions, and every case access is recorded in a tamper-evident audit log.

**Architecture:** React SPA (Vite) talks to a FastAPI backend through a Vite dev proxy (same origin, so the `SameSite=Strict` cookie works). The backend stores users, cases, face versions, chat and audit rows in SQLite (SQLModel) and images on disk. All AI work goes through one OpenAI-compatible LLM service (chat + `images.generate` + `images.edit`) behind `backend/ai/client.py`, which has a mock mode for tests and offline demos.

**Tech Stack:** Python 3.12 (via `uv`), FastAPI, SQLModel, PyJWT, bcrypt, openai SDK, Pillow, opencv-python-headless, pytest + httpx; Node 26, Vite, React, TypeScript, Tailwind, React Router, TanStack Query.

**Spec:** `docs/superpowers/specs/2026-10-28-forensic-sketch-ai-design.md`

## Global Constraints

- Python 3.12 virtual environment created with `uv` (system Python 3.14 is not used).
- Backend never imports a vendor SDK other than `openai`; LLM endpoint comes only from `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_CHAT_MODEL`, `LLM_IMAGE_MODEL`.
- Image defaults: `LLM_IMAGE_SIZE=1024x1536`, `LLM_IMAGE_QUALITY=medium`.
- Timeouts: chat 30 s, image 120 s; one retry on timeout or 5xx.
- JWT HS256, 8-hour expiry, cookie name `session`, `httpOnly`, `SameSite=Strict`, `Secure` controlled by `COOKIE_SECURE` (default `true`; `false` in `.env.example` for local http).
- Login limit: 5 failed logins per username per 10 minutes, then HTTP 429.
- Description and chat message max length: 2000 characters.
- Export: long side 2048 px, PNG, footer with case number, version number, export time (UTC ISO), exporting username.
- Data sent to the LLM: facial description, edit text, current image only. Never case number, title, username or location.
- Prompts contain no crime wording ("suspect", "criminal", "mugshot").
- Audit actions (exact strings): `login`, `login_failed`, `logout`, `case_create`, `case_list`, `case_open`, `image_view`, `generate`, `refine`, `revert`, `export`, `audit_view`, `access_denied`.
- Error body shape: `{"error": {"code": "<CODE>", "message": "<text>"}}` with codes `UNAUTHENTICATED` 401, `FORBIDDEN` 403, `NOT_FOUND` 404, `VALIDATION` 422, `AI_PARSE_FAILED` 422, `AI_REFUSED` 422, `AI_UNAVAILABLE` 503, plus `CONFLICT` 409 and `RATE_LIMITED` 429 (added by this plan).
- All backend tests run with `AI_MOCK=1` and no network.

## Review Focus

1. **Double-submitted refine** (officer clicks twice): two requests race for the same `version_no`. Expect one to succeed and the other to get 409 `CONFLICT`, never two rows with the same number. Test in Task 6.
2. **Refine or export before any face exists**: expect 409 `CONFLICT` "Generate a face first", not a 500. Test in Task 6.
3. **Tampered or expired session cookie**: expect 401 `UNAUTHENTICATED`, not 500. Test in Task 2.
4. **LLM returns a region outside the fixed list or extra prose around the JSON**: expect JSON extracted from the reply, unknown regions rejected by the schema, one guided retry, then `AI_PARSE_FAILED`. Test in Task 5.
5. **Image service returns a URL instead of base64** (provider differences): expect the client to fetch the bytes either way. Test in Task 5.

---

## File Structure

```text
forensic-sketch-ai/
├── pyproject.toml                  # uv project, deps, pytest config
├── .env.example
├── .gitignore                      # .env, storage/, *.db, node_modules, dist, .venv
├── backend/
│   ├── __init__.py
│   ├── app.py                      # create_app(): routers, error handlers, CORS
│   ├── config.py                   # Settings (pydantic-settings), get_settings()
│   ├── db.py                       # engine, init_db(), get_session()
│   ├── models.py                   # User, Case, FaceVersion, ChatMessage, AuditLog
│   ├── errors.py                   # AppError + handlers
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── security.py             # hash/verify password, encode/decode JWT
│   │   ├── deps.py                 # current_user, require_role, require_case_access
│   │   ├── ratelimit.py            # in-memory failed-login limiter
│   │   └── routes.py               # /api/auth/*
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── logger.py               # record(), compute_hash(), verify_chain()
│   │   └── routes.py               # /api/audit, /api/audit/verify
│   ├── cases/
│   │   ├── __init__.py
│   │   └── routes.py               # /api/cases list/create/detail
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── schemas.py              # Attributes, Region, Edit, EditPlan
│   │   ├── prompts.py              # system prompts, build_image_prompt, build_edit_prompt
│   │   ├── client.py               # AIClient (live) + get_ai_client()
│   │   └── mock.py                 # MockAIClient
│   ├── face/
│   │   ├── __init__.py
│   │   ├── service.py              # generate_face, refine_face, revert_face, storage helpers
│   │   └── routes.py               # generate/refine/versions/revert/image
│   ├── export/
│   │   ├── __init__.py
│   │   ├── render.py               # upscale, to_sketch, stamp_footer
│   │   └── routes.py               # export endpoint
│   ├── seed.py                     # demo users + demo case
│   └── tests/
│       ├── conftest.py             # app/client fixtures, tmp DB + storage, login helper
│       ├── test_health.py
│       ├── test_auth.py
│       ├── test_audit.py
│       ├── test_cases.py
│       ├── test_ai_client.py
│       ├── test_face.py
│       └── test_export.py
└── frontend/
    ├── package.json, vite.config.ts, tailwind config, index.html
    └── src/
        ├── main.tsx, App.tsx       # router + QueryClient + auth guard
        ├── api.ts                  # fetch wrapper + typed endpoint functions
        ├── types.ts                # shared TS types mirroring API
        ├── pages/
        │   ├── LoginPage.tsx
        │   ├── CasesPage.tsx
        │   ├── WorkspacePage.tsx
        │   └── AuditPage.tsx
        └── components/
            ├── DescriptionForm.tsx
            ├── RefineChat.tsx
            ├── FaceCanvas.tsx
            ├── VersionStrip.tsx
            └── AttributePanel.tsx
```

---

### Task 1: Backend skeleton, config, models, health

**Files:**
- Create: `pyproject.toml`, `.env.example`, `.gitignore`, `backend/__init__.py`, `backend/config.py`, `backend/db.py`, `backend/models.py`, `backend/errors.py`, `backend/app.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces:
  - `Settings` fields: `jwt_secret: str`, `jwt_expiry_hours: int = 8`, `cookie_secure: bool = True`, `database_url: str = "sqlite:///./app.db"`, `storage_dir: Path = Path("./storage")`, `frontend_origin: str = "http://localhost:5173"`, `llm_base_url: str = ""`, `llm_api_key: str = ""`, `llm_chat_model: str = ""`, `llm_image_model: str = ""`, `llm_image_size: str = "1024x1536"`, `llm_image_quality: str = "medium"`, `ai_mock: bool = False`. `get_settings() -> Settings` (lru_cache).
  - `init_db(engine) -> None`, `get_session() -> Iterator[Session]` (FastAPI dependency), `make_engine(url: str) -> Engine` (SQLite with `check_same_thread=False`).
  - Models (SQLModel, `table=True`): `User(id, username unique, password_hash, role: str, created_at)`, `Case(id, case_number unique, title, created_by FK, status="open", created_at)`, `FaceVersion(id, case_id FK, parent_id FK nullable, version_no, kind, instruction, attributes: dict JSON column, prompt, image_path, created_by FK, created_at)` with `UniqueConstraint("case_id", "version_no")`, `ChatMessage(id, case_id FK, role, content, version_id nullable, created_at)`, `AuditLog(id, ts, user_id nullable, username, role, action, case_id nullable, version_id nullable, ip, user_agent, detail: dict JSON, prev_hash, hash)`. All `created_at`/`ts` are timezone-aware UTC.
  - `AppError(code: str, message: str, status: int)` exception; `register_error_handlers(app)` mapping `AppError` and `RequestValidationError` (→ `VALIDATION`, 422) to the error body shape.
  - `create_app(settings: Settings | None = None) -> FastAPI`; stores engine on `app.state.engine`; `GET /health` → `{"status": "ok", "db": "ok", "ai_mode": "mock" | "live"}`.
  - Test fixtures: `settings` (tmp DB file, tmp storage dir, `ai_mock=True`, `jwt_secret="test"`, `cookie_secure=False`), `app`, `client` (`TestClient`).

- [ ] **Step 1: Init repo and uv project**

Run: `cd ~/forensic-sketch-ai && git init && uv python install 3.12 && uv init --python 3.12 --no-workspace --bare && uv add fastapi uvicorn sqlmodel pydantic-settings pyjwt bcrypt openai pillow opencv-python-headless python-multipart httpx && uv add --dev pytest`
Expected: `.venv` created, `uv run python --version` prints `Python 3.12.x`.

Add to `pyproject.toml`: `[tool.pytest.ini_options] testpaths = ["backend/tests"]`. Write `.gitignore` and `.env.example` with every `Settings` field in upper case (`COOKIE_SECURE=false`, `AI_MOCK=1`).

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_health.py
def test_health_reports_ok_and_mock_mode(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok", "ai_mode": "mock"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_health.py -v`
Expected: FAIL (`ModuleNotFoundError: backend.app`).

- [ ] **Step 4: Implement config, db, models, errors, app as listed in Interfaces**

`create_app` calls `init_db` on startup (lifespan) and creates `settings.storage_dir`. CORS allows only `settings.frontend_origin` with credentials.

- [ ] **Step 5: Run tests**

Run: `uv run pytest -v`
Expected: `test_health_reports_ok_and_mock_mode` PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: backend skeleton with config, models, health"
```

---

### Task 2: Authentication, sessions, roles, login rate limit

**Files:**
- Create: `backend/auth/__init__.py`, `backend/auth/security.py`, `backend/auth/deps.py`, `backend/auth/ratelimit.py`, `backend/auth/routes.py`, `backend/seed.py`
- Modify: `backend/app.py` (include auth router)
- Test: `backend/tests/test_auth.py`; add `seed_users` fixture and `login` fixture (returns a function `login(client, username, password)` that posts to `/api/auth/login` after clearing cookies and asserts 200) to `conftest.py`

**Interfaces:**
- Consumes: `Settings`, `get_session`, `User`, `AppError` (Task 1).
- Produces:
  - `hash_password(pw: str) -> str`, `verify_password(pw: str, hashed: str) -> bool`
  - `create_token(user_id: int, role: str, settings: Settings) -> str`, `decode_token(token: str, settings: Settings) -> dict` (raises `AppError("UNAUTHENTICATED", ..., 401)` on bad signature or expiry)
  - `current_user(request: Request, session: Session) -> User` dependency (reads cookie `session`)
  - `require_role(*roles: str)` → dependency returning `User`, raises 403 `FORBIDDEN`
  - `LoginLimiter.check(username: str) -> None` (raises 429 `RATE_LIMITED`), `.fail(username)`, `.reset(username)`; window 600 s, max 5 failures
  - Routes: `POST /api/auth/login {username, password}` → `{"id", "username", "role"}` + cookie; `POST /api/auth/logout`; `GET /api/auth/me`
  - `seed_users(session) -> None`: creates `officer1`/`officer1pass` (officer), `officer2`/`officer2pass` (officer), `admin`/`adminpass` (admin) if absent
  - Login and logout write audit rows **after Task 3 lands**; Task 3 adds those calls.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_auth.py
def test_login_sets_httponly_cookie_and_me_returns_user(client, seed_users):
    r = client.post("/api/auth/login", json={"username": "officer1", "password": "officer1pass"})
    assert r.status_code == 200
    assert r.json()["role"] == "officer"
    cookie = r.headers["set-cookie"].lower()
    assert "session=" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/auth/me").json()["username"] == "officer1"

def test_wrong_password_is_401(client, seed_users):
    r = client.post("/api/auth/login", json={"username": "officer1", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"

def test_sixth_failed_login_is_rate_limited(client, seed_users):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "officer1", "password": "x"})
    r = client.post("/api/auth/login", json={"username": "officer1", "password": "officer1pass"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"

def test_me_without_cookie_is_401(client):
    assert client.get("/api/auth/me").status_code == 401

def test_tampered_cookie_is_401_not_500(client, seed_users):
    client.cookies.set("session", "not.a.jwt")
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"

def test_expired_token_is_401(client, seed_users, settings):
    from backend.auth.security import create_token
    expired = settings.model_copy(update={"jwt_expiry_hours": -1})
    client.cookies.set("session", create_token(1, "officer", expired))
    assert client.get("/api/auth/me").status_code == 401

def test_validation_error_uses_error_shape(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION"

def test_logout_clears_session(client, seed_users):
    client.post("/api/auth/login", json={"username": "officer1", "password": "officer1pass"})
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest backend/tests/test_auth.py -v`
Expected: FAIL (404 on `/api/auth/login`).

- [ ] **Step 3: Implement security, deps, limiter, routes, seed as listed in Interfaces**

The limiter instance lives on `app.state` so each test app gets a fresh one. A failed login for an unknown username also counts and returns the same 401 message as a wrong password.

- [ ] **Step 4: Run tests**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: JWT cookie auth, roles, login rate limit"
```

---

### Task 3: Audit logger with hash chain, audit API

**Files:**
- Create: `backend/audit/__init__.py`, `backend/audit/logger.py`, `backend/audit/routes.py`
- Modify: `backend/auth/routes.py` (record `login`, `login_failed`, `logout`), `backend/app.py`
- Test: `backend/tests/test_audit.py`

**Interfaces:**
- Consumes: `AuditLog`, `User`, `current_user`, `require_role` (Tasks 1–2).
- Produces:
  - `record(session: Session, request: Request, action: str, user: User | None = None, *, username: str | None = None, case_id: int | None = None, version_id: int | None = None, detail: dict | None = None) -> AuditLog` — fills `ip` from `request.client.host`, `user_agent` from header, reads the latest row's `hash` as `prev_hash` (`"0" * 64` if none), computes `hash`, commits.
  - `compute_hash(prev_hash: str, ts: datetime, user_id: int | None, action: str, case_id: int | None, version_id: int | None, detail: dict) -> str` — `sha256` hex of `"|".join([prev_hash, ts.isoformat(), str(user_id), action, str(case_id), str(version_id), json.dumps(detail, sort_keys=True)])`.
  - `verify_chain(session) -> dict` → `{"ok": True, "rows": n}` or `{"ok": False, "rows": n, "first_bad_id": id}`.
  - `GET /api/audit?case_id=&user_id=&action=&since=&until=&page=1&page_size=50` (admin) → `{"items": [AuditLog...], "total": n}` newest first; records `audit_view`.
  - `GET /api/audit/verify` (admin) → `verify_chain` result; records `audit_view`.
  - `login_failed` rows store `username` from the request body, `user_id` null.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_audit.py
def test_login_and_failed_login_are_audited(client, seed_users, login):
    client.post("/api/auth/login", json={"username": "officer1", "password": "bad"})
    login(client, "admin", "adminpass")
    items = client.get("/api/audit").json()["items"]
    actions = [i["action"] for i in items]
    assert "login_failed" in actions and "login" in actions
    failed = next(i for i in items if i["action"] == "login_failed")
    assert failed["username"] == "officer1" and failed["user_id"] is None

def test_officer_cannot_read_audit(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    assert client.get("/api/audit").status_code == 403

def test_chain_verifies_then_detects_tampering(client, seed_users, login, app):
    login(client, "admin", "adminpass")
    client.get("/api/audit")
    assert client.get("/api/audit/verify").json()["ok"] is True
    from sqlmodel import Session, select
    from backend.models import AuditLog
    with Session(app.state.engine) as s:
        row = s.exec(select(AuditLog).order_by(AuditLog.id)).first()
        row.action = "logout"
        s.add(row); s.commit()
        bad_id = row.id
    result = client.get("/api/audit/verify").json()
    assert result["ok"] is False and result["first_bad_id"] == bad_id
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest backend/tests/test_audit.py -v`
Expected: FAIL (404 on `/api/audit`).

- [ ] **Step 3: Implement logger and routes; add audit calls to login/logout**

`verify_chain` walks rows by ascending `id`, recomputing each hash from the previous row's stored `hash`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: hash-chained audit log and admin audit API"
```

---

### Task 4: Cases API and case access control

**Files:**
- Create: `backend/cases/__init__.py`, `backend/cases/routes.py`
- Modify: `backend/auth/deps.py` (add `require_case_access`), `backend/app.py`
- Test: `backend/tests/test_cases.py`

**Interfaces:**
- Consumes: `current_user`, `record`, `Case`, `FaceVersion`, `ChatMessage`.
- Produces:
  - `require_case_access(case_id: int, request: Request, user = Depends(current_user), session = Depends(get_session)) -> Case` — 404 `NOT_FOUND` if missing; if the user is an officer and `case.created_by != user.id`, records `access_denied` (with `case_id`) and raises 403 `FORBIDDEN`. Admin always passes.
  - `next_case_number(session) -> str` → `"BLR-2026-0001"` style, zero-padded 4 digits, year from current UTC date.
  - `POST /api/cases {title: str (1–200 chars)}` → `CaseOut {id, case_number, title, status, created_at, created_by}`; audit `case_create`.
  - `GET /api/cases` → `list[CaseOut]` (officer: own; admin: all), newest first; audit `case_list`.
  - `GET /api/cases/{case_id}` → `{case: CaseOut, versions: list[VersionOut], chat: list[ChatOut]}`; audit `case_open`. `VersionOut {id, version_no, kind, instruction, attributes, created_at, image_url}` where `image_url = f"/api/cases/{case_id}/versions/{id}/image"`. `ChatOut {id, role, content, version_id, created_at}`. These schemas live in `backend/cases/routes.py` and are imported by Task 6.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_cases.py
def test_create_and_list_own_cases(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    c = client.post("/api/cases", json={"title": "Chain snatching, Yelahanka"}).json()
    assert c["case_number"].startswith("BLR-2026-")
    assert [x["id"] for x in client.get("/api/cases").json()] == [c["id"]]

def test_other_officer_gets_403_and_access_denied_is_audited(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    login(client, "officer2", "officer2pass")
    r = client.get(f"/api/cases/{cid}")
    assert r.status_code == 403
    assert client.get("/api/cases").json() == []
    login(client, "admin", "adminpass")
    denied = client.get(f"/api/audit?action=access_denied&case_id={cid}").json()["items"]
    assert len(denied) == 1 and denied[0]["username"] == "officer2"

def test_admin_sees_all_cases_and_open_is_audited(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    login(client, "admin", "adminpass")
    assert client.get(f"/api/cases/{cid}").status_code == 200
    opened = client.get(f"/api/audit?action=case_open&case_id={cid}").json()["items"]
    assert len(opened) == 1

def test_missing_case_is_404(client, seed_users, login):
    login(client, "admin", "adminpass")
    assert client.get("/api/cases/999").json()["error"]["code"] == "NOT_FOUND"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest backend/tests/test_cases.py -v`
Expected: FAIL (404 on `/api/cases`).

- [ ] **Step 3: Implement `require_case_access`, `next_case_number`, and routes**

- [ ] **Step 4: Run tests**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: cases API with ownership checks and access_denied audit"
```

---

### Task 5: AI client — schemas, prompts, live client, mock

**Files:**
- Create: `backend/ai/__init__.py`, `backend/ai/schemas.py`, `backend/ai/prompts.py`, `backend/ai/client.py`, `backend/ai/mock.py`
- Test: `backend/tests/test_ai_client.py`

**Interfaces:**
- Consumes: `Settings`, `AppError`.
- Produces:
  - `Attributes` (Pydantic): all fields from spec section 4 as `str | None = None`: `gender, age_range, skin_tone, face_shape, jaw, eyes, eyebrows, nose, mouth, ears, hair, facial_hair, marks, accessories, notes`.
  - `Region = Literal["face_shape","jaw","eyes","eyebrows","nose","mouth","ears","hair","facial_hair","skin_tone","marks","age_range","accessories"]`
  - `Edit(region: Region, change: str)`, `EditPlan(edits: list[Edit], reply: str, needs_clarification: bool = False)`
  - `ATTRIBUTE_SYSTEM_PROMPT`, `EDIT_SYSTEM_PROMPT` (both instruct: reply with one JSON object only, matching the given JSON schema; never invent features the witness did not mention).
  - `build_image_prompt(a: Attributes) -> str` — spec 5.1 template; null fields and their connecting words are omitted.
  - `build_edit_prompt(edits: list[Edit]) -> str` — spec 5.2 template.
  - `apply_edits(a: Attributes, edits: list[Edit]) -> Attributes` — sets each `edit.region` field to the new value: `f"{old}, {change}"` if old exists, else `change`.
  - `class AIClient(Protocol)`: `extract_attributes(text: str) -> Attributes`; `parse_edit(message: str, current: Attributes) -> EditPlan`; `generate_image(prompt: str) -> bytes` (PNG); `edit_image(image: bytes, prompt: str) -> bytes`.
  - `LiveAIClient(settings, openai_client: OpenAI | None = None)` implementing it via `chat.completions.create`, `images.generate`, `images.edit` with the timeouts and one retry from Global Constraints.
  - `extract_json(text: str) -> dict` — returns the first `{...}` object in text (handles code fences and surrounding prose).
  - `_structured(system, user, model_cls)` private helper: call chat → `extract_json` → `model_cls.model_validate`; on failure, call once more with the validation error appended; then raise `AppError("AI_PARSE_FAILED", ..., 422)`.
  - Image response handling: use `data[0].b64_json` if present, else download `data[0].url` with `httpx` (timeout 60 s).
  - Error mapping: `openai.APITimeoutError`/`APIConnectionError`/5xx → `AI_UNAVAILABLE` 503; `openai.BadRequestError` whose message contains `safety`, `policy` or `content` → `AI_REFUSED` 422.
  - `MockAIClient`: `extract_attributes` uses whole-word keyword rules (so "female" never matches "male") (`male/man` → gender male, `female/woman` → female, digits followed by `s` or "years" → age_range, words "beard", "moustache", "stubble" → facial_hair, "scar" sentence fragment → marks); `parse_edit` maps region keywords (`jaw`, `eye`, `nose`, `lip`/`mouth`, `hair`, `beard`/`moustache`, `scar`) to `Edit`s and sets `needs_clarification=True` when none match; images are 1024×1536 grey PNGs with the prompt's first 80 chars drawn on them.
  - `get_ai_client(request: Request) -> AIClient` dependency: returns `app.state.ai_client` (created in `create_app`: mock when `settings.ai_mock`, else live). Tests may replace `app.state.ai_client`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_ai_client.py
import base64, pytest
from types import SimpleNamespace
from backend.ai.schemas import Attributes, Edit
from backend.ai.prompts import build_image_prompt, build_edit_prompt, apply_edits
from backend.ai.client import LiveAIClient, extract_json
from backend.errors import AppError

def test_image_prompt_skips_nulls_and_has_no_crime_words():
    p = build_image_prompt(Attributes(gender="male", age_range="30-35", nose="broad"))
    assert "30-35 male" in p and "broad nose" in p and "None" not in p
    for w in ("suspect", "criminal", "mugshot"):
        assert w not in p.lower()

def test_edit_prompt_lists_changes_and_preserves_identity():
    p = build_edit_prompt([Edit(region="jaw", change="wider")])
    assert "jaw: wider" in p and "same person" in p

def test_apply_edits_appends_to_existing_value():
    a = apply_edits(Attributes(jaw="square"), [Edit(region="jaw", change="wider")])
    assert a.jaw == "square, wider"

def test_extract_json_handles_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"gender": "male"}\n```') == {"gender": "male"}

class FakeChat:
    def __init__(self, replies): self.replies, self.calls = list(replies), 0
    def create(self, **kw):
        self.calls += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.replies.pop(0)))])

def fake_openai(chat=None, images=None):
    return SimpleNamespace(chat=SimpleNamespace(completions=chat), images=images)

def test_parse_edit_rejects_unknown_region_then_retries(settings):
    chat = FakeChat(['{"edits":[{"region":"tattoo","change":"x"}],"reply":"ok"}',
                     '{"edits":[{"region":"nose","change":"smaller"}],"reply":"ok"}'])
    plan = LiveAIClient(settings, fake_openai(chat)).parse_edit("smaller nose", Attributes())
    assert plan.edits[0].region == "nose" and chat.calls == 2

def test_parse_fails_after_one_retry(settings):
    chat = FakeChat(["not json", "still not json"])
    with pytest.raises(AppError) as e:
        LiveAIClient(settings, fake_openai(chat)).extract_attributes("tall man")
    assert e.value.code == "AI_PARSE_FAILED" and chat.calls == 2

def test_generate_image_accepts_b64(settings):
    png = b"\x89PNG fake"
    images = SimpleNamespace(generate=lambda **kw: SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png).decode(), url=None)]))
    assert LiveAIClient(settings, fake_openai(images=images)).generate_image("p") == png

def test_generate_image_accepts_url(settings, monkeypatch):
    images = SimpleNamespace(generate=lambda **kw: SimpleNamespace(data=[SimpleNamespace(b64_json=None, url="http://img/x.png")]))
    monkeypatch.setattr("backend.ai.client.httpx.get", lambda url, timeout: SimpleNamespace(content=b"bytes", raise_for_status=lambda: None))
    assert LiveAIClient(settings, fake_openai(images=images)).generate_image("p") == b"bytes"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest backend/tests/test_ai_client.py -v`
Expected: FAIL (`ModuleNotFoundError: backend.ai`).

- [ ] **Step 3: Implement schemas, prompts, live client, mock, and wire `app.state.ai_client` in `create_app`**

`images.generate` call: `model=settings.llm_image_model, prompt=prompt, size=settings.llm_image_size, quality=settings.llm_image_quality, n=1`. `images.edit`: same plus `image=("face.png", image_bytes, "image/png")`. The chat call passes `response_format={"type": "json_object"}`, and if the service rejects that parameter with `BadRequestError`, retries without it.

- [ ] **Step 4: Run tests**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: AI client with schema-validated JSON, image calls, mock mode"
```

---

### Task 6: Face service and routes — generate, refine, revert, image

**Files:**
- Create: `backend/face/__init__.py`, `backend/face/service.py`, `backend/face/routes.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_face.py`

**Interfaces:**
- Consumes: `require_case_access`, `record`, `get_ai_client`, `AIClient`, `Attributes`, `build_image_prompt`, `build_edit_prompt`, `apply_edits`, `VersionOut`, `ChatOut`, `FaceVersion`, `ChatMessage`.
- Produces:
  - `save_image(settings, case_id: int, version_no: int, data: bytes) -> str` → relative path `cases/<case_id>/v<version_no>.png` under `storage_dir`.
  - `latest_version(session, case_id) -> FaceVersion | None`.
  - `generate_face(session, ai, settings, case, user, description) -> FaceVersion` — extract → prompt → image → new version (`kind="generate"`, `parent_id` = latest id or None) + chat rows (user: description, assistant: "Here is the first face. Tell me what to change.").
  - `refine_face(session, ai, settings, case, user, message) -> tuple[FaceVersion | None, str]` — 409 `CONFLICT` "Generate a face first" if no version; if `needs_clarification`, store both chat rows and return `(None, reply)`; else merge attributes, `edit_image` on the latest image, new version (`kind="refine"`).
  - `revert_face(session, settings, case, user, version_id) -> FaceVersion` — copies the image file and attributes to a new version (`kind="revert"`, `instruction=f"Revert to v{n}"`).
  - New `version_no` = latest + 1. On `IntegrityError` from the unique constraint, roll back, delete the written image, raise 409 `CONFLICT` "Another change is in progress. Reload and try again."
  - Request bodies: `GenerateIn {description: str, 1–2000 chars}`, `RefineIn {message: str, 1–2000 chars}`.
  - Routes (all use `require_case_access`):
    - `POST /api/cases/{case_id}/generate` → `VersionOut`; audit `generate` with `version_id`.
    - `POST /api/cases/{case_id}/refine` → `{"version": VersionOut | None, "reply": str}`; audit `refine` with `version_id` (null when clarification) and `detail={"message": message}`.
    - `GET /api/cases/{case_id}/versions` → `list[VersionOut]`.
    - `POST /api/cases/{case_id}/versions/{version_id}/revert` → `VersionOut`; audit `revert`.
    - `GET /api/cases/{case_id}/versions/{version_id}/image` → PNG `FileResponse`; 404 if the version belongs to another case; audit `image_view`.
  - AI calls run before the DB write, so a failed AI call creates no version and no image file.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_face.py
import pytest
from backend.errors import AppError

@pytest.fixture
def case_id(client, seed_users, login):
    login(client, "officer1", "officer1pass")
    return client.post("/api/cases", json={"title": "t"}).json()["id"]

def test_generate_creates_v1_with_image(client, case_id):
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s, scar on left cheek"}).json()
    assert v["version_no"] == 1 and v["kind"] == "generate" and v["attributes"]["gender"] == "male"
    img = client.get(v["image_url"])
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"

def test_refine_creates_v2_with_merged_attributes(client, case_id):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male, 30s"})
    r = client.post(f"/api/cases/{case_id}/refine", json={"message": "make the jaw wider"}).json()
    assert r["version"]["version_no"] == 2 and "wider" in r["version"]["attributes"]["jaw"]

def test_unclear_refine_creates_no_version(client, case_id):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    r = client.post(f"/api/cases/{case_id}/refine", json={"message": "hmm not quite"}).json()
    assert r["version"] is None and r["reply"]
    assert len(client.get(f"/api/cases/{case_id}/versions").json()) == 1

def test_refine_before_generate_is_409(client, case_id):
    r = client.post(f"/api/cases/{case_id}/refine", json={"message": "wider jaw"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"

def test_revert_copies_old_version_as_new(client, case_id):
    v1 = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"}).json()
    client.post(f"/api/cases/{case_id}/refine", json={"message": "bigger nose"})
    v3 = client.post(f"/api/cases/{case_id}/versions/{v1['id']}/revert").json()
    assert v3["version_no"] == 3 and v3["kind"] == "revert" and v3["attributes"] == v1["attributes"]

def test_duplicate_version_no_is_409(client, case_id, app, monkeypatch):
    client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    import backend.face.service as svc
    monkeypatch.setattr(svc, "latest_version", lambda session, cid: None)  # simulate a stale read in a race
    r = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"

def test_description_over_2000_chars_is_422(client, case_id):
    r = client.post(f"/api/cases/{case_id}/generate", json={"description": "a" * 2001})
    assert r.status_code == 422

def test_ai_failure_creates_no_version(client, case_id, app):
    class Down:
        def extract_attributes(self, t): raise AppError("AI_UNAVAILABLE", "down", 503)
    app.state.ai_client = Down()
    r = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"})
    assert r.status_code == 503
    assert client.get(f"/api/cases/{case_id}/versions").json() == []

def test_other_officer_cannot_fetch_image(client, case_id, login):
    v = client.post(f"/api/cases/{case_id}/generate", json={"description": "male"}).json()
    login(client, "officer2", "officer2pass")
    assert client.get(v["image_url"]).status_code == 403
```

In `test_duplicate_version_no_is_409`, `latest_version` returning `None` makes the service compute `version_no=1` again, which hits the unique constraint.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest backend/tests/test_face.py -v`
Expected: FAIL (404 on `/generate`).

- [ ] **Step 3: Implement service and routes as listed in Interfaces**

- [ ] **Step 4: Run tests**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: generate, refine, revert faces with version history"
```

---

### Task 7: Export — upscale, pencil sketch, footer

**Files:**
- Create: `backend/export/__init__.py`, `backend/export/render.py`, `backend/export/routes.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_export.py`

**Interfaces:**
- Consumes: `require_case_access`, `record`, `FaceVersion`, `Settings`.
- Produces:
  - `upscale(img: Image.Image, long_side: int = 2048) -> Image.Image` (Lanczos, keeps aspect ratio).
  - `to_sketch(img: Image.Image) -> Image.Image` — grayscale → invert → `GaussianBlur((21, 21), 0)` → colour dodge `cv2.divide(gray, 255 - blurred, scale=256)` → mild contrast (`alpha=1.15`); returns mode `"L"`.
  - `stamp_footer(img: Image.Image, lines: list[str]) -> Image.Image` — adds a white strip below the image (height 4% of image height, min 60 px) with the text in black. Output height = input height + strip; output keeps the input mode (`"L"` stays `"L"`).
  - `GET /api/cases/{case_id}/versions/{version_id}/export?style=photo|sketch` → PNG with `Content-Disposition: attachment; filename="<case_number>_v<n>_<style>.png"`; footer lines: `f"Case {case_number} · Version {n}"`, `f"Exported {utc_iso} by {username}"`; audit `export` with `detail={"style": style}`. Invalid `style` → 422.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_export.py
import io
from PIL import Image

def make_version(client, login):
    login(client, "officer1", "officer1pass")
    cid = client.post("/api/cases", json={"title": "t"}).json()["id"]
    v = client.post(f"/api/cases/{cid}/generate", json={"description": "male"}).json()
    return cid, v

def test_photo_export_is_2048_long_side_plus_footer(client, seed_users, login):
    cid, v = make_version(client, login)
    r = client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=photo")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    img = Image.open(io.BytesIO(r.content))
    assert img.format == "PNG" and img.width == 1365 and img.height > 2048  # 1024x1536 source

def test_sketch_export_is_grayscale(client, seed_users, login):
    cid, v = make_version(client, login)
    img = Image.open(io.BytesIO(client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=sketch").content))
    assert img.mode == "L"

def test_export_is_audited_with_style(client, seed_users, login):
    cid, v = make_version(client, login)
    client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=sketch")
    login(client, "admin", "adminpass")
    rows = client.get(f"/api/audit?action=export&case_id={cid}").json()["items"]
    assert rows[0]["detail"] == {"style": "sketch"}

def test_bad_style_is_422(client, seed_users, login):
    cid, v = make_version(client, login)
    assert client.get(f"/api/cases/{cid}/versions/{v['id']}/export?style=oil").status_code == 422
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest backend/tests/test_export.py -v`
Expected: FAIL (404).

- [ ] **Step 3: Implement render functions and route**

- [ ] **Step 4: Run tests**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: photo and pencil-sketch export with footer"
```

---

### Task 8: Frontend scaffold, API client, login, case list

**Files:**
- Create: `frontend/` (Vite React TS template), `frontend/vite.config.ts`, `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/CasesPage.tsx`

**Interfaces:**
- Consumes: backend routes from Tasks 2, 4.
- Produces:
  - `types.ts`: `User {id, username, role: "officer" | "admin"}`, `Case {id, case_number, title, status, created_at, created_by}`, `Attributes` (all spec section 4 keys, `string | null`), `Version {id, version_no, kind, instruction, attributes, created_at, image_url}`, `ChatMsg {id, role, content, version_id, created_at}`, `CaseDetail {case, versions, chat}`, `AuditRow` (all `AuditLog` fields), `ApiError {code, message}`.
  - `api.ts`: `request<T>(path, init?) -> Promise<T>` (always `credentials: "include"`; on non-2xx throws `ApiError` from the body; on 401 redirects to `/login`), and `login, logout, me, listCases, createCase, getCase, generate, refine, revert, auditList, auditVerify` plus `exportUrl(caseId, versionId, style)`.
  - Routes: `/login`, `/cases`, `/cases/:id`, `/audit` (admin only; officers redirected to `/cases`). Auth guard uses `me()` via TanStack Query.
  - `vite.config.ts` proxies `/api` and `/health` to `http://localhost:8000`.

- [ ] **Step 1: Scaffold**

Run: `cd frontend && npm create vite@latest . -- --template react-ts && npm i react-router-dom @tanstack/react-query && npm i -D tailwindcss @tailwindcss/vite`
Expected: `npm run dev` serves on 5173.

- [ ] **Step 2: Implement types, api client, router, login page, case list page (table + "New case" dialog with title input)**

- [ ] **Step 3: Verify against the backend**

Run: backend `uv run python -m backend.seed && AI_MOCK=1 uv run uvicorn backend.app:create_app --factory --port 8000`; frontend `npm run dev`.
Expected: log in as `officer1`, create a case, see it in the list; wrong password shows the error message; `npm run build` passes with no type errors.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: frontend scaffold, login, case list"
```

---

### Task 9: Case workspace UI

**Files:**
- Create: `frontend/src/pages/WorkspacePage.tsx`, `frontend/src/components/DescriptionForm.tsx`, `RefineChat.tsx`, `FaceCanvas.tsx`, `VersionStrip.tsx`, `AttributePanel.tsx`

**Interfaces:**
- Consumes: `getCase`, `generate`, `refine`, `revert`, `exportUrl` from Task 8.
- Produces: the workspace layout from spec section 9.
  - No versions yet: show `DescriptionForm` (textarea, 2000-char counter, Generate button).
  - Versions exist: show `RefineChat` (history from `chat`, input, Send). Keep a "Start over" link that re-shows `DescriptionForm`.
  - `FaceCanvas` shows the selected version (default latest) and a spinner overlay with "Generating… this can take up to 30 seconds" while a mutation runs. All inputs are disabled during a mutation (prevents Review Focus item 1 from the UI side).
  - `VersionStrip`: thumbnails `v1..vn`, click selects, "Revert to this" on a non-latest selection.
  - `AttributePanel`: read-only key/value list of the selected version's attributes, plus "Export photo" and "Export sketch" buttons (plain `<a href={exportUrl(...)}>` links so the browser downloads them).
  - Error display: `ApiError.message` in a red banner; `AI_REFUSED` and `AI_UNAVAILABLE` show a "Try again" button that repeats the last request.

- [ ] **Step 1: Implement components and page**

- [ ] **Step 2: Verify in the browser (mock mode)**

Expected: generate → v1 appears; "make the jaw wider" → v2 and an assistant reply; "hmm" → clarification reply, no new version; revert v1 → v3; both exports download; `npm run build` passes.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: case workspace with chat refinement, versions, export"
```

---

### Task 10: Admin audit page

**Files:**
- Create: `frontend/src/pages/AuditPage.tsx`

**Interfaces:**
- Consumes: `auditList`, `auditVerify`.
- Produces: filter bar (action dropdown with the 13 audit actions, case ID input, since/until datetime inputs), paginated table (time local, username, role, action, case ID, version ID, IP), "Verify integrity" button showing a green "Chain intact (n rows)" or red "Tampering detected at row #id" badge. Link from the header visible only to admins.

- [ ] **Step 1: Implement page**

- [ ] **Step 2: Verify in the browser**

Expected: as admin, filter `action=access_denied` after officer2 tries officer1's case shows that row; verify shows green; as officer1, `/audit` redirects to `/cases`.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: admin audit log viewer with integrity check"
```

---

### Task 11: Seed demo data, README, live LLM smoke test

**Files:**
- Modify: `backend/seed.py` (add demo case for `officer1`: title "Chain snatching, Yelahanka", with pre-generated v1–v2 images saved from a mock or live run)
- Create: `README.md`, `scripts/smoke_live.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `python -m backend.seed` is idempotent.
  - `scripts/smoke_live.py`: with `AI_MOCK=0` and real `LLM_*` settings, calls `extract_attributes`, `generate_image`, `parse_edit`, `edit_image` once each, prints timing per call, saves `smoke_v1.png` and `smoke_v2.png`.
  - README: setup (uv, npm), `.env` fields, run commands, demo accounts, demo script from spec section 13.

- [ ] **Step 1: Run the live smoke test**

Run: `AI_MOCK=0 uv run python scripts/smoke_live.py`
Expected: four calls succeed, timings printed, two PNGs saved, and v2 visibly differs only in the edited region. If an image call is refused, adjust `build_image_prompt` wording and re-run.

- [ ] **Step 2: Full rehearsal**

Run the demo script from spec section 13 end to end against the live LLM service.
Expected: every step works; the audit page shows every action; verify shows green.

- [ ] **Step 3: Run the whole test suite**

Run: `uv run pytest -v && (cd frontend && npm run build)`
Expected: all PASS, build succeeds.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: demo seed, README, live smoke test"
```

---

## Parallel Execution for 3 People

| Person | Tasks | Start condition |
|---|---|---|
| A — Backend | 1 → 2 → 3 → 4 → 7 | Immediately |
| B — AI | 5 → 6 → 11 | Task 5 starts after Task 1 commits (needs `Settings`, `AppError`); Task 6 after Task 4 |
| C — Frontend | 8 → 9 → 10 | Immediately, against `types.ts` from this plan; switch from hand-written fake data to the real backend once Task 4 lands |

Checkpoint mapping: hour 8 = Tasks 1–5 and 8; hour 16 = Tasks 6, 7, 9, 10; hour 20 = Task 11.
