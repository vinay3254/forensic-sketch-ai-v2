"""Vision LLM drafts Blender Python; a filesystem-isolated Blender builds its artifacts."""

import ast
import base64
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import textwrap

import openai
from PIL import Image
from pydantic import BaseModel, Field

from backend.ai.client import LiveAIClient, extract_json
from backend.errors import AppError


SYSTEM = """You are a Blender 5.2 Python modeling artist. Return only JSON:
{"summary":"honest fidelity description", "code":"complete executable bpy Python"}.
Model a full-body geometric study from the reference and instructions. Likeness is approximate.
Use only bpy, bmesh, math, mathutils and random. No filesystem reads, network, subprocess, exec/eval,
imported assets, images, textures, image planes or projection. Model actual editable geometry.
Work in a new factory-startup scene. Coordinates: meters, z up, feet z=0, front -y.
Match supplied height, body proportions, face, hair/beard and clothing. Include modeled eyes,
lids, nose, lips, cheeks, jaw, ears, brows, fingers, shoes, cuffs, seams, collar/hood and pockets.
Prefer connected profile/ring meshes, lofts, curves and bevels over visible disconnected balls.
Use matte materials. Keep below 500000 evaluated vertices and subdivision level 2.
Write files ONLY to the supplied output paths. Export selected PERSON meshes only as GLB,
with export_apply=True and no camera/lights. Save complete scene as BLEND. Render 600x900 PNG
using CYCLES, CPU device, 8 samples and soft studio lights; front three-quarter orthographic camera.
Keep construction/rendering below two minutes and code around 200-350 lines.
"""


class BlenderDraft(BaseModel):
    code: str = Field(min_length=1, max_length=64000)
    summary: str = Field(default='', max_length=2000)


def validate_script(code: str) -> None:
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(n.name not in {'bpy', 'bmesh', 'math', 'mathutils', 'random'} for n in node.names):
                raise ValueError('unsupported import')
            if isinstance(node, ast.ImportFrom) and (node.level or node.module not in {'bpy', 'bmesh', 'math', 'mathutils', 'random'}):
                raise ValueError('unsupported import')
            if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
                raise ValueError('introspection is not a modeling operation')
            if isinstance(node, ast.Name) and node.id.startswith('__') and node.id != '__name__':
                raise ValueError('unsupported name')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
                'open', 'eval', 'exec', 'compile', '__import__', 'globals', 'locals', 'vars',
                'getattr', 'setattr', 'delattr', 'input', 'breakpoint', 'help',
            }:
                raise ValueError('unsupported Python operation')
    except (SyntaxError, ValueError) as error:
        raise AppError('INVALID_BLENDER_SCRIPT', f'The LLM returned unsupported modeling code: {error}. Try another prompt.', 422)


def generate_draft(settings, image: bytes, facts: dict, prompt: str, targets=None) -> BlenderDraft:
    image_file = Image.open(io.BytesIO(image)).convert('RGB')
    image_file.thumbnail((1024, 1536))
    encoded = io.BytesIO()
    image_file.save(encoded, format='JPEG', quality=90)
    targets = targets or {'glb': '/work/model.glb', 'blend': '/work/model.blend', 'preview': '/work/preview.png'}
    client = LiveAIClient(settings)
    kw = dict(model=settings.llm_blender_model or settings.llm_chat_model, timeout=180,
              messages=[{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': [
                  {'type': 'text', 'text': prompt + '\nFacts: ' + json.dumps(facts) + '\nOutput paths: ' + json.dumps(targets)},
                  {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(encoded.getvalue()).decode()}}
              ]}])
    for attempt in range(2):
        try:
            response = client._call(client.client.chat.completions.create, raw_bad_request=True,
                                    response_format={'type': 'json_object'}, **kw)
        except openai.BadRequestError:
            response = client._call(client.client.chat.completions.create, **kw)
        reply = ''
        try:
            reply = response.choices[0].message.content or ''
            draft = BlenderDraft.model_validate(extract_json(reply))
            draft.code = textwrap.dedent(draft.code).strip() + '\n'
            validate_script(draft.code)
            return draft
        except (ValueError, IndexError, AttributeError, TypeError, AppError) as error:
            if attempt:
                if isinstance(error, AppError):
                    raise
                raise AppError('AI_PARSE_FAILED', 'The coding model returned no usable Blender script. Try again.', 422)
            kw['messages'].extend([
                {'role': 'assistant', 'content': reply[:70000]},
                {'role': 'user', 'content': f'The draft failed validation: {error}. Fix the Python syntax and indentation, use only supported imports, and return the complete corrected JSON object with code and summary.'},
            ])


class LiveBlenderBuilder:
    def __init__(self, settings):
        self.settings = settings

    def draft(self, image, facts, prompt):
        return generate_draft(self.settings, image, facts, prompt)

    def build(self, draft: BlenderDraft, directory: Path):
        validate_script(draft.code)
        binary = shutil.which(self.settings.blender_bin)
        bwrap, prlimit = shutil.which('bwrap'), shutil.which('prlimit')
        if not binary or not bwrap or not prlimit:
            raise AppError('BLENDER_OFF', 'Local Blender builder needs Blender, bubblewrap and prlimit installed.', 503)
        binary = Path(binary).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'draft.py').write_text(draft.code)
        command = [prlimit, '--cpu=180', '--as=8589934592', '--fsize=134217728', '--',
                   bwrap, '--unshare-all', '--die-with-parent', '--new-session', '--cap-drop', 'ALL', '--clearenv',
                   '--ro-bind', '/usr', '/usr', '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib', '/lib64',
                   '--ro-bind', str(binary.parent), '/opt/blender', '--bind', str(directory.resolve()), '/work',
                   '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', '/work',
                   '--setenv', 'HOME', '/tmp', '--setenv', 'PATH', '/usr/bin',
                   '--setenv', 'OMP_NUM_THREADS', '2', '--setenv', 'OPENBLAS_NUM_THREADS', '2',
                   '--', '/opt/blender/' + binary.name, '--background', '--factory-startup', '-t', '2',
                   '--python-exit-code', '1', '--python', '/work/draft.py']
        with (directory / 'build.log').open('wb') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                code = process.wait(timeout=150)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise AppError('BLENDER_TIMEOUT', 'Blender build timed out. Try a simpler model description.', 504)
        if code or not (directory / 'model.glb').is_file() or not (directory / 'model.blend').is_file():
            raise AppError('BLENDER_BUILD_FAILED', 'Blender could not build this script. Try a simpler model description.', 422)
        if any(path.is_symlink() for path in (directory / 'model.glb', directory / 'model.blend', directory / 'draft.py')):
            raise AppError('BLENDER_BUILD_FAILED', 'Blender returned invalid artifact files.', 422)
