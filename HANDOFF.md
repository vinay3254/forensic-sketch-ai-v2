# Handoff

Status of SketchLab as of 2026-10-28. Branch `backend`, remote `origin` = `vinay3254/forensic-sketch-ai-v2` (private). Nothing is merged to `main` yet.

## Working

- Login, roles (officer sees own cases, admin sees all), login lockout, JWT revoked on logout.
- Cases: create, list, open.
- Sketches: description → black-and-white pencil sketch; refine by chat (vague messages get a clarifying question, no new version); revert; version history.
- Realistic photo from any sketch version (made once per version, then reused).
- Export sketch and photo as PNG (2048 px, footer with case, version, time, user).
- Audit log with SHA-256 hash chain, admin filters, "Verify integrity".
- Tests: `uv run pytest -q` → 147 passed. `npm run build` passes.
- Live AI check (Codex models) passed: generate, refine, realistic photo, both exports.

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
| 8 | Option B: AI marks features already covered, exact quotes only, off by default | **next, waiting for go-ahead** |

Sketches can be generated from a confirmed interview ("Confirm & generate sketch") or, as before, from the single description box on the case page.

## Environment notes

- `.env` (not in git) is set to live mode: chat `auto/best-fast`, image `codex/gpt-5.6-luna-image`, edits `codex/gpt-5.6-luna` via `LLM_IMAGE_EDIT_API=responses`. The Codex login behind it expires periodically; refresh it before a demo.
- Codex `gpt-image-2*` models fail (no paid credits on the account). `antigravity/gemini-3.1-flash-image` is a working fallback (faster, ~20 s).
- Each live image call takes about 35–60 s.
- No DB migrations: new nullable columns are added automatically at startup; any other schema change needs `app.db` deleted and `uv run python -m backend.seed`.
- If a new frontend file shows up unstyled in dev, restart `npm run dev`.

## Known issues

- Refined attribute text repeats itself (e.g. `"light stubble, thin moustache with light stubble"`): `apply_edits` appends the change to the old value instead of replacing it.
- Edits can change more than asked (e.g. a moustache edit also thinned the stubble).
- Each thumbnail load writes an `image_view` audit row, so the log fills quickly.
- The `revoked_token` table is never pruned.
- No frontend unit tests; the frontend is checked with `npm run build` and in the browser.
- A deleted tail of audit rows still verifies as intact; `/api/audit/verify` returns `head_hash` so an auditor can compare it with a noted value.

## Sketch style trial (pick one, remove the other)

Sketches looked too polished. The image prompt now asks for a rough, hand-drawn composite of an ordinary face (both options use it). On top of that, `SKETCH_FINISH` in `.env` picks the finish applied to every generated and refined sketch:

- `clean` (default, option A): the image as the model drew it.
- `scanned` (option B): `face/service.py:scanned_finish`, a photocopy curve (faint shading drops out, strokes darken), grey paper tone and grain.

`AI_MOCK=0 uv run python -m scripts.compare_sketch_styles ["description"] [out_dir]` makes one live sketch and saves both finishes plus a side-by-side. Once the user decides, delete the losing option, its setting and the script.

## Ideas discussed, not built

- Hugging Face image models as an alternative backend: FLUX.1-schnell (generate) + Qwen-Image-Edit-2511 (edit / photo). Needs an HF token and a second AI client.
- A UI redesign was tried and reverted at the user's request (`06ccce8` reverted by `a9f43d5`).
