# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SketchLab: an officer turns a witness description into a black-and-white forensic pencil sketch, refines it by chat, can convert a version into a realistic photo, and exports both. Every case access is written to a hash-chained audit log. Design: `docs/superpowers/specs/2026-10-28-forensic-sketch-ai-design.md`. In-progress feature: Smart Witness Interview, `docs/superpowers/specs/2026-10-28-smart-witness-interview-design.md` (its "Delivery" list is the build order). **Read `HANDOFF.md` first**: it has which interview features are done, which is next, live-AI environment notes and known issues. Update it whenever a feature lands.

## Commands

Backend (Python 3.12 via `uv`, run from repo root):

```bash
uv sync
uv run python -m backend.seed                  # idempotent: demo users + demo case
uv run uvicorn backend.app:create_app --factory --reload --port 8000
uv run pytest -q                               # all tests (always mock AI, no network)
uv run pytest backend/tests/test_face.py::test_refine_creates_v2_with_merged_attributes
uv run python -m scripts.smoke_live            # one live call per AI operation (needs AI_MOCK=0 + LLM_* in .env)
uv run python -m scripts.compare_sketch_styles # one live sketch saved with both SKETCH_FINISH options (needs AI_MOCK=0)
```

Frontend (`frontend/`, Vite + React + TS + Tailwind 4):

```bash
npm install
npm run dev      # :5173, proxies /api and /health to :8000
npm run build    # tsc type-check + vite build — the frontend's only automated check
```

If newly added frontend files render unstyled in dev, restart `npm run dev` (the Tailwind dev scan can go stale; `npm run build` is authoritative).

Config comes from `.env` (see `.env.example`). `JWT_SECRET` must be ≥32 chars or the app refuses to start. `AI_MOCK=1` runs fully offline with placeholder images.

## Architecture

- `backend/app.py:create_app()` wires everything onto `app.state` (`settings`, `engine`, `login_limiter`, `ai_client`). Tests build the app with a tmp-path `Settings` (`backend/tests/conftest.py`) and swap `app.state.ai_client` to inject failures.
- **Request path for case routes:** `auth/deps.py` — `session_claims` (JWT cookie, rejects revoked `jti`) → `current_user` → `require_case_access` (owner or admin; a denial writes an `access_denied` audit row before the 403). New case-scoped routes must depend on `require_case_access` and then check that child objects (versions, interviews) belong to that case, returning 404 otherwise.
- **Errors:** raise `AppError(code, message, status)`; `errors.py` maps it, validation errors, HTTP errors and unhandled exceptions to `{"error": {"code", "message"}}`. The frontend's `api.ts:request()` throws `ApiError` from that shape.
- **Audit:** `audit/logger.py:record()` appends a row whose SHA-256 covers the previous hash and all row fields, under a process-wide lock. It commits, which is why `db.get_session` uses `expire_on_commit=False`. Action strings are fixed and mirrored in `frontend/src/types.ts:AUDIT_ACTIONS` — add new ones in both places.
- **AI:** everything goes through `ai/client.py` (`LiveAIClient`, OpenAI SDK against `LLM_BASE_URL`) or `ai/mock.py` (`MockAIClient`). The text model returns JSON validated by `ai/schemas.py` (one guided retry, then `AI_PARSE_FAILED`). Image generation uses `images.generate`; edits use `images.edit` or, with `LLM_IMAGE_EDIT_API=responses`, the Responses API `image_generation` tool (needed for Codex models). Prompt text lives only in `ai/prompts.py`; image prompts must never contain crime words (test-enforced).
- **Face pipeline** (`face/service.py`): generate / refine / revert / make_photo. Every AI image goes through `normalize_image` (PNG, centre-cropped to `LLM_IMAGE_SIZE` aspect; sketches stored grayscale, photos RGB). Versions are append-only with a unique `(case_id, version_no)`; a clash becomes 409 and the new image file is deleted. Images are served only by version id, never by path.
- **Export** (`export/`): upscale to 2048 px, footer with case/version/time/user. `style=photo` requires a realistic photo made first (409 otherwise).
- **Witness interview** (`interview/`): the prompt bank in `questions.py` is fixed; `test_interview_questions.py` fails on yes/no openers, " or ", or suggestive value words. Answers are stored verbatim and the stored prompt is always copied from the bank, never from the client. Confirmed interviews are read-only (409) and carry a SHA-256 of `transcript.canonical_transcript`. A sketch is generated from a confirmed interview via `transcript.render_description` (verbatim words labelled remembered/uncertain); fields for "Don't know" answers are forced to null after extraction, and uncertain fields are stored on `FaceVersion.uncertain` and carried through refine (minus edited regions) and revert.
- **Schema changes:** there are no migrations. On startup `db.init_db` runs `create_all` (new tables) and `add_missing_columns` (adds new *nullable* columns to existing SQLite tables). A new non-nullable column, or a changed column, still means deleting `app.db` and reseeding.

## Working agreements

- Build multi-feature work one feature at a time: test (TDD, failing test first), verify live/in the browser, commit, push, then stop and wait for the user's go-ahead before the next feature.
- Do not add `Co-Authored-By: Claude` trailers or "Generated with Claude Code" lines to commits or PRs.
- Work happens on branch `backend`; remote `origin` is `vinay3254/forensic-sketch-ai-v2`.
