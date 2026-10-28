"""TRACE 3D head worker. Photo PNG in, approximate 3D head (GLB with vertex colours) out.

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
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from skimage.measure import marching_cubes as sk_marching_cubes

VENDOR = Path(__file__).resolve().parent / "vendor" / "TripoSR"
MC_RESOLUTION = 192
BODY_RESOLUTION = 128  # keep full-body extraction within this laptop's 16 GB system RAM
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
    import onnxruntime as ort
    from tsr.system import TSR

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(4096)
    options = ort.SessionOptions()
    options.enable_cpu_mem_arena = False
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    # rembg's default model is large; a small CPU segmenter leaves RAM for 3D extraction.
    state.update(model=model.to(device), device=device,
                 rembg=rembg.new_session('u2netp', sess_opts=options, providers=['CPUExecutionProvider']))
    yield


app = FastAPI(title="TRACE head3d", lifespan=lifespan)


def make_mesh(photo: Image.Image, resolution=MC_RESOLUTION, foreground=None):
    from tsr.utils import remove_background, resize_foreground, to_gradio_3d_orientation

    foreground = foreground if foreground is not None else remove_background(photo, state["rembg"])
    img = resize_foreground(foreground, FOREGROUND_RATIO)
    a = np.asarray(img).astype(np.float32) / 255
    img = Image.fromarray(((a[:, :, :3] * a[:, :, 3:4] + (1 - a[:, :, 3:4]) * 0.5) * 255).astype(np.uint8))
    with gpu, torch.no_grad():
        codes = state["model"]([img], device=state["device"])
        mesh = state["model"].extract_mesh(codes, True, resolution=resolution)[0]
    mesh = to_gradio_3d_orientation(mesh)  # y up, facing +z: what glTF viewers expect
    return mesh


def make_head(photo: Image.Image) -> bytes:
    return make_mesh(photo).export(file_type="glb")


@app.post("/body")
async def body(request: Request, height_cm: float = Query(172, ge=120, le=220)):
    import trimesh
    from body_surface import apply_reference
    from tsr.utils import remove_background
    try:
        image = Image.open(io.BytesIO(await request.body())).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(422, "Body must be an image.")
    foreground = remove_background(image, state['rembg'])
    mesh = make_mesh(image, resolution=BODY_RESOLUTION, foreground=foreground)
    # TripoSR's Gradio orientation faces -z; TRACE and Blender's glTF camera face +z.
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]))
    lo, hi = mesh.bounds
    if hi[1] - lo[1] <= 0:
        raise HTTPException(502, "Reconstruction produced no body geometry.")
    mesh.apply_translation([-((lo[0] + hi[0]) / 2), -lo[1], -((lo[2] + hi[2]) / 2)])
    mesh.apply_scale(height_cm / 100 / (hi[1] - lo[1]))
    # Preserve visible detail using the actual reference, not blurry predicted colors.
    colored = apply_reference(mesh, image, foreground)
    output = colored.export(file_type="glb", include_normals=True)
    del colored, mesh, foreground, image
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if sys.platform.startswith('linux'):
        import ctypes
        ctypes.CDLL(None).malloc_trim(0)
    return Response(output, media_type="model/gltf-binary")


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
