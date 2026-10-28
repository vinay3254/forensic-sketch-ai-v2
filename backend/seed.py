from sqlmodel import Session, select

from backend.auth.security import hash_password
from backend.models import User

DEMO_USERS = [
    ("officer1", "officer1pass", "officer"),
    ("officer2", "officer2pass", "officer"),
    ("admin", "adminpass", "admin"),
]


def seed_users(session: Session) -> None:
    for username, password, role in DEMO_USERS:
        if not session.exec(select(User).where(User.username == username)).first():
            session.add(User(username=username, password_hash=hash_password(password), role=role))
    session.commit()
