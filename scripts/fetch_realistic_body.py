"""Download what the realistic 3D body needs into storage/realistic/ (one-time setup):

  uv run python -m scripts.fetch_realistic_body

- MPFB2 v2.0.18, MakeHuman's Blender add-on (code GPL-3.0, body assets CC0), run by blender_worker's Python
- MediaPipe Pose Landmarker (heavy), Apache-2.0, for landmarks and the body outline

Also needs blender_worker's environment (cd blender_worker && uv sync). Restart the backend afterwards.
"""

import hashlib
import io
import shutil
import urllib.request
import zipfile

from backend.config import get_settings

MPFB_TAG = "v2.0.18"
MPFB_URL = f"https://github.com/makehumancommunity/mpfb2/archive/refs/tags/{MPFB_TAG}.zip"
POSE_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/"
            "pose_landmarker_heavy.task")
POSE_SHA256 = "64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b"


def main() -> None:
    root = get_settings().storage_dir / "realistic"
    root.mkdir(parents=True, exist_ok=True)
    model = root / "pose_landmarker_heavy.task"
    if not model.is_file():
        data = urllib.request.urlopen(POSE_URL, timeout=120).read()
        if hashlib.sha256(data).hexdigest() != POSE_SHA256:
            raise SystemExit("pose model checksum mismatch; not saved")
        model.write_bytes(data)
    print("pose model:", model)
    mpfb = root / "mpfb2"
    if not (mpfb / "src" / "mpfb").is_dir():
        with zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(MPFB_URL, timeout=300).read())) as z:
            tmp = root / "mpfb2-download"
            shutil.rmtree(tmp, ignore_errors=True)
            z.extractall(tmp)
            shutil.rmtree(mpfb, ignore_errors=True)
            next(tmp.iterdir()).rename(mpfb)
            shutil.rmtree(tmp, ignore_errors=True)
    print("MPFB2:", mpfb / "src")


if __name__ == "__main__":
    main()
