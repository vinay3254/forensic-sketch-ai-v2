# AI Crime Scene Sketch Generator

HackFest 2026 · Track 1 (AI Nexus) · Problem T1-P.

An officer types a witness's description, gets a realistic face, refines it by chat ("make the jaw wider"), and exports a high-resolution photo and pencil sketch. Every access to a case is written to a tamper-evident audit log.

- Design: [`docs/superpowers/specs/2026-10-28-forensic-sketch-ai-design.md`](docs/superpowers/specs/2026-10-28-forensic-sketch-ai-design.md)
- Plan: [`docs/superpowers/plans/2026-10-28-forensic-sketch-ai.md`](docs/superpowers/plans/2026-10-28-forensic-sketch-ai.md)

## Backend setup

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.12 for you.

```bash
cp .env.example .env          # set JWT_SECRET; keep AI_MOCK=1 until the LLM service is ready
uv sync
uv run python -m backend.seed # demo users + demo case
uv run uvicorn backend.app:create_app --factory --reload --port 8000
```

Check: `curl localhost:8000/health` → `{"status":"ok","db":"ok","ai_mode":"mock"}`.
API docs: http://localhost:8000/docs

### Connecting the LLM service

Any OpenAI-compatible endpoint that supports chat completions, `images.generate` and `images.edit`:

```env
AI_MOCK=0
LLM_BASE_URL=http://localhost:<port>/v1
LLM_API_KEY=<key>
LLM_CHAT_MODEL=<chat model id>
LLM_IMAGE_MODEL=<image model id>
```

Then run the smoke test, which calls each AI operation once and prints timings:

```bash
uv run python scripts/smoke_live.py
```

### Tests

```bash
uv run pytest
```

Tests always use the mock AI client and need no network.

## Frontend

The Vite dev server must proxy `/api` and `/health` to `http://localhost:8000`, so the session cookie stays same-origin. See plan Tasks 8–10.

## Demo accounts

| Username | Password | Role |
|---|---|---|
| officer1 | officer1pass | officer (owns the demo case) |
| officer2 | officer2pass | officer |
| admin | adminpass | admin |

## Demo script (3 minutes)

1. Log in as `officer1`. Create case "Chain snatching, Yelahanka".
2. Paste the witness description. The first face appears.
3. Refine twice: "jaw wider", "add a thin moustache". Only those features change.
4. Revert to version 2 to show history, then return to the latest.
5. Export photo and sketch.
6. Log in as `admin`. Open the audit log filtered to this case. Show each step with user and time. Click "Verify integrity".
7. Log in as `officer2`. Try to open the case. Show the 403 and the `access_denied` audit row.

## API summary

| Method | Path | Who |
|---|---|---|
| POST | `/api/auth/login`, `/api/auth/logout` · GET `/api/auth/me` | anyone / signed in |
| GET, POST | `/api/cases` | signed in |
| GET | `/api/cases/{id}` | owner or admin |
| POST | `/api/cases/{id}/generate` `{description}` | owner or admin |
| POST | `/api/cases/{id}/refine` `{message}` | owner or admin |
| GET | `/api/cases/{id}/versions` | owner or admin |
| POST | `/api/cases/{id}/versions/{vid}/revert` | owner or admin |
| GET | `/api/cases/{id}/versions/{vid}/image` | owner or admin |
| GET | `/api/cases/{id}/versions/{vid}/export?style=photo\|sketch` | owner or admin |
| GET | `/api/audit`, `/api/audit/verify` | admin |
