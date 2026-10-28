"""Realistic body: a MakeHuman (MPFB2) human fitted to a full-body picture. Run by backend/figure/realistic.py:

  python -I realistic_body.py MPFB_SRC JOB_DIR OUT_DIR HEIGHT_CM GENDER(0 female..1 male) AGE BUILD(0 slim..1 heavy)

JOB_DIR holds front_pose.json / _mask.png / _fill.png from backend/figure/pose.py, and the same for "side"
(the person facing the picture's right edge) and "back" when those views exist. Writes OUT_DIR/figure.glb
and figure.blend, and prints "summary: ..." on success.

Steps: build the human, aim its arms and legs like the picture, stretch it between landmarks so eyes,
shoulders, hips, knees and ankles sit at the picture's heights, fit every 1 cm slice to the front outline
(width) and the side outline (depth), then texture each face from the view that looks at it most squarely.
"""

import importlib
import json
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

src, job, out_dir = sys.argv[1:4]
height_cm, gender, age, build = (float(v) for v in sys.argv[4:8])
os.makedirs(out_dir, exist_ok=True)
t0 = time.time()

# --- MPFB2, loaded as an add-on from its source folder ---------------------------------------------
sys.path.insert(0, src)
bpy.ops.wm.read_factory_settings(use_empty=True)
_home = os.path.join(out_dir, "mpfb_user")


def _ext_path(package, *, path="", create=False):
    # MPFB expects to be an installed extension; give it a user folder outside one
    d = os.path.join(_home, path)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


bpy.utils.extension_path_user = _ext_path
import addon_utils  # noqa: E402


def _fail(e):
    raise e


addon_utils.enable("mpfb", default_set=True, handle_error=_fail)
HS = importlib.import_module("mpfb.services.humanservice").HumanService
TS = importlib.import_module("mpfb.services.targetservice").TargetService
HOP = importlib.import_module("mpfb.entities.objectproperties").HumanObjectProperties


def load_view(name):
    path = os.path.join(job, f"{name}_pose.json")
    return json.load(open(path)) if os.path.exists(path) else None


def load_mask(name):
    im = bpy.data.images.load(os.path.join(job, f"{name}_pose_mask.png"))
    return np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1, :, 0] > 0.5  # top row first


pose = load_view("front")
P = {k: Vector((v[0], v[1])) for k, v in pose["points"].items()}

# --- body: the human the witness described, rigged -----------------------------------------------
human = HS.create_human(mask_helpers=True, detailed_helpers=True)  # the rig needs the joint helpers
age_macro = 0.5 + min((age - 25) / 65, 1) * 0.5 if age >= 25 else 0.1875 + max(age - 11, 0) / 14 * 0.3125
for key, value in dict(gender=gender, age=age_macro, muscle=0.5, weight=0.3 + 0.55 * build, height=0.5).items():
    HOP.set_value(key, value, entity_reference=human)
TS.reapply_macro_details(human)
rig = HS.add_builtin_rig(human, "default")
bpy.context.view_layer.update()


# --- pose: each arm and leg points the way it does in the picture -----------------------------------
def image_dir(a, b):
    d = P[b] - P[a]  # picture: x right, y down -> world: +X (person's left), +Z up
    return Vector((d.x, 0, -d.y)).normalized()


def aim(bone, target):
    pb = rig.pose.bones[bone]
    m = rig.matrix_world @ pb.matrix
    head = m.to_translation()
    cur = ((rig.matrix_world @ pb.tail) - head).normalized()
    rot = cur.rotation_difference(target).to_matrix().to_4x4()
    pb.matrix = rig.matrix_world.inverted() @ (Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ m)
    bpy.context.view_layer.update()


for side in ("L", "R"):
    s = side.lower()
    aim(f"upperarm01.{side}", image_dir(f"{s}_shoulder", f"{s}_elbow"))
    aim(f"lowerarm01.{side}", image_dir(f"{s}_elbow", f"{s}_wrist"))
    aim(f"upperleg01.{side}", image_dir(f"{s}_hip", f"{s}_knee"))
    aim(f"lowerleg01.{side}", image_dir(f"{s}_knee", f"{s}_ankle"))


