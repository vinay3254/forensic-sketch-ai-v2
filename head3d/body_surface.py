"""Project the actual reference onto front geometry; keep inferred colors elsewhere."""

import numpy as np
import trimesh


def apply_reference(mesh, image, foreground):
    if mesh.volume < 0:
        mesh.invert()
    # glTF vertex colors are linear; TripoSR's RGB predictions are display colors.
    colors = mesh.visual.vertex_colors.copy()
    rgb = colors[:, :3].astype(np.float32) / 255
    colors[:, :3] = np.rint(np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4) * 255).astype(np.uint8)
    mesh.visual.vertex_colors = colors
    mesh.visual.material = trimesh.visual.material.PBRMaterial(
        baseColorFactor=[255] * 4, metallicFactor=0, roughnessFactor=1,
    )
    bounds = foreground.getchannel('A').getbbox()
    if bounds is None:
        raise ValueError('No foreground person found')
    lo, hi = mesh.bounds
    if hi[0] <= lo[0] or hi[1] <= lo[1]:
        raise ValueError('Empty person geometry')
    x = (mesh.vertices[:, 0] - lo[0]) / (hi[0] - lo[0])
    y = (mesh.vertices[:, 1] - lo[1]) / (hi[1] - lo[1])
    left, top, right, bottom = bounds
    uv = np.column_stack(((left + x * (right - left)) / image.width,
                          1 - (bottom - y * (bottom - top)) / image.height))
    front = mesh.face_normals[:, 2] > 0.2
    surface = trimesh.Trimesh(vertices=mesh.vertices.copy(), faces=mesh.faces[front].copy(), process=False)
    surface.visual = trimesh.visual.texture.TextureVisuals(
        uv=uv,
        material=trimesh.visual.material.PBRMaterial(baseColorTexture=image.convert('RGB'), metallicFactor=0, roughnessFactor=1),
    )
    back = mesh.copy()
    back.update_faces(~front)
    # ColorVisuals.copy() does not carry its attached material into the new visual.
    back.visual.material = mesh.visual.material
    return trimesh.Scene({'reference_front': surface, 'inferred_surfaces': back})
