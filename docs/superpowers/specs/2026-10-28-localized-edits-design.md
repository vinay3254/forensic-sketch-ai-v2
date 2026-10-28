# Localized Edits — Design

Date: 2026-10-28
Status: approved in conversation

## Problem

An image edit redraws the whole sketch. Asking for a wider nose also changes the hair, eyes, mouth and shirt (measured: mean change of 16 grey levels outside the nose). Witnesses lose details they already confirmed.

## Solution

After each refine, a face-parsing model (BiSeNet, 19 CelebAMask-HQ classes) finds the edited regions in the old and new sketch. The new pixels are kept inside those regions; the old pixels are pasted back everywhere else, with a soft edge. Measured in a spike: change outside the region drops to 0 and the edit inside is kept.

## Components

- `backend/face/regions.py`
  - `FaceParser`: loads `storage/models/face_parser.onnx` with ONNX Runtime (CPU) once; `parse(img) -> 512×512 class map`.
  - `REGION_CLASSES`: edit region → BiSeNet classes. `nose`→10; `mouth`→11,12,13; `eyebrows`→2,3; `ears`→7,8,9; `hair`→17,18; `accessories`→6. `eyes` uses a box from the eyebrow bottom to the nose top, across the eyebrows, widened by 15%.
  - `localize(parser, before, after, regions) -> bytes | None`: union of region masks from both images, grown and feathered by 1/40 of the image size, then `before·(1−m) + after·m`. Returns `None` (raw edit used, as before) when a region has no mapping (`face_shape`, `jaw`, `facial_hair`, `marks`, `age_range`, `skin_tone`), when the region is not found, when the face moved (skin+nose+brows mask IoU between before and after < 0.85), or when parsing fails.
- `app.state.face_parser`: built in `create_app` when `EDIT_LOCALIZE` is on, `AI_MOCK` is off and the model file exists; otherwise `None`. Tests inject a fake parser.
- `face/service.refine_face`: after `normalize_image`, before `finish_sketch`, try `localize`. New nullable column `FaceVersion.localized` (bool) records whether it ran.
- `scripts/fetch_face_parser.py`: downloads the BiSeNet weights (`79999_iter.pth`, SHA-256 checked) and the model code at a pinned commit of `zllrunning/face-parsing.PyTorch` into a temp dir, exports ONNX to `storage/models/face_parser.onnx`. Needs PyTorch only for this one-time step; the app never imports PyTorch.

## Errors

Localization never fails a refine: any problem falls back to the raw edit with `localized = false`.

## Testing

- `localize` with a fake parser: outside pixels equal before, inside equal after; unmapped region, missing region, moved face and parser error return `None`; `eyes` box built from brows and nose.
- Refine route stores `localized` true with a fake parser, false without one.
- Live: nose and hair edits on a real sketch, checked by eye.

## Licence

Code MIT. Weights trained on CelebAMask-HQ, which is for non-commercial research use only.
