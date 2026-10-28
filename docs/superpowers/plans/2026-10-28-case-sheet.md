# Case Sheet Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disguise variants, person/case details, full-body figure, body-type chart and a one-page printable case sheet.

**Architecture:** Each feature is a small backend module (`backend/variants/`, `backend/cases/details.py`, `backend/body/`, `backend/sheet/`) with its own routes, wired in `app.py`, plus one workspace panel. Images go through `normalize_image`; variants reuse `face/regions.localize`. The sheet is drawn with Pillow from stored data only (no AI).

**Tech Stack:** FastAPI, SQLModel/SQLite, Pillow, ONNX Runtime (existing), React + TanStack Query + Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-28-case-sheet-design.md`

## Global Constraints

- Image prompts never contain `suspect`, `criminal`, `mugshot` (or `police`); incident fields (`approach`, `weapon`, `offence`, `requesting_unit`, `reference`) never reach any prompt.
- Witness words stored verbatim; new interview prompts pass `test_interview_questions.py`.
- New case routes: `Depends(require_case_access)`; child objects of another case → 404 `NOT_FOUND`.
- New audit actions `variant_create`, `case_update`, `body_create` added in `frontend/src/types.ts:AUDIT_ACTIONS`.
- No migrations: new tables and nullable columns only.
- One commit per task, pushed to `origin main`; no Claude co-author trailer.

## Review Focus

- A variant asked for on a version of another case → 404, no AI call.
- Details text over 500 chars or unknown keys → 422, nothing saved.
- Interview prefill must not overwrite details the officer already typed.
- Sheet for a case with only a version (no details, variants, figure, chart files) still renders.
- Weapon/offence set on the case → absent from the body-figure prompt.

---

### Task 1: Localize additions (facial-hair box, region in either image)

**Files:** Modify `backend/face/regions.py`; Test `backend/tests/test_regions.py`

**Interfaces:** Produces `localize(parser, before, after, regions)` unchanged signature; `"facial_hair"` now accepted.

- [ ] Tests: `test_facial_hair_uses_lower_face_box` (pixel between nose and chin edited, forehead not); `test_region_added_in_after_image_is_localized` (before map without glasses, after map with glasses → localized, outside unchanged); existing `test_region_not_found_returns_none` still passes (absent in both).
- [ ] Implement: `REGION_CLASSES["facial_hair"] = ()` with `_lower_face_box(m)`: rows from nose-middle to skin bottom + 4% of size, columns across skin; `_region_mask` returns an empty mask (not None) when a class is absent; `localize` returns None only when the union is empty or a box cannot be built.
- [ ] `uv run pytest -q backend/tests/test_regions.py` → pass; commit `feat(face): localize facial hair and newly added items`.

### Task 2: Disguise variants

**Files:** Create `backend/variants/{__init__,service,routes}.py`, `backend/tests/test_variants.py`, `frontend/src/components/VariantsPanel.tsx`; Modify `backend/models.py` (`Variant`), `backend/ai/prompts.py` (`VARIANTS`, `build_variant_prompt`), `backend/app.py`, `frontend/src/{api,types}.ts`, `frontend/src/pages/WorkspacePage.tsx`.

**Interfaces:**
- `VARIANTS: dict[str, tuple[str, str, list[str] | None]]` = kind → (label, change phrase, localize regions).
- `build_variant_prompt(kind: str) -> str` (edit wording like `build_edit_prompt`, identity and line style kept).
- `create_variant(session, ai, settings, parser, case, user, version, kind) -> Variant`.
- Routes: `POST /api/cases/{id}/versions/{vid}/variants` body `{kind}` → `VariantOut{id, version_id, version_no, kind, label, localized, image_url, created_at}`; `GET /api/cases/{id}/variants` → list newest first; `GET /api/cases/{id}/variants/{xid}/image` (audits `image_view`).

- [ ] Tests: create returns kind/label/localized False (no parser) and a PNG image; unknown kind → 422; version of other case → 404; other officer → 403; audit `variant_create` row with kind; AI failure → 503 and audit outcome; every variant prompt free of crime words; with `FakeParser` → `localized` True.
- [ ] Implement backend; frontend panel (checkbox per kind, "Make selected" runs sequential mutations with "n of m" progress, numbered grid with labels).
- [ ] `uv run pytest -q` and `npm run build` pass; live: one `cap` and one `glasses` variant on a real sketch, check by eye; commit `feat(variants): disguise variants of a sketch`.

### Task 3: Person and case details + interview questions

**Files:** Create `backend/cases/details.py`, `backend/tests/test_case_details.py`, `frontend/src/components/DetailsPanel.tsx`; Modify `backend/models.py` (`Case.details`), `backend/cases/routes.py` (case out + PUT), `backend/interview/{questions,transcript}.py`, `backend/interview/routes.py` (prefill after generate), tests for the bank, frontend types/api/workspace.

**Interfaces:**
- `class CaseDetails(BaseModel)` with optional `str` fields (`max_length=500`, `extra="forbid"`): `height, build, clothing, movement, voice, other_traits, approach, weapon, offence, requesting_unit, reference`.
- `PUT /api/cases/{id}/details` → `CaseDetails`; `GET /api/cases/{id}` includes `case.details`.
- `prefill_from_interview(details: dict, answers: list[dict]) -> dict` — keys `height, build, clothing, movement, voice`; skips `unknown` and blank; never overwrites non-empty.
- New optional EXTRAS keys `height, build, clothing, movement, voice`; `FIELDS_FOR` entries `()`.

- [ ] Tests: put/get round trip; 501 chars → 422; unknown key → 422; other officer → 403; audit `case_update` with changed keys; prefill fills empty, keeps typed, skips unknown; generate-from-interview prefills the case; bank tests updated for new keys.
- [ ] Implement; frontend panel with Person and Incident groups and Save.
- [ ] Tests + build pass; browser/API live check; commit `feat(cases): person and incident details, body questions in the interview`.

### Task 4: Full-body figure

**Files:** Create `backend/body/{__init__,routes}.py`, `backend/tests/test_body.py`; Modify `backend/models.py` (`BodyFigure`), `backend/ai/prompts.py` (`build_body_prompt(a: Attributes, d: CaseDetails) -> str`), `app.py`, frontend details panel.

**Interfaces:** `POST /api/cases/{id}/body` → `{id, image_url, created_at}`; `GET /api/cases/{id}/body` → latest or 404; `GET /api/cases/{id}/body/image`.

- [ ] Tests: create stores and serves a PNG; prompt contains build and clothing and none of weapon/offence/approach text even when set, and no crime words; other officer → 403; audit `body_create`; GET with none → 404.
- [ ] Implement (prompt: hand-drawn full-length standing figure, front view, head to feet, plain background, black and white; sketch stored grayscale).
- [ ] Tests + build; live: one figure; commit `feat(body): full-body figure from build and clothing`.

### Task 5: Body-type reference chart

**Files:** Create `scripts/make_body_types.py`, `backend/assets/body_types/*.png`, `backend/body/types.py`, `backend/tests/test_body_types.py`; Modify `backend/body/routes.py`, details panel.

**Interfaces:** `BODY_TYPES = [("slim","Slim"),("athletic","Athletic"),("overweight","Overweight"),("heavy","Heavy"),("obese","Obese")]`; `body_type_file(key) -> Path | None`; `GET /api/body-types` → present files only; `GET /api/body-types/{key}/image` (login required, 404 unknown/missing).

- [ ] Tests (with a tmp assets dir monkeypatched): list skips missing files; unknown key → 404; needs login.
- [ ] Generate the five PNGs live (grayscale, 600 px tall), commit them; UI picker sets `build`.
- [ ] Commit `feat(body): body-type reference chart`.

### Task 6: Printable case sheet

**Files:** Create `backend/sheet/{__init__,render,routes}.py`, `backend/tests/test_sheet.py`; Modify `app.py`, `AttributePanel.tsx`, `api.ts`.

**Interfaces:** `render_sheet(data: SheetData) -> Image.Image` (A4 landscape 3508×2480, mode L); `GET /api/cases/{id}/sheet?version_id=&format=png|pdf`.

- [ ] Tests: PNG 3508×2480; PDF starts `%PDF`; no version → 409; version of other case → 404; audit `export` `{style: "sheet", format}`; renders with only a version (no details/variants/figure/chart).
- [ ] Implement layout per spec sections; skip empty ones.
- [ ] Tests + build; live: sheet for the live case with variants and figure, check by eye; update HANDOFF/CLAUDE.md/README; commit `feat(sheet): printable one-page case sheet`.
