# Handoff

Status of TRACE (renamed from SketchLab) as of 2026-10-28. Branch `main` (the only branch), remote `origin` = `vinay3254/forensic-sketch-ai-v2` (private).

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

- Left/right: the first-sketch prompt now says left/right mean the person's own side (a mole "above the left lip" had been drawn on the viewer's left). Not yet re-checked live.
- A text description never pins down one face: the same words fit many people, so the first sketch is a starting point to refine with the witness. The first-sketch prompt lists features by name, includes the typed description verbatim (crime words replaced; interview words are not passed, so "don't know" stays blank) and asks for a natural, not idealised face.
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

The image prompt asks for a rough, hand-drawn composite (loose outlines, hatching, hair as shaded shapes), and edits keep that line style. It used to say "not idealised, not a model", which pushed good-looking faces towards plain ones; it now says "neither more nor less attractive than the description says".

**Ethnic appearance** (`Attributes.appearance`, 2026-10-28): the witness's own words ("South Indian, Telugu-looking"), asked as a neutral interview question after age/gender, listed second in the image prompt and carried into the photo prompt. The extractor is told never to infer it from skin colour. Without it the model drew a generic European face for an Indian description (case 9 vs case 10). A photocopy-style post-process ("scanned" finish) was tried and dropped in favour of the plain model output.

## Sign-up and admin dashboard (2026-10-29)

The login page has **Sign in / Create account**. Anyone can create an **investigator** account; an **admin** account needs `ADMIN_SIGNUP_CODE` from `.env` (empty = admin sign-up off), because admins can read every investigator's activity. Sign-up logs the new user in and is audited as `signup`; bad admin codes count towards the login rate limit. Admins land on **Dashboard** (`/dashboard`, sidebar first item): tiles (investigators, logged in now, sessions, cases worked, sketches, failed logins + denials), activity per day stacked by kind of work (Sketch & 3D / Interviews / Case work / Sign-in & account, with a table view), sign-ins per day with failed attempts as red dots plus an alerts list, a session timeline (one bar per login→logout, coloured by how it ended), investigator cards with live status and a 14-day sparkline, cases per person, admins, and the latest 20 actions. Everything is from `GET /api/admin/dashboard?days=7|14|30`, scoped like Oversight (own + unassigned investigators, all admins). Charts are hand-written SVG (`components/charts.tsx`), colours from the dataviz validator (all pass on the paper surface; aqua is below 3:1, so legends, hover values and a table view are always there). Test accounts on the dev database: `test_admin` / `Admin@Trace2026` (admin) and `test_investigator` / `Invest@Trace2026` (investigator, overseen by test_admin); dev admin code `TRACE-ADMIN-2026`.

## Realistic body: 2D to 3D (2026-10-29)

Figure tab → From image → **Realistic body** (default option). `backend/figure/realistic.py` asks the image model for a side view and a back view of the full-body image (`VIEW_PROMPTS`, in parallel), runs MediaPipe Pose (`backend/figure/pose.py`: 33 landmarks, person mask, picture with the paper filled by body tones) on all three, then runs `blender_worker/realistic_body.py` with the blender_worker Python. That script builds an MPFB2 (MakeHuman) human with the case's gender, age and build, rigs it, aims arms and legs like the picture, stretches heights so eyes/shoulders/hips/knees/ankles land where the picture has them, fits every 1 cm slice to the front outline (arms slide to the outline, torso fills between) and the side outline (depth), scales the head as a whole, and textures each face from the view that faces it (torso: front/back only, because the arms hide its sides in the side view). Output: GLB + packed .blend saved as a `BodyModel` (engine "Realistic body …"), so the viewer, downloads and Open in Blender from the parallel session's work apply. ~4 s in Blender; ~1–2 min in total because of the two drawn views. Audited as `body_realistic`. Off (503 `REALISTIC_OFF`) until `uv run python -m scripts.fetch_realistic_body` has put MPFB2 (GPL code, CC0 assets) and the pose model in `storage/realistic/` and `blender_worker` is synced. Limits: dresses/long tunics become body shape, not cloth (legs get pushed together under a kurta); side/back detail is the image model's drawing; feet show MPFB toes under the shoe texture.

