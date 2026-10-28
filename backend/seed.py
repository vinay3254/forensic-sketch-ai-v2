from sqlmodel import Session, select

from backend.ai.client import AIClient
from backend.auth.security import hash_password
from backend.config import Settings
from backend.models import Case, User

DEMO_USERS = [
    ("officer1", "officer1pass", "officer"),
    ("officer2", "officer2pass", "officer"),
    ("admin", "adminpass", "admin"),
    ("vinay3254", "7767", "officer"),
]
DEMO_CASE_TITLE = "Chain snatching, Yelahanka"
DEMO_DESCRIPTION = (
    "Man, around 30 to 35 years, medium brown skin, square face with a strong jaw, small deep-set dark eyes, "
    "thick straight eyebrows, broad nose, thin lips, short black hair receding at the front, light stubble, "
    "small scar on the left cheek."
)
DEMO_REFINEMENT = "Make the jaw a bit wider and the eyebrows thicker."


def seed_users(session: Session) -> None:
    for username, password, role in DEMO_USERS:
        if not session.exec(select(User).where(User.username == username)).first():
            session.add(User(username=username, password_hash=hash_password(password), role=role))
    session.commit()


def seed_demo(session: Session, settings: Settings, ai: AIClient) -> None:
    from backend.cases.routes import next_case_number
    from backend.face.service import generate_face, refine_face

    seed_users(session)
    if session.exec(select(Case).where(Case.title == DEMO_CASE_TITLE)).first():
        return
    officer = session.exec(select(User).where(User.username == "officer1")).one()
    case = Case(case_number=next_case_number(session), title=DEMO_CASE_TITLE, created_by=officer.id)
    session.add(case)
    session.commit()
    session.refresh(case)
    generate_face(session, ai, settings, case, officer, DEMO_DESCRIPTION)
    refine_face(session, ai, settings, case, officer, DEMO_REFINEMENT)


def main() -> None:
    from backend.ai.client import LiveAIClient
    from backend.ai.mock import MockAIClient
    from backend.config import get_settings
    from backend.db import init_db, make_engine

    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    ai = MockAIClient() if settings.ai_mock else LiveAIClient(settings)
    with Session(engine, expire_on_commit=False) as session:
        seed_demo(session, settings, ai)
    print("Seeded demo users (officer1, officer2, admin, vinay3254) and demo case.")


if __name__ == "__main__":
    main()
