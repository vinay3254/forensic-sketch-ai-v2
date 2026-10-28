# AI Crime Scene Sketch Generator

HackFest 2026 · Track 1 (AI Nexus) · Problem T1-P.

An officer interviews a witness (or types a description), gets a black-and-white forensic pencil sketch, refines it by chat ("make the jaw wider"), can turn any version into a realistic photo, and exports both at high resolution. Every access to a case is written to a tamper-evident audit log.

- Design: [`docs/superpowers/specs/2026-10-28-forensic-sketch-ai-design.md`](docs/superpowers/specs/2026-10-28-forensic-sketch-ai-design.md)
- Plan: [`docs/superpowers/plans/2026-10-28-forensic-sketch-ai.md`](docs/superpowers/plans/2026-10-28-forensic-sketch-ai.md)
- Smart Witness Interview design: [`docs/superpowers/specs/2026-10-28-smart-witness-interview-design.md`](docs/superpowers/specs/2026-10-28-smart-witness-interview-design.md)
- Current status and next steps: [`HANDOFF.md`](HANDOFF.md)

## Backend setup

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.12 for you.

```bash
cp .env.example .env          # set JWT_SECRET (32+ chars); keep AI_MOCK=1 until the LLM service is ready
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
# Image models that cannot take an input image (e.g. Codex): edit via the Responses API instead
LLM_IMAGE_EDIT_API=responses   # default: images
LLM_IMAGE_EDIT_MODEL=<text model that calls the image_generation tool>
```

Setup used for the demo: chat `auto/best-fast`, image `codex/gpt-5.6-luna-image`, edits `codex/gpt-5.6-luna` with `LLM_IMAGE_EDIT_API=responses`.

Then run the smoke test, which calls each AI operation once and prints timings:

```bash
uv run python -m scripts.smoke_live
```

### Localized edits (optional)

AI image edits redraw the whole sketch. With the face-parsing model installed, each refine keeps the change only inside the regions the witness asked about (nose, mouth, eyes, eyebrows, ears, hair, glasses) and pastes the previous sketch back everywhere else. Edits to the jaw, face shape, facial hair or marks keep the full redraw. One-time setup (downloads PyTorch only for the export, about 1–2 minutes):

```bash
uv run --with torch --with torchvision --with onnx python -m scripts.fetch_face_parser
```

This writes `storage/models/face_parser.onnx`; restart the backend. Set `EDIT_LOCALIZE=0` to turn it off. Model code: [zllrunning/face-parsing.PyTorch](https://github.com/zllrunning/face-parsing.PyTorch) (MIT). The weights were trained on CelebAMask-HQ, which is licensed for non-commercial research use only.

### Tests

```bash
uv run pytest
```

Tests always use the mock AI client and need no network.

## Frontend

Requires Node 20+. Start the backend first, then:

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

The Vite dev server proxies `/api` and `/health` to `http://localhost:8000`, so the session cookie stays same-origin. Open http://localhost:5173 and log in with a demo account.

`npm run build` type-checks and builds to `frontend/dist`.

## Demo accounts

| Username | Password | Role |
|---|---|---|
| officer1 | officer1pass | officer (owns the demo case) |
| officer2 | officer2pass | officer |
| admin | adminpass | admin |
| vinay3254 | 7767 | officer |

## Demo script (3 minutes)

1. Log in as `officer1`. Create case "Chain snatching, Yelahanka".
2. Paste the witness description. The first pencil sketch appears.
3. Refine twice: "jaw wider", "add a thin moustache". Only those features change.
4. Revert to version 1 to show history.
5. Click "Make realistic photo", flip the Sketch / Realistic photo toggle, then export sketch and photo.
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
| POST, GET | `/api/cases/{id}/versions/{vid}/photo` (make / view realistic photo) | owner or admin |
| GET | `/api/cases/{id}/versions/{vid}/export?style=photo\|sketch` | owner or admin |
| GET | `/api/interview/questions` | signed in |
| GET, POST | `/api/cases/{id}/interviews` | owner or admin |
| GET, PUT | `/api/cases/{id}/interviews/{iid}` (PUT = autosave draft) | owner or admin |
| POST | `/api/cases/{id}/interviews/{iid}/assist`, `/confirm`, `/generate` | owner or admin |
| PUT | `/api/cases/{id}/details` (person and incident details) | owner or admin |
| POST, GET | `/api/cases/{id}/versions/{vid}/variants` `{kind}` · `/api/cases/{id}/variants` (disguise variants) | owner or admin |
| POST, GET | `/api/cases/{id}/body` (full-body figure) | owner or admin |
| GET | `/api/body-types` (build reference chart) | signed in |
| GET | `/api/cases/{id}/sheet?version_id=&format=png\|pdf` (one-page case sheet) | owner or admin |
| GET | `/api/audit`, `/api/audit/verify` | admin |
