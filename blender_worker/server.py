"""TRACE figure worker: Blender (bpy) kept loaded, so a figure rebuild takes a fraction of a second.

  cd blender_worker && uv run uvicorn server:app --port 8020     # then FIGURE_URL=http://127.0.0.1:8020

POST /figure.glb   params JSON -> GLB (for the live 3D view)
POST /figure.png   params JSON -> pencil line-art PNG (case sheet)
POST /figure.blend params JSON -> .blend file (open in the Blender app)
"""

import os
import threading
import time
from dataclasses import asdict

import bpy
from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel, Field

import figure

app = FastAPI(title="TRACE figure worker")
# Blender operators (glTF export, primitives) need Blender's main thread, so the endpoints are
# async and run on the event loop, which is the main thread; requests are served one at a time.
blender = threading.Lock()
bpy.ops.wm.read_factory_settings(use_empty=True)


class ParamsIn(BaseModel):
    height_cm: float = Field(172, ge=120, le=220)
    build: float = Field(0.35, ge=0, le=1)
    muscle: float = Field(0.4, ge=0, le=1)
    gender: float = Field(0.0, ge=0, le=1)
    age: float = Field(35, ge=10, le=100)
    top: str = "tshirt"
    bottom: str = "trousers"
    headwear: str = "none"


def _make(params: ParamsIn, suffix: str, write) -> Response:
    with blender:
        t = time.perf_counter()
        figure.build(figure.Params(**params.model_dump()))
        path = figure.tmp(suffix)
        try:
            write(path)
            with open(path, "rb") as f:
                data = f.read()
        finally:
            os.unlink(path)
    media = {".glb": "model/gltf-binary", ".png": "image/png", ".blend": "application/x-blender"}[suffix]
    return Response(data, media_type=media, headers={"X-Build-Ms": str(round((time.perf_counter() - t) * 1000))})


@app.post("/figure.glb")
async def glb(params: ParamsIn):
    return _make(params, ".glb", figure.export_glb)


@app.post("/figure.png")
async def png(params: ParamsIn):
    return _make(params, ".png", figure.render_png)


@app.post("/figure.blend")
async def blend(params: ParamsIn):
    return _make(params, ".blend", figure.save_blend)


@app.get("/health")
def health():
    return {"status": "ok", "blender": bpy.app.version_string, "defaults": asdict(figure.Params())}
