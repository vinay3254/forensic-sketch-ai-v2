# Case Sheet Features — Design

Date: 2026-10-28
Status: approved in conversation ("build all five in this order")

## Goal

A finished case should produce what an investigator's composite sheet carries, not only a face: the person's height, build, clothing and behaviour, how the incident happened, disguise variants of the face, a full-body figure, a body-type reference, and one printable page that puts it all together. Reference: a state forensic institute's composite sheet shown by the user (layout only; no agency branding is copied).

## Rules that still apply

- Image prompts never contain crime words (test-enforced). Offence, weapon and approach are text on the case and the sheet only; they never reach any prompt.
- Witness words are stored verbatim. Interview prompts stay neutral (existing bank tests apply to new questions).
- Every new case route depends on `require_case_access` and 404s for child objects of another case. Every new action is audited and mirrored in `frontend/src/types.ts:AUDIT_ACTIONS`.
- No migrations: new tables via `create_all`, new nullable columns via `add_missing_columns`.

## Delivery (one feature at a time: test first, live check, commit, push)

### 1. Disguise variants

The officer picks variants of the selected sketch version; each is one image edit of that version.

- Kinds (fixed list, fixed prompt text in `ai/prompts.py:VARIANTS`): `cap`, `brimmed_hat`, `hood`, `glasses`, `sunglasses`, `moustache`, `full_beard`, `goatee`, `stubble`, `shaved_head`.
- Localization regions per kind: hats and `shaved_head` → `hair`; glasses → `accessories` + `eyes`; facial hair → `facial_hair`; `hood` → none (full redraw).
- `regions.py` changes: `facial_hair` maps to a lower-face box (nose middle to just below the chin, across the skin); a region counts as found when it is present in **either** image, so adding something new (glasses, a cap) is localized too.
- Table `Variant`: `id, case_id, version_id, kind, image_path, prompt, localized, created_by, created_at`.
- API: `POST /api/cases/{id}/versions/{vid}/variants {kind}` → one variant (the UI calls it once per selected kind, in sequence, showing progress); `GET /api/cases/{id}/variants`; `GET /api/cases/{id}/variants/{xid}/image`. Audit `variant_create` (outcome on failure too).
- UI: "Disguise variants" panel under the version strip: checkboxes, "Make selected", a numbered grid with labels.

### 2. Person and case details

- `Case.details` (JSON, nullable). Person: `height`, `build`, `clothing`, `movement`, `voice`, `other_traits`. Incident: `approach`, `weapon`, `offence`, `requesting_unit`, `reference`. All optional strings, 500 chars max.
- API: `PUT /api/cases/{id}/details` (replaces the whole object), returned in `GET /api/cases/{id}`. Audit `case_update` (detail: changed keys only).
- Interview: new optional questions `height`, `build`, `clothing`, `movement`, `voice` (neutral wording, bank tests apply). They speak to no face attribute. When a sketch is generated from a confirmed interview, their verbatim answers fill the matching empty detail fields (answers marked "Don't know" are skipped); fields the officer already filled are never overwritten.
- UI: "Person & case details" panel on the workspace with the two groups; saves on "Save".

### 3. Full-body figure

- `POST /api/cases/{id}/body` draws a full-length standing pencil figure from the latest version's gender and age and the case's `build` and `clothing`; `height` is not drawn (the model cannot draw to scale) but labelled on the sheet. Prompt in `ai/prompts.py:build_body_prompt`; includes no incident field.
- Table `BodyFigure`: `id, case_id, image_path, prompt, created_by, created_at`; the newest is used. `GET /api/cases/{id}/body/image`. Audit `body_create`.
- UI: "Full-body figure" card in the details panel with a "Draw figure" button.

### 4. Body-type reference chart

- Five fixed reference figures: `slim`, `athletic`, `overweight`, `heavy`, `obese`, generated once by `scripts/make_body_types.py` (live) and committed as small grayscale PNGs in `backend/assets/body_types/`.
- `GET /api/body-types` → `[{key, label, image_url}]` for the files present; `GET /api/body-types/{key}/image`.
- UI: clicking a figure in the details panel sets `build` to its label (still editable as text).

### 5. Printable case sheet

- `GET /api/cases/{id}/sheet?version_id=&format=png|pdf` (default: latest version, png). 409 when the case has no version.
- A4 landscape at 300 dpi, drawn with Pillow: header (case number, title, date, requesting unit, reference, offence); main sketch; face description (non-null attributes, uncertain ones marked); person details; incident details (approach, weapon); full-body figure with the witness's height text beside a bar; numbered disguise variants; body-type chart with the matching build highlighted; footer (version, exported time and user, "Composite sketch: an investigative aid, not a photograph"). Sections without data are left out.
- Audit `export` with `detail: {style: "sheet", format}`. UI: "Export case sheet" button next to "Export sketch".

## Testing

Per feature, mock AI only: route happy path, 404 for another case's child objects, 403 + audit for another officer, audit rows, 409 cases, and the crime-word check on every new prompt (including when weapon/offence are set). `localize` tests for the lower-face box and "present in either image". Sheet: PNG and PDF are valid, size is A4 at 300 dpi, empty sections are skipped. Live check per feature; `npm run build` for the frontend.

## Out of scope

Agency logos and "wanted" banners, numeric height scales, matching against photo databases.
