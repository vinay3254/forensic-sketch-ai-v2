# TRACE: runs on a Kaggle GPU (pushed by backend/figure/kaggle3d.py). Hunyuan3D-2 multi-view turns the
# front, side and back drawings into one 3D shape (shape.glb); TRACE paints it with the drawings afterwards.
import glob, os, shutil, subprocess, sys, time

t0 = time.time()


def log(*a):
    print(f"[{time.time() - t0:6.0f}s]", *a, flush=True)


def sh(cmd, cwd=None):
    log("$", cmd)
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:], flush=True)
        raise RuntimeError(f"failed: {cmd}")


data = os.path.dirname(glob.glob("/kaggle/input/**/front.png", recursive=True)[0])
repo = "/kaggle/hy3d"  # outside /kaggle/working, so it is not part of the output
sh(f"git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git {repo}")
sh("pip install -q -r requirements.txt", cwd=repo)
sh("pip install -q -e .", cwd=repo)
sys.path.insert(0, repo)

import torch  # noqa: E402
from PIL import Image  # noqa: E402
from hy3dgen.rembg import BackgroundRemover  # noqa: E402
from hy3dgen.shapegen import DegenerateFaceRemover, FaceReducer, FloaterRemover, Hunyuan3DDiTFlowMatchingPipeline  # noqa: E402

rembg = BackgroundRemover()


def load(name, mirror=False):
    im = Image.open(os.path.join(data, f"{name}.png")).convert("RGB")
    return rembg(im.transpose(Image.FLIP_LEFT_RIGHT) if mirror else im)


views = {"front": load("front")}
if os.path.exists(os.path.join(data, "back.png")):
    views["back"] = load("back")
if os.path.exists(os.path.join(data, "side.png")):
    # the side drawing faces the picture's right edge (we see the person's right side); the left is its mirror
    views["right"], views["left"] = load("side"), load("side", mirror=True)
log("inputs ready:", sorted(views))
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
    "tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv", variant="fp16")
mesh = pipe(image=views, num_inference_steps=30, octree_resolution=380, num_chunks=20000,
            generator=torch.manual_seed(12345), output_type="trimesh")[0]
for f in (FloaterRemover(), DegenerateFaceRemover(), FaceReducer()):
    mesh = f(mesh)
mesh.export("/kaggle/working/shape.glb")
log("shape done:", len(mesh.vertices), "vertices; GPU peak", round(torch.cuda.max_memory_allocated() / 1e9, 1), "GB")
shutil.rmtree(repo, ignore_errors=True)