## Investigator oversight (2026-10-29)

Admins get **Oversight** (sidebar, Ctrl+K): every investigator they oversee with live status (logged in / offline), last login and logout, logins, sessions, cases, actions, failed logins and access denials; the same for every admin. Each person opens to their **sessions** (login → logout, or "logged in again without logging out" / "expired" / "still logged in"), each with IP, cases touched, action counts and the full timeline, and to **cases handled**, each with the full case log (everyone's actions in that case). Investigators are assigned to an admin with `User.supervisor_id` (the "Overseen by" dropdown); an admin sees their own investigators, unassigned ones (so nobody goes unwatched) and all admins; anyone else's investigator is 403 and audited as `access_denied`. Everything is computed from the existing hash-chained audit log, so nothing new is recorded per action and old rows stay verifiable; oversight views are audited as `oversight_view`, assignments as `supervisor_assign`. The raw Audit log page is unchanged and still shows every row to every admin. Sessions are grouped per user in order, so two browsers logged in as the same person at once are counted as one session ending the other.

## Demo criminal-records database (2026-10-29)

`/records` (sidebar "Records", Ctrl+K "Criminal records"): searchable people with mugshot, alias, area, marks and charge history (FIR no., police station, date, BNS section, offence, status: under investigation / charge-sheeted / convicted / acquitted). **Everything is fictional and labelled so on every page**: faces are synthetic FLUXSynID identities (Zenodo 15172770, CC BY-NC 4.0, so non-commercial; replace with our own generated faces before any commercial use), names/aliases/marks/cases come from `backend/records/seed.py`. Bengaluru areas and police stations are real place names only. Search matches name, alias, record no., marks, area, offence, BNS section and FIR no.; filters by status and station. Every search (`record_search`, with the query and result count) and every record opened (`record_view`) is audited. Faces live in `storage/records/` (gitignored, never committed):

```bash
uv run --with remotezip python -m scripts.fetch_record_faces 120   # ~1 h: Zenodo rate-limits; resumable
uv run python -m scripts.seed_records                              # idempotent
```

The fetch reads single files out of the 11.7 GB zip with HTTP range requests (South Asian adults only, ID-style photo + one live photo each); the live photo is kept for testing suspect matching later.

## Voice input in Indian languages (2026-10-29)

Record/Stop (browser Web Speech API, Chrome/Edge) on every interview answer and on the Sketch page's description box, in English, Hindi, Kannada, Telugu, Tamil, Malayalam, Marathi, Bengali and Gujarati (`backend/translate.py:LANGUAGES`, mirrored in `types.ts:SPEECH_LANGS`). The witness's words are stored verbatim in their language; an English translation (chat model, `TRANSLATE_SYSTEM_PROMPT`: literal, keeps doubt words) is stored beside them, shown to the officer and on the review, and is what the attribute extractor reads. Interview answers carry `lang`/`english` and `Interview.free_recall_lang/_english` only for non-English words, so English transcripts hash exactly as before; the hash covers the translation. Confirming with untranslated words is 422 `TRANSLATION_MISSING`. Translation runs automatically when recording stops, or with the Translate button; changing the words clears it. A typed/spoken description on the Sketch page is translated before generating (`GenerateIn.lang`); the version keeps "original\n(Language) → English". Every translation is audited as `translate`. Live: ~5-20 s per answer. The language spoken is never used as ethnic appearance.

## Proportion sliders (2026-10-29)

Words lose a face's proportions, so after the first sketch the witness reshapes it directly: eye size, eye spacing, nose length and width, mouth width, face length, jaw width (Sketch page, right panel, "Proportions" tab). `face/proportions.py` takes landmarks from the BiSeNet class map (eyes estimated under the brows, mouth estimated when the parser misses pencil lips) and applies smooth local scale/shift warps as one backward-mapped field: no AI call. Preview is a 512 px warp (~70 ms once landmarks are cached per image); Save makes a new version (`kind="adjust"`, attributes and uncertain fields carried over, audited as `proportion_adjust` with the slider values). Previews store nothing and are not audited separately (the image view that loaded the sketch is). Needs `storage/models/face_parser.onnx`, otherwise 503 `PROPORTIONS_OFF`.

## Style library (2026-10-28)

- **Styles** tab on every case (Alt+4; case sheet is now Alt+5): 52 looks in 6 categories (clothing, hair, facial hair, headwear, eyewear, accessories) from `backend/styles/catalog.py`, plus "describe your own". A click is one image edit of the latest sketch, saved as a new version (`instruction` "Style: …", chat + `style_apply` audit), kept inside the matching face-parser region (new `clothing` region = BiSeNet class 16; accessories have per-style regions). Hair and facial-hair styles replace that attribute.
- Thumbnails are faceless pencil mannequins in `backend/assets/styles/`, drawn by `scripts/make_style_thumbs.py` (skips existing files; about 2 min each). Missing ones show a placeholder icon.
- Live check: Hoodie on the woman's sketch, face unchanged, `localized` true.

## Blender figure (2026-10-28)

- **Figure** tab (Alt+5; case sheet is Alt+6): a 3D mannequin the officer shapes by typing ("heavier, about 185 cm, jacket and jeans") or with sliders (height cm, build, muscle, body shape, age) and clothing chips (top, bottom, cap). It redraws as you go and can be turned around; a red ruler shows the height to scale.
- `blender_worker/` (Python 3.13 + `bpy` 5.2.3) keeps Blender loaded: `cd blender_worker && uv run uvicorn server:app --port 8020`, with `FIGURE_URL=http://127.0.0.1:8020` in `.env`. Rebuild + GLB export ~25–75 ms; pencil PNG for the case sheet ~4 s (Cycles CPU + Freestyle; the GPU did not help, see below); `.blend` download for the Blender app ("Open in Blender" needs `sudo pacman -S blender`).
- The body is built only with Blender's own Skin/Subdivision modifiers (a mannequin, generic head); garments are cut from the body surface. MPFB2 (realistic MakeHuman bodies, CC0 assets) was tried but running its downloaded code was blocked by Claude Code's safety check; it can replace the mannequin if the user allows it.
- Backend `figure/`: settings per case on `Case.figure` (defaults read from case details and the sketch: height text in any unit, build words, gender, age, clothing words); `POST /figure/prompt` turns words into setting changes through the chat model (`figure_edit`); `POST /figure/save` renders the pencil figure into the case's full-body figure (so it prints on the case sheet). Audit `figure_update`, `figure_save`.
- GPU check: on this laptop Cycles CUDA/OptiX was no faster than CPU for this tiny scene (time goes to setup and the CPU-only Freestyle pass), and EEVEE runs in software without a display. Real-time comes from the browser drawing the model with WebGL instead.
- Known roughness: jagged garment edges, plain mannequin head.

## Next (agreed, not started)

1. **Suspect matching (CPU)**: InsightFace `buffalo_l` via ONNX Runtime (like the face parser), admin-managed face set stored in SQLite (512-d embeddings, plain cosine search), search from a version's realistic photo, top-5 "possible leads" with scores and a cut-off ("no strong match" below it), every search audited. Needs a short design first. Demo face set only (CUFS under its research licence, or AI-generated faces); `buffalo_l` weights are non-commercial.
2. **Docker Compose** so `docker compose up` runs backend + frontend identically on either laptop.

Decided against: CodeFormer/GFPGAN on exports (adds invented photo detail to sketches/photos), local SDXL/ControlNet on a 6 GB GPU, DECA/3DDFA for 3D, and a GPU worker on the second laptop (also 6 GB VRAM, so no gain).

## Ideas discussed, not built

- Accuracy, from composite research (Frowd et al.): **pick the closest face** (witness chooses among 4 variants per round, EvoFIT-style; whole-face choosing beat feature description ~4x in a meta-analysis), a **likeness score** (InsightFace sketch vs reference photo, for testing only), **draw-first pad** (witness doodles before the interview; Davidson et al. 2025), morphing several composites, caricature animation for bulletins, photo/CCTV still to sketch.

- Hugging Face image models as an alternative backend: FLUX.1-schnell (generate) + Qwen-Image-Edit-2511 (edit / photo). Needs an HF token and a second AI client.
- A UI redesign was tried and reverted at the user's request (`06ccce8` reverted by `a9f43d5`).
