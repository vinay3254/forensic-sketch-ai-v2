from sqlmodel import Session, select

from backend.ai.mock import MockAIClient
from backend.models import Case, FaceVersion
from backend.seed import seed_demo


def test_seed_demo_is_idempotent(app, client, settings):
    with Session(app.state.engine, expire_on_commit=False) as s:
        seed_demo(s, settings, MockAIClient())
        seed_demo(s, settings, MockAIClient())
        cases = s.exec(select(Case)).all()
        assert [c.title for c in cases] == ["Chain snatching, Yelahanka"]
        assert len(s.exec(select(FaceVersion)).all()) == 2
