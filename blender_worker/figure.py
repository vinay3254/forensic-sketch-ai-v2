"""Build a parametric mannequin in Blender from a handful of numbers, and export it.

Only Blender's own tools are used: the body is a stick skeleton turned into a smooth surface by
the Skin and Subdivision modifiers; garments are cut from that finished surface and pushed out a
little, so they follow the body exactly. Units are metres; the figure stands on z=0, facing -y.
"""

import os
import tempfile
from dataclasses import dataclass

import bmesh
import bpy

TOPS = ("none", "tshirt", "shirt", "hoodie", "jacket", "kurta")
BOTTOMS = ("none", "trousers", "jeans", "shorts", "skirt")
HEADWEAR = ("none", "cap")


@dataclass
class Params:
    height_cm: float = 172
    build: float = 0.35  # 0 slim .. 1 obese
    muscle: float = 0.4  # 0 soft .. 1 muscular
    gender: float = 0.0  # 0 male .. 1 female
    age: float = 35
    top: str = "tshirt"
    bottom: str = "trousers"
    headwear: str = "none"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def skeleton(p: Params):
    """Joint positions (x, y, z) with skin radius, plus the bones joining them."""
    H = _clamp(p.height_cm, 120, 220) / 100
    s = H / 1.75
    b, m, g = _clamp(p.build, 0, 1), _clamp(p.muscle, 0, 1), _clamp(p.gender, 0, 1)
    girth = 1 + 0.95 * b
    limb = (1 + 0.45 * b) * (1 + 0.25 * m)
    old = _clamp((p.age - 40) / 40, 0, 1)
    sh = (0.215 - 0.035 * g + 0.02 * m) * s
    hipw = (0.095 + 0.03 * g) * s * (1 + 0.55 * b)
    arm_out = 0.03 * s + 0.07 * b * s
    stoop = 0.03 * old * s
    J = {
        "pelvis": ((0, 0, 0.53 * H), 0.125 * s * girth),
        "belly": ((0, -0.02 * b * s, 0.62 * H), (0.12 + 0.08 * b) * s * girth),
        "chest": ((0, stoop * 0.5, 0.72 * H), (0.14 + 0.02 * m + 0.015 * g) * s * (1 + 0.6 * b)),
        "neck": ((0, stoop, 0.835 * H), 0.05 * s * (1 + 0.35 * b + 0.2 * m)),
        "head": ((0, stoop * 1.2, 0.915 * H), 0.095 * s),
        "headtop": ((0, stoop * 1.2, 0.975 * H), 0.072 * s),
        "l_sh": ((sh, 0, 0.805 * H - stoop), 0.058 * s * limb),
        "r_sh": ((-sh, 0, 0.805 * H - stoop), 0.058 * s * limb),
        "l_el": ((sh + arm_out, 0.01, 0.63 * H), 0.043 * s * limb),
        "r_el": ((-sh - arm_out, 0.01, 0.63 * H), 0.043 * s * limb),
        "l_wr": ((sh + arm_out * 1.3, 0, 0.475 * H), 0.032 * s * (1 + 0.25 * b)),
        "r_wr": ((-sh - arm_out * 1.3, 0, 0.475 * H), 0.032 * s * (1 + 0.25 * b)),
        "l_hd": ((sh + arm_out * 1.35, 0, 0.42 * H), 0.04 * s),
        "r_hd": ((-sh - arm_out * 1.35, 0, 0.42 * H), 0.04 * s),
        "l_hip": ((hipw, 0, 0.5 * H), 0.085 * s * limb),
        "r_hip": ((-hipw, 0, 0.5 * H), 0.085 * s * limb),
        "l_kn": ((hipw * 0.85, 0, 0.27 * H), 0.058 * s * limb),
        "r_kn": ((-hipw * 0.85, 0, 0.27 * H), 0.058 * s * limb),
        "l_an": ((hipw * 0.8, 0, 0.045 * H), 0.04 * s * (1 + 0.25 * b)),
        "r_an": ((-hipw * 0.8, 0, 0.045 * H), 0.04 * s * (1 + 0.25 * b)),
        "l_ft": ((hipw * 0.8, -0.1 * s, 0.015 * H), 0.035 * s),
        "r_ft": ((-hipw * 0.8, -0.1 * s, 0.015 * H), 0.035 * s),
    }
    bones = [("pelvis", "belly"), ("belly", "chest"), ("chest", "neck"), ("neck", "head"), ("head", "headtop"),
             ("chest", "l_sh"), ("chest", "r_sh"), ("l_sh", "l_el"), ("r_sh", "r_el"), ("l_el", "l_wr"),
             ("r_el", "r_wr"), ("l_wr", "l_hd"), ("r_wr", "r_hd"), ("pelvis", "l_hip"), ("pelvis", "r_hip"),
             ("l_hip", "l_kn"), ("r_hip", "r_kn"), ("l_kn", "l_an"), ("r_kn", "r_an"), ("l_an", "l_ft"), ("r_an", "r_ft")]
    return J, bones, H


# garments, cut from the body surface: torso z-range (fractions of height), sleeve end (None = no
# sleeves), leg end (None = no legs), outward offset in metres, grey tone
GARMENTS = {
    "tshirt": ((0.47, 0.84), 0.72, None, 0.012, 0.66),
    "shirt": ((0.47, 0.84), 0.48, None, 0.012, 0.7),
    "hoodie": ((0.45, 0.85), 0.47, None, 0.022, 0.62),
    "jacket": ((0.46, 0.85), 0.47, None, 0.02, 0.5),
    "kurta": ((0.30, 0.84), 0.58, 0.30, 0.014, 0.68),
    "trousers": ((0.47, 0.56), None, 0.04, 0.01, 0.55),
    "jeans": ((0.47, 0.56), None, 0.04, 0.008, 0.45),
    "shorts": ((0.47, 0.56), None, 0.31, 0.012, 0.58),
    "skirt": ((0.36, 0.56), None, 0.36, 0.018, 0.6),
}


