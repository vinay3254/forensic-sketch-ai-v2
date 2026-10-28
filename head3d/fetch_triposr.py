"""Fetch TripoSR (MIT, Tripo AI & Stability AI) at a pinned commit into head3d/vendor/TripoSR.

Run once: uv run --project head3d python head3d/fetch_triposr.py
The model weights download from Hugging Face (stabilityai/TripoSR) when the worker first starts.
"""

import subprocess
from pathlib import Path

COMMIT = "107cefdc244c39106fa830359024f6a2f1c78871"
DEST = Path(__file__).resolve().parent / "vendor" / "TripoSR"

if not DEST.exists():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", "https://github.com/VAST-AI-Research/TripoSR", str(DEST)], check=True)
subprocess.run(["git", "-C", str(DEST), "checkout", "-q", COMMIT], check=True)
print(f"TripoSR {COMMIT[:7]} in {DEST}")
