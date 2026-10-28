import os

import pytest

from backend.tests.test_body_model import GLB
from backend.errors import AppError


@pytest.fixture
def setup(client, app, seed_users, login):
    login(client, 'officer1', 'officer1pass')
    case = client.post('/api/cases', json={'title': 'Blender modeling'}).json()['id']
    body = client.post(f'/api/cases/{case}/body').json()
    calls = []

    class Builder:
        def draft(self, image, facts, prompt):
            from backend.figure.modeling import BlenderDraft
            calls.append(('draft', image, facts, prompt))
            return BlenderDraft(code='import bpy\n', summary='Modeled study')

        def build(self, draft, directory):
            calls.append(('build', draft.code))
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'draft.py').write_text(draft.code)
            (directory / 'model.glb').write_bytes(GLB)
            (directory / 'model.blend').write_bytes(b'BLENDER-test')

    class Desktop:
        def import_glb(self, data):
            calls.append(('desktop', data))

    app.state.blender_builder = Builder()
    app.state.figure_worker = Desktop()
    return case, body, calls


def test_app_prompt_builds_saved_mesh_and_delivers_to_blender(client, setup):
    case, body, calls = setup
    image = client.get(body['image_url']).content
    response = client.post(f'/api/cases/{case}/figure/blender-jobs', json={'body_id': body['id'], 'prompt': 'Model a larger nose and hoodie'})
    assert response.status_code == 202, response.text
    job = client.get(f'/api/cases/{case}/figure/blender-jobs/latest').json()
    assert job['status'] == 'complete' and job['desktop_opened']
    assert calls[0][1] == image and calls[0][2]['height_cm'] == 172
    assert calls[0][3] == 'Model a larger nose and hoodie'
    assert calls[-1] == ('desktop', GLB)
    model = client.get(f'/api/cases/{case}/figure/reconstruction').json()
    assert model['id'] == job['model_id'] and model['engine'] == 'LLM Blender modeling'
    assert client.get(model['mesh_url']).content == GLB
    assert client.get(model['blend_url']).content == b'BLENDER-test'
    assert client.get(model['script_url']).text == 'import bpy\n'


def test_generation_failure_keeps_previous_model(client, app, setup):
    case, body, _ = setup
    endpoint = f'/api/cases/{case}/figure/blender-jobs'
    client.post(endpoint, json={'body_id': body['id'], 'prompt': 'First'})
    previous = client.get(f'/api/cases/{case}/figure/reconstruction').json()
    def fail(*_):
        raise AppError('AI_UNAVAILABLE', 'Coding model unavailable.', 503)
    app.state.blender_builder.draft = fail
    client.post(endpoint, json={'body_id': body['id'], 'prompt': 'Second'})
    job = client.get(endpoint + '/latest').json()
    assert job['status'] == 'failed' and job['error'] == 'Coding model unavailable.'
    assert client.get(f'/api/cases/{case}/figure/reconstruction').json()['id'] == previous['id']


def test_closed_desktop_keeps_completed_model(client, app, setup):
    case, body, _ = setup
    app.state.figure_worker = None
    client.post(f'/api/cases/{case}/figure/blender-jobs', json={'body_id': body['id'], 'prompt': 'Build'})
    job = client.get(f'/api/cases/{case}/figure/blender-jobs/latest').json()
    assert job['status'] == 'complete' and not job['desktop_opened'] and job['desktop_error']
    assert client.get(f'/api/cases/{case}/figure/reconstruction').json()['id'] == job['model_id']


def test_modeling_source_job_and_artifacts_enforce_case_access(client, setup, login):
    case, body, _ = setup
    other = client.post('/api/cases', json={'title': 'Other'}).json()['id']
    assert client.post(f'/api/cases/{other}/figure/blender-jobs', json={'body_id': body['id'], 'prompt': 'Build'}).status_code == 404
    client.post(f'/api/cases/{case}/figure/blender-jobs', json={'body_id': body['id'], 'prompt': 'Build'})
    model = client.get(f'/api/cases/{case}/figure/reconstruction').json()
    login(client, 'officer2', 'officer2pass')
    assert client.get(f'/api/cases/{case}/figure/blender-jobs/latest').status_code == 403
    assert client.post(f'/api/cases/{case}/figure/blender-jobs', json={'prompt': 'Build'}).status_code == 403
    assert client.get(model['script_url']).status_code == 403