def bone_z(name):
    return (rig.matrix_world @ rig.pose.bones[name].head).z


def both(name):
    return (bone_z(f"{name}.L") + bone_z(f"{name}.R")) / 2


rig_heights = [both("foot"), both("lowerleg01"), both("upperleg01"), both("upperarm01"), both("eye")]


def part_of(bone):
    """Body part of a deform bone: arm and leg sides are kept apart; the rest is head or torso."""
    side = bone[-1] if bone[-2:] in (".L", ".R") else ""
    if any(k in bone for k in ("upperarm", "lowerarm", "wrist", "finger", "thumb", "metacarpal")):
        return "arm" + side
    if any(k in bone for k in ("upperleg", "lowerleg", "foot", "toe")):
        return "leg" + side
    if bone.startswith(("head", "jaw", "eye", "tongue", "special", "temporal", "oculi", "orbicularis", "levator",
                        "risorius", "nose", "cheek", "lip", "brow", "ear")):
        return "head"
    return "torso"


# --- one plain mesh: pose and hidden helpers applied, scaled to the stated height ------------------
bones = {b.name for b in rig.data.bones}
group_names = {g.index: g.name for g in human.vertex_groups if g.name in bones}  # deform groups only
deps = bpy.context.evaluated_depsgraph_get()
mesh = bpy.data.meshes.new_from_object(human.evaluated_get(deps), depsgraph=deps)
mesh.transform(human.matrix_world)
labels = []  # each vertex's body part, from its strongest bone weight
for v in mesh.vertices:
    g = max((x for x in v.groups if x.group in group_names), key=lambda x: x.weight, default=None)
    labels.append(part_of(group_names[g.group]) if g else "torso")
lab = np.array(labels)
zs = [v.co.z for v in mesh.vertices]
zt = height_cm / 100
k = zt / (max(zs) - min(zs))
mesh.transform(Matrix.Translation((0, 0, -min(zs) * k)) @ Matrix.Scale(k, 4))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
body = bpy.data.objects.new("figure", mesh)
bpy.context.scene.collection.objects.link(body)
for poly in mesh.polygons:
    poly.use_smooth = True

top, bottom = pose["top"], pose["bottom"]
scale = (bottom - top) / zt  # front picture: pixels per metre
cx = (P["l_hip"].x + P["r_hip"].x) / 2


def pic_z(*names):
    return zt - (sum(P[n].y for n in names) / len(names) - top) / scale


# --- proportions: eyes, shoulders, hips, knees and ankles at the picture's heights ------------------
model = [0.0] + [(z - min(zs)) * k for z in rig_heights] + [zt]
picture = [0.0, pic_z("l_ankle", "r_ankle"), pic_z("l_knee", "r_knee"), pic_z("l_hip", "r_hip"),
           pic_z("l_shoulder", "r_shoulder"), pic_z("l_eye", "r_eye"), zt]
if all(np.diff(model) > 0) and all(np.diff(picture) > 0):
    for v in mesh.vertices:
        v.co.z = float(np.interp(v.co.z, model, picture))
    mesh.update()


# --- outline: every 1 cm slice of the body takes the picture's width, and the side view's depth ------
def runs(xs, gap):
    xs = np.sort(xs)
    cuts = np.nonzero(np.diff(xs) > gap)[0]
    return list(zip(np.r_[xs[0], xs[cuts + 1]], np.r_[xs[cuts], xs[-1]]))


