"""Experimental LLM -> reviewable Blender Python draft. Never executes generated code.

uv run python scripts/draft_blender_model.py --case 6 --model codex/gpt-6.1-sol --output /tmp/trace-llm-blender
Review draft.py before running it in a separate Blender process.
"""

import argparse
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from sqlmodel import Session

from backend.body.routes import latest_body
from backend.config import get_settings
from backend.db import make_engine
from backend.face.service import existing_image_file, latest_version
from backend.figure.routes import current_params
from backend.figure.modeling import generate_draft
from backend.models import Case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=int, required=True, dest='case_id')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prompt', default='Build a detailed geometric study matching this full-body reference. Prioritize modeled face and clothing.')
    parser.add_argument('--model', help='Explicit model route for this trial; does not change product settings')
    args = parser.parse_args()
    settings = get_settings()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with Session(make_engine(settings.database_url)) as session:
        case = session.get(Case, args.case_id)
        if not case:
            raise SystemExit('Case not found')
        source = latest_body(session, case.id)
        if not source:
            raise SystemExit('Draw a full-body reference first')
        params = current_params(session, case)
        version = latest_version(session, case.id)
        facts = {'case_id': case.id, 'body_id': source.id, 'height_cm': params.height_cm,
                 'details': case.details or {}, 'attributes': version.attributes if version else {}}
        image = Image.open(existing_image_file(settings, source.image_path)).convert('RGB')
    encoded = io.BytesIO()
    image.save(encoded, format='PNG')
    targets = {key: str(output / name) for key, name in [('glb', 'model.glb'), ('blend', 'model.blend'), ('preview', 'preview.png')]}
    trial_settings = settings.model_copy(update={'llm_blender_model': args.model or settings.llm_blender_model or settings.llm_chat_model})
    draft = generate_draft(trial_settings, encoded.getvalue(), facts, args.prompt, targets)
    (output / 'draft.py').write_text(draft.code)
    (output / 'draft.json').write_text(json.dumps({'summary': draft.summary, 'facts': facts, 'targets': targets}, indent=2))
    print('Draft:', output / 'draft.py')
    print('Summary:', draft.summary)
    print('Draft not executed. Review Python before running Blender.')


if __name__ == '__main__':
    main()