def test_rejects_non_modeling_python_before_blender():
    from backend.figure.modeling import validate_script
    with pytest.raises(AppError):
        validate_script('import os\nos.system("curl example.com")')
    with pytest.raises(AppError):
        validate_script('import bpy\nexec("print(1)")')
    validate_script('import bpy, math\nfrom mathutils import Vector\nbpy.ops.object.select_all(action="SELECT")')


def test_interrupted_job_is_recoverable_after_restart(client, app, setup):
    from sqlmodel import Session
    from backend.models import BlenderJob
    case, body, _ = setup
    with Session(app.state.engine) as session:
        session.add(BlenderJob(case_id=case, body_id=body['id'], prompt='Interrupted', worker_pid=99999999, created_by=1))
        session.commit()
    response = client.get(f'/api/cases/{case}/figure/blender-jobs/latest')
    assert response.json()['status'] == 'failed'
    assert 'restart' in response.json()['error']
    assert client.post(f'/api/cases/{case}/figure/blender-jobs', json={'prompt': 'Retry'}).status_code == 202


def test_active_job_rejects_duplicate_submission(client, app, setup):
    from sqlmodel import Session
    from backend.models import BlenderJob
    from backend.figure.modeling_routes import process_token
    case, body, _ = setup
    with Session(app.state.engine) as session:
        session.add(BlenderJob(case_id=case, body_id=body['id'], prompt='Active', worker_pid=os.getpid(), worker_token=process_token(os.getpid()), created_by=1))
        session.commit()
    assert client.post(f'/api/cases/{case}/figure/blender-jobs', json={'prompt': 'Duplicate'}).status_code == 409


def test_invalid_geometry_does_not_publish_model(client, app, setup):
    case, body, _ = setup
    original = app.state.blender_builder.build
    def invalid(draft, directory):
        original(draft, directory)
        (directory / 'model.glb').write_bytes(b'not geometry')
    app.state.blender_builder.build = invalid
    client.post(f'/api/cases/{case}/figure/blender-jobs', json={'prompt': 'Build'})
    assert client.get(f'/api/cases/{case}/figure/blender-jobs/latest').json()['status'] == 'failed'
    assert client.get(f'/api/cases/{case}/figure/reconstruction').json() is None


def test_reused_pid_cannot_keep_a_stale_job_active(client, app, setup):
    from sqlmodel import Session
    from backend.models import BlenderJob
    case, body, _ = setup
    with Session(app.state.engine) as session:
        session.add(BlenderJob(case_id=case, body_id=body['id'], prompt='Old process', worker_pid=os.getpid(), worker_token='different-process-start', created_by=1))
        session.commit()
    assert client.get(f'/api/cases/{case}/figure/blender-jobs/latest').json()['status'] == 'failed'


def test_database_atomically_rejects_two_active_jobs_for_one_case(client, app, setup):
    from sqlmodel import Session
    from sqlalchemy.exc import IntegrityError
    from backend.models import BlenderJob
    case, body, _ = setup
    with Session(app.state.engine) as session:
        session.add(BlenderJob(case_id=case, body_id=body['id'], prompt='First', worker_pid=os.getpid(), created_by=1))
        session.commit()
        session.add(BlenderJob(case_id=case, body_id=body['id'], prompt='Second', worker_pid=os.getpid(), created_by=1))
        with pytest.raises(IntegrityError):
            session.commit()


def test_invalid_llm_python_gets_one_correction_attempt(settings, monkeypatch):
    import io
    from PIL import Image
    from types import SimpleNamespace
    from backend.figure.modeling import generate_draft
    import json
    replies = [json.dumps({'code': 'import bpy\n  bpy.ops.object.select_all(action="SELECT")', 'summary': 'bad'}),
               json.dumps({'code': 'import bpy\nbpy.ops.object.select_all(action="SELECT")', 'summary': 'fixed'})]
    calls = []
    class AI:
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=None)))
        def _call(self, _, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=replies.pop(0)))])
    monkeypatch.setattr('backend.figure.modeling.LiveAIClient', lambda _: AI())
    image = io.BytesIO(); Image.new('RGB', (2, 2)).save(image, format='PNG')
    draft = generate_draft(settings, image.getvalue(), {}, 'Build a person')
    assert draft.summary == 'fixed' and len(calls) == 2
