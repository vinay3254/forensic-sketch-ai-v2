"""SketchLab 3D head worker. Photo PNG in, approximate 3D head (GLB with vertex colours) out.

Runs TripoSR on the GPU in its own process so the web app never loads PyTorch.
  uv run --project head3d python head3d/fetch_triposr.py           # once
  cd head3d && uv run uvicorn server:app --port 8010               # then set HEAD3D_URL=http://127.0.0.1:8010
"""

import io
import sys
import threading
import types
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from skimage.measure import marching_cubes as sk_marching_cubes

VENDOR = Path(__file__).resolve().parent / "vendor" / "TripoSR"
MC_RESOLUTION = 192
FOREGROUND_RATIO = 0.85


def _marching_cubes(volume: torch.Tensor, level: float):
    # stands in for torchmcubes, which needs a CUDA build toolchain; same output layout
    v, f, _, _ = sk_marching_cubes(volume.cpu().numpy(), level)
    return torch.from_numpy(v[:, ::-1].copy()).float(), torch.from_numpy(f.astype(np.int64))


sys.modules["torchmcubes"] = types.SimpleNamespace(marching_cubes=_marching_cubes)
sys.path.insert(0, str(VENDOR))

state: dict = {}
gpu = threading.Lock()  # one head at a time on a 6 GB card


@asynccontextmanager
async def lifespan(app: FastAPI):
    import rembg
    from tsr.system import TSR

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(4096)
    state.update(model=model.to(device), device=device, rembg=rembg.new_session())
    yield


app = FastAPI(title="SketchLab head3d", lifespan=lifespan)


def make_head(photo: Image.Image) -> bytes:
    from tsr.utils import remove_background, resize_foreground, to_gradio_3d_orientation

    img = resize_foreground(remove_background(photo, state["rembg"]), FOREGROUND_RATIO)
    a = np.asarray(img).astype(np.float32) / 255
    img = Image.fromarray(((a[:, :, :3] * a[:, :, 3:4] + (1 - a[:, :, 3:4]) * 0.5) * 255).astype(np.uint8))
    with gpu, torch.no_grad():
        codes = state["model"]([img], device=state["device"])
        mesh = state["model"].extract_mesh(codes, True, resolution=MC_RESOLUTION)[0]
    mesh = to_gradio_3d_orientation(mesh)  # y up, facing +z: what glTF viewers expect
    return mesh.export(file_type="glb")


@app.post("/head")
async def head(request: Request):
    try:
        photo = Image.open(io.BytesIO(await request.body())).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(422, "Body must be an image.")
    return Response(make_head(photo), media_type="model/gltf-binary")


@app.get("/health")
def health():
    return {"status": "ok", "device": state.get("device")}