mask = load_mask("front")
co = np.array([v.co[:] for v in mesh.vertices])
disp = np.zeros_like(co)
has = np.zeros(len(co), bool)
BAND = 0.01
bands = np.floor(co[:, 2] / BAND).astype(int)
shoulder_z = pic_z("l_shoulder", "r_shoulder")
for b in np.unique(bands):
    z = (b + 0.5) * BAND
    if z > shoulder_z:  # above the shoulders the outline is a hood or collar, not the body
        continue
    idx = np.nonzero(bands == b)[0]
    row = int(round(top + (zt - z) * scale))
    if not 0 <= row < mask.shape[0]:
        continue
    cols = np.nonzero(mask[row])[0]
    if len(cols) < 3:
        continue
    pic = [((s - cx) / scale, (e - cx) / scale) for s, e in runs(cols.astype(float), 2)]
    # each part (torso, an arm, a leg) goes with the picture shape it overlaps most; its extent comes from a
    # few cm around the slice, so a sparse slice still sees the arms
    groups = {}
    win = np.nonzero(np.abs(co[:, 2] - z) < 0.025)[0]
    for name in set(lab[win]):
        pw, p = win[lab[win] == name], idx[lab[idx] == name]
        a, e = co[pw, 0].min(), co[pw, 0].max()
        if len(p) == 0 or len(pw) < 3 or e - a < 0.01:
            continue
        j = max(range(len(pic)), key=lambda i: min(pic[i][1], e) - max(pic[i][0], a))
        if min(pic[j][1], e) - max(pic[j][0], a) > 0:
            groups.setdefault(j, []).append((a, e, p, name))
    for j, parts in groups.items():
        parts.sort(key=lambda t: t[0])
        left, right = pic[j]
        # arms hanging against the body keep their own size and slide to the outline; what lies between
        # them (the torso, or a lone leg) is scaled to fill the rest
        if len(parts) > 1 and parts[0][3].startswith("arm"):
            pa, pe, p, _ = parts.pop(0)
            disp[p, 0], has[p] = left - pa, True
            left += pe - pa
        if len(parts) > 1 and parts[-1][3].startswith("arm"):
            pa, pe, p, _ = parts.pop()
            disp[p, 0], has[p] = right - pe, True
            right -= pe - pa
        ratio = (right - left) / sum(pe - pa for pa, pe, _, _ in parts)
        if not 0.6 < ratio < 2.2:
            continue
        x0 = left
        for pa, pe, p, _ in parts:
            disp[p, 0] = x0 + (co[p, 0] - pa) * ratio - co[p, 0]
            disp[p, 1] = (co[p, 1] - co[p, 1].mean()) * (ratio - 1) * 0.8  # thicker too, until the side view says
            has[p] = True
            x0 += (pe - pa) * ratio

# the head keeps its shape: scaled as a whole to the picture's head width at eye level
eye_z = pic_z("l_eye", "r_eye")
cols = np.nonzero(mask[int(round(top + (zt - eye_z) * scale))])[0]
near = (lab == "head") & (np.abs(co[:, 2] - eye_z) < 0.02)
head_ratio = 1.0
if len(cols) and near.sum() > 3:
    head_ratio = float(np.clip((cols.max() - cols.min()) / scale / np.ptp(co[near, 0]), 0.85, 1.25))
    chin_z = pic_z("mouth_l", "mouth_r") - 0.04
    head = co[:, 2] > chin_z
    disp[head] = (co[head] - np.array([0.0, co[head, 1].mean(), chin_z])) * (head_ratio - 1)
    has[head] = True

hip_z = pic_z("l_hip", "r_hip")
y_centre = co[(np.abs(co[:, 2] - hip_z) < 0.03) & (lab == "torso"), 1].mean()
side = load_view("side")
if side:  # depth: each slice of torso and legs takes the side view's outline (the picture faces right)
    smask = load_mask("side")
    s_top, ss = side["top"], (side["bottom"] - side["top"]) / zt
    s_cx = (side["points"]["l_hip"][0] + side["points"]["r_hip"][0]) / 2
    trunk = (lab != "head") & (lab != "armL") & (lab != "armR")
    for b in np.unique(bands):
        z = (b + 0.5) * BAND
        if z > shoulder_z:
            continue
        idx = np.nonzero((bands == b) & (lab != "head"))[0]
        win = np.nonzero((np.abs(co[:, 2] - z) < 0.025) & trunk)[0]
        row = int(round(s_top + (zt - z) * ss))
        if len(idx) == 0 or len(win) < 3 or not 0 <= row < smask.shape[0]:
            continue
        cols = np.nonzero(smask[row])[0]
        if len(cols) < 3:
            continue
        c, d = sorted((-(cols.min() - s_cx) / ss + y_centre, -(cols.max() - s_cx) / ss + y_centre))
        a, e = co[win, 1].min(), co[win, 1].max()
        ratio = (d - c) / (e - a)
        if 0.6 < ratio < 2.2:
            disp[idx, 1] = c + (co[idx, 1] - a) * ratio - co[idx, 1]
            has[idx] = True

