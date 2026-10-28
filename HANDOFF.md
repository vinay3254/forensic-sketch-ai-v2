# Handoff

Status of SketchLab as of 2026-10-28. Branch `main` (the only branch), remote `origin` = `vinay3254/forensic-sketch-ai-v2` (private).

## Working

- Login, roles (officer sees own cases, admin sees all), login lockout, JWT revoked on logout.
- Cases: create, list, open.
- Sketches: description → black-and-white pencil sketch; refine by chat (vague messages get a clarifying question, no new version); revert; version history.
- Realistic photo from any sketch version (made once per version, then reused).
- Export sketch and photo as PNG (2048 px, footer with case, version, time, user).
- Audit log with SHA-256 hash chain, admin filters, "Verify integrity".
- Tests: `uv run pytest -q` → 279 passed. `npm run build` passes.
- Live AI check (Codex models) passed: generate, refine, realistic photo, both exports.

## Light UI, navigation and sketch theme (2026-10-28)

- Layout follows a Seto-style reference: light frame, sidebar with `lucide-react` icons, rounded cards, composer, history rail.
- Colours follow a sketch theme (`frontend/src/index.css` `@theme`): graphite pencil on warm drawing paper with a grain, paper-white cards with graphite hairlines, one red-pencil accent (`accent`). The older pages' `slate`/`blue` classes are remapped there to graphite/red pencil.
- Home (`/cases`): welcome, three action cards, a composer (typed or dictated description creates a case and pre-fills the workspace form; generating stays a click), and a case-history rail with search, latest-sketch thumbnails (`latest_image_url`, `version_count` on `GET /api/cases`) and quick links to each case page.
- Moving around: a case bar on every case page (Sketch · Details · Interview · Case sheet, Alt+1…4), Ctrl/⌘K jump-to palette (cases, their pages, New case, Home, Audit), recent cases in the sidebar, and cases reopen on the page last used (browser `localStorage`, per device). `/cases/:id/interview` opens the draft or latest interview, or offers to start one.
- Still in the older layout (new colours only): interview, audit and login pages.
- Refine suggestion chips were removed at the user's request.
- Dev servers for this checkout: backend `--port 8001` with `FRONTEND_ORIGIN=http://localhost:5174`, frontend `BACKEND_URL=http://localhost:8001 npx vite --port 5174` (ports 8000/5173 were held by another session's stack).
- Two untracked files from a stopped parallel session, unused: `frontend/src/components/Icon.tsx`, `docs/superpowers/plans/2026-10-28-dashboard-refresh.md`. Delete them if nobody needs them.

## Smart Witness Interview (in progress)

Spec: `docs/superpowers/specs/2026-10-28-smart-witness-interview-design.md`. Built one feature at a time; the user approves each before the next starts.

| # | Feature | State |
|---|---|---|
| 1 | Fixed neutral question bank + wording tests | done (`1c4a8fc`) |
| 2 | Interview storage API (start / read / autosave, access control, audit) | done (`4e8afb7`) |
| 3 | Interview screens: free account + feature steps, statuses, autosave | done (`aa0f750`) |
| 4 | Speech-to-text (browser Web Speech API, `en-IN` default; en-US, Hindi, Kannada) | done |
| 5 | Optional extras step (facial hair, hairstyle, glasses, distinguishing features) | done |
| 6 | Review & confirm (lock transcript, SHA-256 in audit) | done |
| 7 | Generate sketch from confirmed interview (unknown → blank, uncertain flagged) | done |
| 8 | Option B: AI marks features already covered, exact quotes only, off by default | done |

All eight interview features are built. AI assist is a checkbox on the free-account step (off by default); "Check the free account" calls `POST .../assist`, and each feature step then shows the witness's exact words for it. Live check: 5 features found, every quote verbatim, about 23 s.

Sketches can be generated from a confirmed interview ("Confirm & generate sketch") or, as before, from the single description box on the case page.

## Environment notes

- `.env` (not in git) is set to live mode: chat `auto/best-fast`, image `codex/gpt-5.6-luna-image`, edits `codex/gpt-5.6-luna` via `LLM_IMAGE_EDIT_API=responses`. The Codex login behind it expires periodically; refresh it before a demo.
- Codex `gpt-image-2*` models fail (no paid credits on the account). `antigravity/gemini-3.1-flash-image` is a working fallback (faster, ~20 s).
- Each live image call takes about 35–60 s.
- No DB migrations: new nullable columns are added automatically at startup; any other schema change needs `app.db` deleted and `uv run python -m backend.seed`.
- If a new frontend file shows up unstyled in dev, restart `npm run dev`.

## Known issues

- Left/right from the witness's point of view is not pinned down: "small mole above the left lip" was drawn on the viewer's left (the person's right). Witnesses usually mean the person's own left; the image prompt should say so.
- Refined attribute text repeats itself (e.g. `"light stubble, thin moustache with light stubble"`): `apply_edits` appends the change to the old value instead of replacing it.
- Edits to unmapped regions (jaw, face shape, facial hair, marks) still redraw the whole sketch, so they can change more than asked.
- Each thumbnail load writes an `image_view` audit row, so the log fills quickly.
- The `revoked_token` table is never pruned.
- No frontend unit tests; the frontend is checked with `npm run build` and in the browser.
- A deleted tail of audit rows still verifies as intact; `/api/audit/verify` returns `head_hash` so an auditor can compare it with a noted value.

## Case sheet features

Built from a real composite sheet the user showed (spec `docs/superpowers/specs/2026-10-28-case-sheet-design.md`, plan `docs/superpowers/plans/2026-10-28-case-sheet.md`):

- **Disguise variants** (`backend/variants/`): ten fixed kinds from the selected version, one image edit each (~35–60 s), localized when the face stays put (glasses and beard did; the cap edit moved the face and kept the full redraw).
- **Person & case details** (`Case.details`, `backend/cases/details.py`): height, build, clothing, movement, voice, other traits; approach, weapon, offence, requesting unit, reference. Five optional interview questions fill empty person fields verbatim after "Confirm & generate".
- **Full-body figure** (`backend/body/routes.py`): drawn from build, clothing and the sketch's age, gender and hair; height is printed beside it, not drawn to scale.
- **Body-type chart** (`backend/body/types.py`, PNGs in `backend/assets/body_types/`, redraw with `scripts/make_body_types.py`): clicking a figure fills `build`.
- **Case sheet** (`backend/sheet/`): A4 landscape 300 dpi PNG or PDF with header, sketch, face/person/incident sections, figure with height bar, build chart, numbered variants and footer.

Incident fields never reach an image prompt (tested).

## 3D head (paused, off by default)

Spec `docs/superpowers/specs/2026-10-28-3d-head-design.md`, plan `docs/superpowers/plans/2026-10-28-3d-head.md`. Tasks 1–2 of 4 built; the user paused it: too slow for a live demo.

- Worker `head3d/` (TripoSR on the GPU): `uv run --project head3d python head3d/fetch_triposr.py` once, then `cd head3d && uv run uvicorn server:app --port 8010`, and set `HEAD3D_URL=http://127.0.0.1:8010`. Empty `HEAD3D_URL` hides the panel and the routes return 503.
- Backend: `POST /api/cases/{id}/versions/{vid}/head` (makes the realistic photo first), `GET /heads`, `GET /heads/{hid}/mesh`.
- Viewer: `HeadPanel` / `HeadViewer` (three.js, lazy-loaded), presets left/right profile, ¾, front.

Open problems before it can be used:
- **Possible mirrored mesh**: the "Left profile" preset showed the person's right side. The `torchmcubes` stand-in in `head3d/server.py` reverses the axis order; check with an asymmetric mark before trusting any side view.
- Dark cracks on the face, probably flipped triangle winding from the same stand-in (or render with `side: THREE.DoubleSide`).
- Slow: about 30 s for the photo plus 25–60 s for the head.
- Tasks 3 (save angles as pencil sketches) and 4 (case sheet) not started.
- `head3d/uv.lock` pins old `transformers==4.35.0` (TripoSR's requirement); GitHub Dependabot flags vulnerabilities in the repo.

## Localized edits

Done. Refines keep the change inside the edited regions and paste the previous sketch back elsewhere (`face/regions.py`, spec `docs/superpowers/specs/2026-10-28-localized-edits-design.md`). Needs `storage/models/face_parser.onnx` from `scripts/fetch_face_parser.py`; without it refines behave as before. Live check: a nose edit changed only the nose. Jaw, face shape, facial hair and marks have no parser class and still redraw the whole sketch. This fixes the known issue "edits change more than asked" for the mapped regions.

## Sketch style

The image prompt asks for a rough, hand-drawn composite of an ordinary face (loose outlines, hatching, hair as shaded shapes, not idealised), and edits keep that line style. A photocopy-style post-process ("scanned" finish) was tried and dropped in favour of the plain model output.

## Next (agreed, not started)

1. **Suspect matching (CPU)**: InsightFace `buffalo_l` via ONNX Runtime (like the face parser), admin-managed face set stored in SQLite (512-d embeddings, plain cosine search), search from a version's realistic photo, top-5 "possible leads" with scores and a cut-off ("no strong match" below it), every search audited. Needs a short design first. Demo face set only (CUFS under its research licence, or AI-generated faces); `buffalo_l` weights are non-commercial.
2. **Docker Compose** so `docker compose up` runs backend + frontend identically on either laptop.

Decided against: CodeFormer/GFPGAN on exports (adds invented photo detail to sketches/photos), local SDXL/ControlNet on a 6 GB GPU, DECA/3DDFA for 3D, and a GPU worker on the second laptop (also 6 GB VRAM, so no gain).

## Ideas discussed, not built

- Hugging Face image models as an alternative backend: FLUX.1-schnell (generate) + Qwen-Image-Edit-2511 (edit / photo). Needs an HF token and a second AI client.
- A UI redesign was tried and reverted at the user's request (`06ccce8` reverted by `a9f43d5`).
