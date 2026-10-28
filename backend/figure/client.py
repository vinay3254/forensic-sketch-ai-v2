"""Client for the Blender figure worker (blender_worker/server.py)."""

from typing import Protocol

import httpx

from backend.errors import AppError
from backend.figure.params import FigureParams

TIMEOUT = 60  # a pencil render takes ~4 s; a model rebuild well under a second


class FigureWorker(Protocol):
    def glb(self, p: FigureParams) -> bytes: ...
    def png(self, p: FigureParams) -> bytes: ...
    def blend(self, p: FigureParams) -> bytes: ...


class HttpFigureWorker:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    def _post(self, path: str, p: FigureParams) -> bytes:
        try:
            r = httpx.post(f"{self.url}{path}", json=p.model_dump(), timeout=TIMEOUT)
            r.raise_for_status()
        except httpx.HTTPError:
            raise AppError("AI_UNAVAILABLE", "The Blender worker did not respond. Try again.", 503)
        return r.content

    def glb(self, p: FigureParams) -> bytes:
        return self._post("/figure.glb", p)

    def png(self, p: FigureParams) -> bytes:
        return self._post("/figure.png", p)

    def blend(self, p: FigureParams) -> bytes:
        return self._post("/figure.blend", p)