# smooth the corrections over the mesh: slices blend, and unmatched parts follow their neighbours
edges = np.array([e.vertices[:] for e in mesh.edges])
for _ in range(25):
    acc, cnt = np.zeros_like(disp), np.zeros(len(co))
    np.add.at(acc, edges[:, 0], disp[edges[:, 1]])
    np.add.at(acc, edges[:, 1], disp[edges[:, 0]])
    np.add.at(cnt, edges[:, 0], 1)
    np.add.at(cnt, edges[:, 1], 1)
    disp = np.where(has[:, None], 0.5 * disp + 0.5 * acc / np.maximum(cnt, 1)[:, None], acc / np.maximum(cnt, 1)[:, None])
co += disp
for v, c in zip(mesh.vertices, co):
    v.co = c
mesh.update()

# --- texture: each face takes the view (front, back or side) that looks at it most squarely ---------
views = [("front", pose)] + [(n, load_view(n)) for n in ("side", "back") if load_view(n)]
fills = [bpy.data.images.load(os.path.join(job, f"{n}_pose_fill.png")) for n, _ in views]
views = [(n, v) for (n, v), im in zip(views, fills) if im.size[1] == fills[0].size[1]]  # one texture row
fills = [im for im in fills if im.size[1] == fills[0].size[1]]
tiles = {n: i for i, (n, _) in enumerate(views)}
geo = {n: (v["size"][0], v["size"][1], v["top"], (v["bottom"] - v["top"]) / zt,
           (v["points"]["l_hip"][0] + v["points"]["r_hip"][0]) / 2) for n, v in views}

# the side view's head is lined up by itself (head centre at eye level), the rest by the hips
head_eye = co[(lab == "head") & (np.abs(co[:, 2] - eye_z) < 0.02), 1]
head_y = (head_eye.min() + head_eye.max()) / 2 if len(head_eye) else y_centre
side_head_px = None
if "side" in tiles:
    scols = np.nonzero(load_mask("side")[int(round(side["top"] + (zt - eye_z) * geo["side"][3]))])[0]
    if len(scols):
        side_head_px = (scols.min() + scols.max()) / 2


def uv_for(name, c, part):
    vw, vh, vtop, vs, vcx = geo[name]
    if name == "front":
        px = vcx + c.x * vs
    elif name == "back":  # seen from behind: picture right is the person's right (-X)
        px = vcx - c.x * vs
    elif part == "head" and side_head_px is not None:
        px = side_head_px - (c.y - head_y) * vs
    else:  # side view faces right: picture right is the person's front (-Y); both sides use it
        px = vcx - (c.y - y_centre) * vs
    return ((tiles[name] + px / vw) / len(views), 1 - (vtop + (zt - c.z) * vs) / vh)


for uv in list(mesh.uv_layers):
    mesh.uv_layers.remove(uv)
proj = mesh.uv_layers.new(name="views")
for poly in mesh.polygons:
    n, part = poly.normal, labels[poly.vertices[0]]
    score = {"front": -n.y if n.y < 0 or "back" in tiles else 0.01}
    if "back" in tiles:
        score["back"] = n.y
    if "side" in tiles and part != "torso":  # the torso's sides are behind the arms in a side view
        score["side"] = abs(n.x) * 1.05
    view = max(score, key=score.get)
    for li in poly.loop_indices:
        proj.data[li].uv = uv_for(view, mesh.vertices[mesh.loops[li].vertex_index].co, part)

atlas = np.concatenate([np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4) for im in fills], axis=1)
img = bpy.data.images.new("views", atlas.shape[1], atlas.shape[0])
img.pixels[:] = atlas.ravel()
img.pack()  # the .blend carries its own texture
mat = bpy.data.materials.new("picture")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = img
mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.9
mesh.materials.append(mat)

bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, "figure.glb"), export_format="GLB", use_selection=False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "figure.blend"))
print(f"summary: {height_cm:.0f} cm, posed and fitted to the picture's outline"
      f"{', depth from the side view' if side else ''}; textured from {', '.join(tiles)} "
      f"({len(mesh.vertices)} vertices, {time.time() - t0:.1f} s)", flush=True)
