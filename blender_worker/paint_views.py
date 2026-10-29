"""Paint a generated 3D shape with the case's front, side and back drawings. Run by backend/figure/kaggle3d.py:

  python -I paint_views.py SHAPE.glb JOB_DIR OUT_DIR HEIGHT_CM

The shape is scaled to the stated height and stood on the ground; each face takes the drawing that looks at it
most squarely (front, back, or the side view for both sides), registered by the outline's centre and the
picture's top and bottom. JOB_DIR holds <view>_pose.json / _mask.png / _fill.png from backend/figure/pose.py.
Writes OUT_DIR/figure.glb and figure.blend.
"""
import json, os, sys
import bpy
import numpy as np
from mathutils import Matrix

mesh_path, job, out_dir, height_cm = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=mesh_path)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
deps = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(objs[0].evaluated_get(deps), depsgraph=deps)
me.transform(objs[0].matrix_world)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
co = np.array([v.co[:] for v in me.vertices])
zt = height_cm / 100
k = zt / np.ptp(co[:, 2])
me.transform(Matrix.Translation((-(co[:, 0].max() + co[:, 0].min()) / 2 * k, -(co[:, 1].max() + co[:, 1].min()) / 2 * k, -co[:, 2].min() * k)) @ Matrix.Scale(k, 4))
obj = bpy.data.objects.new("figure", me)
bpy.context.scene.collection.objects.link(obj)
for p in me.polygons:
    p.use_smooth = True
me.update()


def view(name):
    p = os.path.join(job, f"{name}_pose.json")
    return json.load(open(p)) if os.path.exists(p) else None


def mask(name):
    im = bpy.data.images.load(os.path.join(job, f"{name}_pose_mask.png"))
    return np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1, :, 0] > 0.5


views = [(n, v) for n in ("front", "side", "back") if (v := view(n))]
tiles = {n: i for i, (n, _) in enumerate(views)}
co = np.array([v.co[:] for v in me.vertices])
geo = {}
for n, v in views:
    vs = (v["bottom"] - v["top"]) / zt
    m = mask(n)
    # horizontal centre: the outline's centre at mid-height lines up with the mesh's centre there
    mid = int(v["top"] + (zt * 0.55) * vs)
    cols = np.nonzero(m[mid])[0]
    ccol = (cols.min() + cols.max()) / 2
    if n == "side":
        band = np.abs(co[:, 2] - zt * 0.45) < 0.03
        mc = (co[band, 1].min() + co[band, 1].max()) / 2
    else:
        band = np.abs(co[:, 2] - zt * 0.45) < 0.03
        mc = (co[band, 0].min() + co[band, 0].max()) / 2
    geo[n] = (v["size"][0], v["size"][1], v["top"], vs, ccol, mc)


def uv_for(n, c):
    vw, vh, top, vs, ccol, mc = geo[n]
    if n == "front":
        px = ccol + (c.x - mc) * vs
    elif n == "back":
        px = ccol - (c.x - mc) * vs
    else:
        px = ccol - (c.y - mc) * vs
    return ((tiles[n] + px / vw) / len(views), 1 - (top + (zt - c.z) * vs) / vh)


for uv in list(me.uv_layers):
    me.uv_layers.remove(uv)
proj = me.uv_layers.new(name="views")
for poly in me.polygons:
    nrm = poly.normal
    score = {"front": -nrm.y}
    if "back" in tiles:
        score["back"] = nrm.y
    if "side" in tiles:
        score["side"] = abs(nrm.x) * 0.9
    best = max(score, key=score.get)
    for li in poly.loop_indices:
        proj.data[li].uv = uv_for(best, me.vertices[me.loops[li].vertex_index].co)

fills = [bpy.data.images.load(os.path.join(job, f"{n}_pose_fill.png")) for n, _ in views]
atlas = np.concatenate([np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4) for im in fills], axis=1)
img = bpy.data.images.new("views", atlas.shape[1], atlas.shape[0])
img.pixels[:] = atlas.ravel()
img.pack()
mat = bpy.data.materials.new("picture")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = img
mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.9
me.materials.append(mat)
bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, "figure.glb"), export_format="GLB")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "figure.blend"))
print(f"summary: {height_cm:.0f} cm, {len(me.vertices)} vertices, painted from {', '.join(tiles)}", flush=True)
