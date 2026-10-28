import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from backend.config import Settings
from backend.errors import AppError


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


# checked when the username does not exist, so both paths take one bcrypt round
DUMMY_HASH = hash_password("dummy-password-for-timing")


def create_token(user_id: int, role: str, settings: Settings) -> str:
    exp = datetime.now(UTC) + timedelta(hours=settings.jwt_expiry_hours)
    claims = {"sub": str(user_id), "role": role, "exp": exp, "jti": uuid.uuid4().hex}
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise AppError("UNAUTHENTICATED", "Session expired or invalid. Please log in again.", 401)
