"""Launch Blender UI as TRACE's figure worker, using only Blender's bundled Python.

blender --factory-startup --python blender_worker/desktop.py -- --port 8020
"""

import argparse
import base64
from dataclasses import asdict
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Euler, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure
from desktop_http import DesktopBridge


def validated(data):
    params = figure.Params(**data)
    for key, lo, hi in (("height_cm", 120, 220), ("build", 0, 1), ("muscle", 0, 1), ("gender", 0, 1), ("age", 10, 100)):
        value = getattr(params, key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"Invalid {key}")
    for key, choices in (("top", figure.TOPS), ("bottom", figure.BOTTOMS), ("headwear", figure.HEADWEAR)):
        if getattr(params, key) not in choices:
            raise ValueError(f"Invalid {key}")
    return params


def render(path, data):
    if path == "/import.glb":
        raw = base64.b64decode(data.get("glb", ""), validate=True)
        made = figure.import_glb(raw)
        bridge.info["source"] = "image reconstruction"
        bridge.info.pop("params", None)
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    area.spaces.active.shading.type = "MATERIAL"
        return b'{"imported":true}', "application/json"
    params = validated(data)
    figure.build(params)
    bridge.info["params"] = asdict(params)
    bridge.info["source"] = "mannequin"
    suffix = Path(path).suffix
    output = figure.tmp(suffix)
    try:
        writer, media = {
            ".glb": (figure.export_glb, "model/gltf-binary"),
            ".png": (figure.render_png, "image/png"),
            ".blend": (figure.save_blend, "application/x-blender"),
        }[suffix]
        writer(output)
        return Path(output).read_bytes(), media
    finally:
        os.unlink(output)


args = argparse.ArgumentParser()
args.add_argument("--port", type=int, default=8020)
options = args.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
bridge = DesktopBridge(render, port=options.port, info={"blender": bpy.app.version_string})
# Only this newly launched factory-startup scene is cleared; existing windows are untouched.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
figure.build(figure.Params())
bpy.context.scene.name = "TRACE — connected to localhost"
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            region = area.spaces.active.region_3d
            region.view_location = Vector((0, 0, 0.9))
            region.view_distance = 3.2
            region.view_rotation = Euler((math.pi / 2, 0, 0)).to_quaternion()
            region.view_perspective = "ORTHO"
            area.spaces.active.overlay.show_floor = False
bridge.start()
bpy.app.timers.register(bridge.drain, first_interval=0.1, persistent=True)
print(f"TRACE_DESKTOP_READY {bridge.url}", flush=True)
