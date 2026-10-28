"""By-hand check of a running worker (needs the GPU): python head3d/smoke.py photo.png [url]"""

import io
import sys
import time

import httpx
import trimesh

url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8010"
t = time.perf_counter()
r = httpx.post(f"{url}/head", content=open(sys.argv[1], "rb").read(), timeout=300)
r.raise_for_status()
mesh = trimesh.load(io.BytesIO(r.content), file_type="glb", force="mesh")
print(f"{time.perf_counter() - t:.0f}s, {len(r.content) // 1024} KB, {len(mesh.vertices)} vertices, extents {mesh.extents.round(2)}")
