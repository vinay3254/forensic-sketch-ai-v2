"""Body landmarks and outline of a full-body picture (MediaPipe Pose Landmarker, CPU).

Also returns a "filled" copy of the picture: the paper around the person replaced by the nearest
body tones, so a texture projected from it never shows white at the body's edges."""

import io
from pathlib import Path

import numpy as np
from PIL import Image

NAMES = [
    "nose", "l_eye_in", "l_eye", "l_eye_out", "r_eye_in", "r_eye", "r_eye_out", "l_ear", "r_ear", "mouth_l",
    "mouth_r", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist", "l_pinky", "r_pinky",
    "l_index", "r_index", "l_thumb", "r_thumb", "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle",
    "l_heel", "r_heel", "l_foot", "r_foot",
]


class NoPerson(ValueError):
    pass


def _png(a: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "PNG")
    return buf.getvalue()


def fill_background(gray: np.ndarray, mask: np.ndarray) -> np.ndarray:
    # the mask runs a few pixels past the body: shrink it, and never trust paper-white pixels
    known = mask.copy()
    for _ in range(6):
        known &= np.roll(known, 1, 0) & np.roll(known, -1, 0) & np.roll(known, 1, 1) & np.roll(known, -1, 1)
    known &= gray < 215
    if not known.any():
        return gray.astype(np.uint8)
    val = np.where(known, gray, 0).astype(np.float32)
    for _ in range(400):
        if known.all():
            break
        acc = np.zeros_like(val)
        cnt = np.zeros_like(val)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            acc += np.roll(np.roll(val, dy, 0), dx, 1)
            cnt += np.roll(np.roll(known, dy, 0), dx, 1)
        grow = ~known & (cnt > 0)
        val[grow] = acc[grow] / cnt[grow]
        known |= grow
    val[~known] = gray[mask].mean() if mask.any() else 128
    return val.clip(0, 255).astype(np.uint8)


def detect(image: bytes, model_path: Path) -> tuple[dict, bytes, bytes]:
    """(landmarks and outline box in pixels, mask PNG, filled picture PNG)."""
    import mediapipe as mp

    img = Image.open(io.BytesIO(image)).convert("RGB")
    w, h = img.size
    opts = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)), output_segmentation_masks=True,
        num_poses=1,
    )
    with mp.tasks.vision.PoseLandmarker.create_from_options(opts) as det:
        res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(img)))
    if not res.pose_landmarks:
        raise NoPerson("No person found in the picture.")
    pts = {n: [round(p.x * w, 1), round(p.y * h, 1), round(p.visibility, 2)] for n, p in zip(NAMES, res.pose_landmarks[0])}
    mask = res.segmentation_masks[0].numpy_view()[..., 0] > 0.5
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        raise NoPerson("No person found in the picture.")
    pose = {"size": [w, h], "points": pts, "top": int(ys.min()), "bottom": int(ys.max()),
            "left": int(xs.min()), "right": int(xs.max())}
    gray = np.asarray(img.convert("L"), np.float32)
    return pose, _png((mask * 255).astype(np.uint8)), _png(fill_background(gray, mask))
