"""CPU checks: head3d/.venv/bin/python -m unittest discover -s head3d -p test_surface.py"""

import unittest
import json
import struct

import numpy as np
from PIL import Image
import trimesh

from body_surface import apply_reference


class SurfaceTests(unittest.TestCase):
    def test_reference_front_has_uv_texture_and_back_retains_colors(self):
        mesh = trimesh.creation.box(extents=[0.5, 1.8, 0.3])
        mesh.visual.vertex_colors = [90, 90, 90, 255]
        image = Image.new('RGB', (100, 200), 'red')
        foreground = Image.new('RGBA', image.size, (0, 0, 0, 0))
        foreground.paste((255, 0, 0, 255), (20, 10, 80, 190))
        result = apply_reference(mesh, image, foreground)
        front = result.geometry['reference_front']
        back = result.geometry['inferred_surfaces']
        self.assertTrue(np.all(front.face_normals[:, 2] > 0.2))
        self.assertTrue(np.all(back.face_normals[:, 2] <= 0.2))
        self.assertEqual(len(front.faces) + len(back.faces), len(mesh.faces))
        self.assertTrue(np.all(front.visual.uv >= 0))
        self.assertTrue(np.all(front.visual.uv <= 1))
        self.assertIsNotNone(front.visual.material.baseColorTexture)
        glb = result.export(file_type='glb', include_normals=True)
        size = struct.unpack('<I', glb[12:16])[0]
        document = json.loads(glb[20:20 + size])
        for item in document['meshes']:
            material = document['materials'][item['primitives'][0]['material']]
            self.assertEqual(material['pbrMetallicRoughness']['metallicFactor'], 0)

    def test_empty_foreground_is_rejected(self):
        mesh = trimesh.creation.box()
        with self.assertRaises(ValueError):
            apply_reference(mesh, Image.new('RGB', (50, 50)), Image.new('RGBA', (50, 50)))


if __name__ == '__main__':
    unittest.main()