def _material(name: str, grey: float):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (grey, grey * 0.99, grey * 0.95, 1)
    bsdf.inputs["Roughness"].default_value = 1
    mat.diffuse_color = (grey, grey * 0.99, grey * 0.95, 1)
    return mat


def _body(J: dict, bones: list):
    names = list(J)
    mesh = bpy.data.meshes.new("body")
    mesh.from_pydata([J[n][0] for n in names], [(names.index(a), names.index(b)) for a, b in bones], [])
    obj = bpy.data.objects.new("body", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("skin", "SKIN")  # creates the skin-radius layer set below
    for n, sv in zip(names, mesh.skin_vertices[0].data):
        r = J[n][1]
        sv.radius = (r, r * 0.82)
    mesh.skin_vertices[0].data[0].use_root = True
    sub = obj.modifiers.new("smooth", "SUBSURF")
    sub.levels = sub.render_levels = 2
    obj.data.materials.append(_material("skin", 0.97))
    return obj


def _garment(kind: str, body, J: dict, H: float):
    """Cut the garment's region out of the body surface and push it outward a little."""
    (z0, z1), sleeve_end, leg_end, offset, grey = GARMENTS[kind]
    sh = abs(J["l_sh"][0][0])
    hip = abs(J["l_hip"][0][0])
    leg_top = J["l_hip"][0][2]  # below the hips everything is leg, not arm
    deps = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(body.evaluated_get(deps))
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # the torso's half-width at a height, from the torso joints' skin radii
    torso = sorted((J[n][0][2], J[n][1]) for n in ("pelvis", "belly", "chest", "neck"))

    def torso_half_width(z: float) -> float:
        if z <= torso[0][0]:
            return torso[0][1]
        for (za, ra), (zb, rb) in zip(torso, torso[1:]):
            if z <= zb:
                return ra + (rb - ra) * (z - za) / (zb - za)
        return torso[-1][1]

    def covered(v) -> bool:
        x, z = abs(v.co.x), v.co.z
        if z < leg_top and x > hip * 2.2:  # a hand hanging beside the thigh
            return False
        if z >= leg_top and z < 0.86 * H and x > max(torso_half_width(z) * 1.08, sh * 0.8):
            return sleeve_end is not None and z >= sleeve_end * H  # arm: sleeve down to sleeve_end
        if z0 * H <= z <= z1 * H:
            return True
        return leg_end is not None and leg_end * H <= z < z0 * H + 0.02

    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not covered(v)], context="VERTS")
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * offset
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.clear()
    mesh.materials.append(_material(f"cloth-{kind}", grey))
    obj = bpy.data.objects.new(kind, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _cap(J: dict):
    (hx, hy, hz), hr = J["headtop"]
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=hr * 1.22)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -hr * 0.05], context="VERTS")  # a dome
    mesh = bpy.data.meshes.new("cap")
    bm.to_mesh(mesh)
    bm.free()
    cap = bpy.data.objects.new("cap", mesh)
    bpy.context.scene.collection.objects.link(cap)
    cap.location = (hx, hy - hr * 0.1, hz - hr * 0.8)  # sits down on the crown
    cap.scale.z = 0.8
    cap.data.materials.append(_material("cap", 0.4))
    return cap


def build(p: Params) -> list:
    """Replace the scene's figure with one built from `p`; returns the new objects."""
    for obj in list(bpy.data.objects):
        if obj.get("trace_figure"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    J, bones, H = skeleton(p)
    body = _body(J, bones)
    made = [body]
    if p.bottom in GARMENTS:
        made.append(_garment(p.bottom, body, J, H))
    if p.top in GARMENTS:
        made.append(_garment(p.top, body, J, H))
    if p.headwear == "cap":
        made.append(_cap(J))
    for obj in made:
        obj["trace_figure"] = True
    return made


def export_glb(path: str) -> None:
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_apply=True, use_selection=False,
                              export_cameras=False, export_lights=False, export_materials="EXPORT")


def setup_render_scene() -> None:
    scene = bpy.context.scene
    if scene.camera:
        return
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.3  # fixed scale, so a taller person is taller on the sheet
    cam.location = (0, -10, 1.08)
    cam.rotation_euler = (1.5708, 0, 0)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 2.2
    sun.rotation_euler = (0.9, 0.2, 0.3)
    scene.collection.objects.link(sun)
    world = bpy.data.worlds.new("w")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 0.55
    scene.render.film_transparent = True  # the page supplies the paper colour
    scene.render.resolution_x, scene.render.resolution_y = 520, 1000
    scene.render.use_freestyle = True
    ls = scene.view_layers[0].freestyle_settings.linesets.new("lines")
    ls.select_by_visibility = True
    ls.linestyle.color = (0.15, 0.14, 0.12)
    ls.linestyle.thickness = 1.8
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 8
    scene.cycles.device = "CPU"
    scene.view_settings.view_transform = "Standard"


def render_png(path: str) -> None:
    setup_render_scene()
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def save_blend(path: str) -> None:
    setup_render_scene()
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, compress=True)


def tmp(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="trace-figure-")
    os.close(fd)
    return path
