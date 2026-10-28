import struct
import json

import pytest

from backend.errors import AppError

def triangle_glb():
    binary = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    data = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
            'nodes': [{'mesh': 0}], 'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
            'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3'}],
            'bufferViews': [{'buffer': 0, 'byteLength': len(binary)}], 'buffers': [{'byteLength': len(binary)}]}
    chunk = json.dumps(data).encode()
    chunk += b' ' * (-len(chunk) % 4)
    total = 12 + 8 + len(chunk) + 8 + len(binary)
    return struct.pack('<4sII', b'glTF', 2, total) + struct.pack('<I4s', len(chunk), b'JSON') + chunk + struct.pack('<I4s', len(binary), b'BIN\x00') + binary


GLB = triangle_glb()


@pytest.fixture
def setup(client, app, seed_users, login):
    login(client, 'officer1', 'officer1pass')
    case_id = client.post('/api/cases', json={'title': 'Body reconstruction'}).json()['id']
    source = client.post(f'/api/cases/{case_id}/body').json()
    calls = []

    class Reconstructor:
        def make_body(self, image, height_cm):
            calls.append((image, height_cm))
            return GLB

    app.state.head3d_client = Reconstructor()
    return case_id, source, calls


def test_reconstruction_uses_saved_image_and_persists_mesh(client, setup):
    case, source, calls = setup
    original = client.get(source['image_url']).content
    response = client.post(f'/api/cases/{case}/figure/reconstruct', json={'body_id': source['id']})
    assert response.status_code == 200, response.text
    model = response.json()
    assert model['body_id'] == source['id']
    assert calls[0][0] == original
    assert calls[0][1] == 172
    assert client.get(model['mesh_url']).content == GLB
    assert client.get(f'/api/cases/{case}/figure/reconstruction').json()['id'] == model['id']
    assert client.get(source['image_url']).content == original


def test_reconstruction_requires_service_and_keeps_old_result(client, app, setup):
    case, source, _ = setup
    first = client.post(f'/api/cases/{case}/figure/reconstruct', json={'body_id': source['id']}).json()
    app.state.head3d_client = None
    assert client.post(f'/api/cases/{case}/figure/reconstruct', json={}).status_code == 503
    assert client.get(f'/api/cases/{case}/figure/reconstruction').json()['id'] == first['id']


def test_reconstruction_rejects_invalid_worker_result(client, app, setup):
    case, _, _ = setup
    app.state.head3d_client.make_body = lambda *_: b'not a GLB'
    assert client.post(f'/api/cases/{case}/figure/reconstruct', json={}).status_code == 502
    assert client.get(f'/api/cases/{case}/figure/reconstruction').json() is None


def test_header_only_glb_never_replaces_a_saved_model(client, app, setup):
    case, _, _ = setup
    first = client.post(f'/api/cases/{case}/figure/reconstruct', json={}).json()
    app.state.head3d_client.make_body = lambda *_: struct.pack('<4sII', b'glTF', 2, 12)
    assert client.post(f'/api/cases/{case}/figure/reconstruct', json={}).status_code == 502
    assert client.get(f'/api/cases/{case}/figure/reconstruction').json()['id'] == first['id']


def test_reconstruction_checks_source_and_mesh_case_ownership(client, setup, login):
    case, source, _ = setup
    other = client.post('/api/cases', json={'title': 'Other'}).json()['id']
    assert client.post(f'/api/cases/{other}/figure/reconstruct', json={'body_id': source['id']}).status_code == 404
    model = client.post(f'/api/cases/{case}/figure/reconstruct', json={}).json()
    assert client.get(model['mesh_url'].replace(f'/cases/{case}/', f'/cases/{other}/')).status_code == 404
    login(client, 'officer2', 'officer2pass')
    assert client.get(model['mesh_url']).status_code == 403
    assert client.post(f'/api/cases/{case}/figure/reconstruct', json={}).status_code == 403


def test_reconstruction_opens_exact_saved_mesh_in_blender(client, app, setup):
    case, _, _ = setup
    model = client.post(f'/api/cases/{case}/figure/reconstruct', json={}).json()
    imported = []

    class Blender:
        def import_glb(self, mesh):
            imported.append(mesh)

    app.state.figure_worker = Blender()
    response = client.post(f'/api/cases/{case}/figure/reconstructions/{model["id"]}/blender')
    assert response.status_code == 200
    assert imported == [GLB]
