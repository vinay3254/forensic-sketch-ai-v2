"""Copy one user's cases from another TRACE database (and its storage folder) into this one.

Usage: uv run python -m scripts.import_cases OLD_DB OLD_STORAGE USERNAME
Cases get new case numbers here; sketches, versions, chat, details, interviews, variants and
figures come along, image files are copied, and each import is written to the audit chain.
Back up app.db first.
"""

import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

from sqlmodel import Session, create_engine, select

from backend.audit.logger import record
from backend.cases.routes import next_case_number
from backend.config import get_settings
from backend.db import init_db, make_engine
from backend.face.service import image_file
from backend.models import BodyFigure, Case, ChatMessage, FaceVersion, Head3D, Interview, User, Variant

NO_REQUEST = SimpleNamespace(client=None, headers={})  # audit rows written by this script, not a web request


def main() -> None:
    old_db, old_storage, username = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    settings = get_settings()
    new_engine = make_engine(settings.database_url)
    init_db(new_engine)
    old = Session(create_engine(f"sqlite:///{old_db}"))
    new = Session(new_engine, expire_on_commit=False)

    users = {u.id: u.username for u in old.exec(select(User)).all()}
    here = {u.username: u for u in new.exec(select(User)).all()}
    uid = lambda old_id: here[users[old_id]].id if old_id is not None and users.get(old_id) in here else None  # noqa: E731
    me = here[username]

    def copy_file(rel: str | None, case_id: int) -> str | None:
        if not rel:
            return None
        src = old_storage / rel
        if not src.is_file():
            print(f"  missing file, skipped: {rel}")
            return None
        dest_rel = f"cases/{case_id}/{Path(rel).name}"
        dest = image_file(settings, dest_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest_rel

    old_me = next(i for i, n in users.items() if n == username)
    for oc in old.exec(select(Case).where(Case.created_by == old_me).order_by(Case.id)).all():
        c = Case(**oc.model_dump(exclude={"id", "case_number", "created_by"}), case_number=next_case_number(new), created_by=me.id)
        new.add(c)
        new.commit()

        interviews = {}
        for oi in old.exec(select(Interview).where(Interview.case_id == oc.id).order_by(Interview.id)).all():
            iv = Interview(**oi.model_dump(exclude={"id", "case_id", "created_by", "confirmed_by"}),
                           case_id=c.id, created_by=uid(oi.created_by) or me.id, confirmed_by=uid(oi.confirmed_by))
            new.add(iv)
            new.commit()
            interviews[oi.id] = iv.id

        versions = {}
        for ov in old.exec(select(FaceVersion).where(FaceVersion.case_id == oc.id).order_by(FaceVersion.version_no)).all():
            v = FaceVersion(
                **ov.model_dump(exclude={"id", "case_id", "parent_id", "interview_id", "image_path", "photo_path", "created_by"}),
                case_id=c.id, parent_id=versions.get(ov.parent_id), interview_id=interviews.get(ov.interview_id),
                image_path=copy_file(ov.image_path, c.id) or "", photo_path=copy_file(ov.photo_path, c.id),
                created_by=uid(ov.created_by) or me.id,
            )
            new.add(v)
            new.commit()
            versions[ov.id] = v.id

        for m in old.exec(select(ChatMessage).where(ChatMessage.case_id == oc.id).order_by(ChatMessage.id)).all():
            new.add(ChatMessage(**m.model_dump(exclude={"id", "case_id", "version_id"}), case_id=c.id, version_id=versions.get(m.version_id)))
        for x in old.exec(select(Variant).where(Variant.case_id == oc.id)).all():
            if (path := copy_file(x.image_path, c.id)) and x.version_id in versions:
                new.add(Variant(**x.model_dump(exclude={"id", "case_id", "version_id", "image_path", "created_by"}),
                                case_id=c.id, version_id=versions[x.version_id], image_path=path, created_by=uid(x.created_by) or me.id))
        for b in old.exec(select(BodyFigure).where(BodyFigure.case_id == oc.id)).all():
            if path := copy_file(b.image_path, c.id):
                new.add(BodyFigure(**b.model_dump(exclude={"id", "case_id", "image_path", "created_by"}),
                                   case_id=c.id, image_path=path, created_by=uid(b.created_by) or me.id))
        for h in old.exec(select(Head3D).where(Head3D.case_id == oc.id)).all():
            if (path := copy_file(h.mesh_path, c.id)) and h.version_id in versions:
                new.add(Head3D(**h.model_dump(exclude={"id", "case_id", "version_id", "mesh_path", "created_by"}),
                               case_id=c.id, version_id=versions[h.version_id], mesh_path=path, created_by=uid(h.created_by) or me.id))
        new.commit()
        record(new, NO_REQUEST, "case_create", me, case_id=c.id,
               detail={"imported_from": oc.case_number, "versions": len(versions), "interviews": len(interviews)})
        print(f"{oc.case_number} -> {c.case_number}  {c.title[:40]!r}: {len(versions)} versions, {len(interviews)} interviews")


if __name__ == "__main__":
    main()
