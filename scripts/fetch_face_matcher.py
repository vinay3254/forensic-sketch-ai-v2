"""Download the face-matching models into storage/models/ (one-time setup for suspect matching):

  uv run python -m scripts.fetch_face_matcher

- ArcFace w600k_r50 from InsightFace buffalo_l (ONNX): a 512-number face fingerprint. The InsightFace model
  weights are for non-commercial research use only.
- MediaPipe BlazeFace short-range (Apache-2.0): finds the face and its eye, nose and mouth points.
"""

import hashlib
import urllib.request

from backend.config import get_settings

MODELS = {
    "arcface_w600k_r50.onnx": (
        "https://huggingface.co/public-data/insightface/resolve/33c1063c49c785b7652d3fd529f86fa4f149392b/"
        "models/buffalo_l/w600k_r50.onnx",
        "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
    ),
    "blaze_face_short_range.tflite": (
        "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/"
        "blaze_face_short_range.tflite",
        None,
    ),
}


def main() -> None:
    out = get_settings().storage_dir / "models"
    out.mkdir(parents=True, exist_ok=True)
    for name, (url, sha) in MODELS.items():
        path = out / name
        if path.is_file():
            print("have", path)
            continue
        data = urllib.request.urlopen(url, timeout=600).read()
        if sha and hashlib.sha256(data).hexdigest() != sha:
            raise SystemExit(f"{name}: checksum mismatch; not saved")
        path.write_bytes(data)
        print("saved", path, len(data) // 1_000_000, "MB")


if __name__ == "__main__":
    main()
