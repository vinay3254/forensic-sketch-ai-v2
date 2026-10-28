"""Client for the 3D head worker (head3d/server.py), which runs TripoSR on the GPU in its own process."""

from typing import Protocol

import httpx

from backend.errors import AppError

HEAD_TIMEOUT = 180  # the worker takes about a minute per head


class Head3DClient(Protocol):
    def make_head(self, photo_png: bytes) -> bytes: ...  # GLB
    def make_body(self, image_png: bytes, height_cm: float) -> bytes: ...


class HttpHead3DClient:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def make_head(self, photo_png: bytes) -> bytes:
        return self._reconstruct("/head", photo_png)

    def make_body(self, image_png: bytes, height_cm: float) -> bytes:
        return self._reconstruct(f"/body?height_cm={height_cm}", image_png)

    def _reconstruct(self, path: str, image_png: bytes) -> bytes:
        try:
            r = httpx.post(f"{self.url}{path}", content=image_png, headers={"Content-Type": "image/png"}, timeout=HEAD_TIMEOUT)
            r.raise_for_status()
        except httpx.HTTPError:
            raise AppError("AI_UNAVAILABLE", "The 3D service did not respond. Try again.", 503)
        return r.content
