"""Fill the demo criminal-records database from the faces fetched by scripts/fetch_record_faces.py.

  uv run python -m scripts.seed_records      # idempotent: faces already used are skipped
"""

import json

from sqlmodel import Session

from backend.config import get_settings
from backend.db import init_db, make_engine
from backend.records.seed import seed_records


def main() -> None:
    settings = get_settings()
    faces = json.loads((settings.storage_dir / "records" / "faces.json").read_text())
    engine = make_engine(settings.database_url)
    init_db(engine)
    with Session(engine) as s:
        print(f"added {seed_records(s, faces)} fictional people ({len(faces)} faces available)")


if __name__ == "__main__":
    main()
