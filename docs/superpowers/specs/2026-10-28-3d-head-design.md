# 3D Head and Other Angles — Design

Date: 2026-10-28
Status: draft for review

## Goal

A witness who saw the person from the side, or at an angle, should be able to check the face from that angle. SketchLab turns a sketch version into an approximate 3D head, lets the officer and witness rotate it, and saves chosen angles as pencil sketches that go on the case sheet. Later (separate spec) the same head gets Blender-style sculpting brushes in the browser.

## Spike findings (2026-10-28, throwaway)

| Input → method | Result | Cost |
|---|---|---|
| Sketch → TripoSR | rotatable head, blurry, flat profile, checker artefacts | 61 s, 3.9 GB VRAM |
| Realistic photo → TripoSR | clean head, believable and consistent profile | 47 s, 3.9 GB VRAM |
| AI redraw of the sketch at an angle | best looking, but each angle is an independent guess | ~45 s per angle |
| **Photo → TripoSR → AI redraws the 3D view as pencil** | keeps the 3D shape and pose, in our sketch style | ~50 s + ~45 s per angle |

Chosen: the last row. DECA/FLAME was not tried (registration-gated, non-commercial). Blender's own code is not used: its sculpt module is tied to the whole C++ application and GPL-licensed.

## Rules

- Every 3D-derived image is labelled **"approximate"** in the UI and on the sheet: a front view carries no depth, so the profile is the model's guess, not the witness's memory.
- The 3D model runs only on this machine's GPU. No case image goes to a new external service.
- Image prompts stay free of crime words (existing test pattern).
- Case-scoped routes use `require_case_access`; another case's head or view is 404. New audit actions: `head_create`, `angle_view_create` (mirrored in `AUDIT_ACTIONS`).
- No migrations: new tables only.

## Architecture

```
browser ──► backend (FastAPI) ──HTTP──► head3d worker (FastAPI + PyTorch + TripoSR, GPU)
   ▲  three.js viewer                       POST /head  (PNG in → GLB out)
   └── GLB + angle views
```

### Head worker (`head3d/`)

- Own small project with its own `pyproject.toml` (PyTorch, TripoSR deps, `scikit-image` for marching cubes instead of the CUDA-compiled `torchmcubes`, `rembg`). The app's environment never imports PyTorch.
- `head3d/setup.py` fetches TripoSR (MIT) at a pinned commit into `head3d/vendor/` (git-ignored); weights come from Hugging Face `stabilityai/TripoSR` on first start.
- `head3d/server.py`: loads the model once (~30 s), serves `POST /head` (body: PNG; returns `model/gltf-binary` with vertex colours, 192³ marching cubes) and `GET /health`. One request at a time (GPU lock). Run: `uv run --project head3d uvicorn server:app --port 8010`.

### Backend

- Setting `HEAD3D_URL` (empty = feature off; the UI hides the 3D panel and the routes return 503 `HEAD3D_OFF`).
- `backend/head3d/client.py`: `Head3DClient.make_head(photo_png: bytes) -> bytes` (GLB), 180 s timeout; failures → `AppError("AI_UNAVAILABLE", …, 503)`. `app.state.head3d_client`, swapped by a fake in tests.
- Table `Head3D`: `id, case_id, version_id, mesh_path, created_by, created_at`.
- Table `AngleView`: `id, case_id, head_id, yaw, label, render_path, image_path, created_by, created_at`. `yaw` in degrees, −90 (left profile) … +90 (right profile); `label` from yaw: `Front` (|yaw| < 15), `Left/Right three-quarter` (< 65), `Left/Right profile`.
- Routes (prefix `/api/cases/{id}`):
  - `POST /versions/{vid}/head` → makes the realistic photo first if the version has none (existing `make_photo`), sends it to the worker, stores the GLB. Audited `head_create` (outcome on failure too).
  - `GET /heads` → newest first `{id, version_id, version_no, mesh_url, created_at}`; `GET /heads/{hid}/mesh` → GLB.
  - `POST /heads/{hid}/views` `{yaw, render: base64 PNG ≤ 4 MB}` → the browser's render of the head at that angle is redrawn as a pencil sketch by the image model (`ai/prompts.py:build_angle_prompt`), stored with its render. Audited `angle_view_create`.
  - `GET /views` → newest first; `GET /views/{xid}/image`.

### Frontend

- `HeadPanel` on the workspace (only when `HEAD3D_URL` is set; `/health` reports `head3d: on|off`): "Make 3D head" for the selected version (progress text: photo, then 3D, ~1.5 min), a three.js viewer (`three` + `GLTFLoader` + `OrbitControls`, yaw limited to ±90°, pitch ±20°), preset buttons (left profile, left ¾, front, right ¾, right profile), and "Save this angle as a sketch", which captures the canvas (`preserveDrawingBuffer`) and posts it with the current yaw.
- Saved angle views show in a strip with their label and "approximate".

### Case sheet

- Angle views print in the bottom strip before the disguise variants, labelled e.g. "Left profile (3D, approximate)".

## Delivery (one feature at a time: failing test first, live check, commit, push)

1. **Head worker + head API** — worker project and setup script; backend client, `Head3D`, `POST /versions/{vid}/head`, `GET /heads`, mesh route; fake client in tests. Live: head for the case-6 sketch.
2. **3D viewer** — `HeadPanel` with rotate and presets; checked in the browser.
3. **Angle views** — `AngleView`, capture + redraw, strip in the panel. Live: left profile and right ¾.
4. **Case sheet** — angle views on the sheet.

## Testing

Fake head client (returns a tiny valid GLB); route tests for 404 across cases, 403 + audit for another officer, photo made first when missing, 503 when the feature is off or the worker fails, render too large or not a PNG → 422, yaw outside ±90 → 422, label boundaries, crime-word check on `build_angle_prompt`. Worker: one smoke test script (`head3d/smoke.py`) run by hand, not in CI (needs the GPU).

## Out of scope (later spec)

Sculpting brushes (SculptGL-based, MIT) on the head mesh; exporting the head to Blender and importing it back; matching against photo databases.
