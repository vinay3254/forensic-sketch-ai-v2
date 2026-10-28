"""Client for the Blender figure worker (blender_worker/server.py)."""

from typing import Protocol
import base64

import httpx

from backend.errors import AppError
from backend.figure.params import FigureParams

TIMEOUT = 60  # a pencil render takes ~4 s; a model rebuild well under a second


class FigureWorker(Protocol):
    def glb(self, p: FigureParams) -> bytes: ...
    def png(self, p: FigureParams) -> bytes: ...
    def blend(self, p: FigureParams) -> bytes: ...
    def import_glb(self, mesh: bytes) -> None: ...


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

    def import_glb(self, mesh: bytes) -> None:
        try:
            health = httpx.get(f"{self.url}/health", timeout=5)
            health.raise_for_status()
            if health.json().get("mode") != "desktop":
                raise AppError("DESKTOP_OFF", "Open Blender for TRACE before sending this model.", 503)
            response = httpx.post(f"{self.url}/import.glb", json={"glb": base64.b64encode(mesh).decode("ascii")}, timeout=TIMEOUT)
            response.raise_for_status()
        except (httpx.HTTPError, ValueError):
            raise AppError("AI_UNAVAILABLE", "Could not send the model to desktop Blender. Keep Blender for TRACE open.", 503)
