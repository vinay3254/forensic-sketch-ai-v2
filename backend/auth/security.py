from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from backend.config import Settings
from backend.errors import AppError


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user_id: int, role: str, settings: Settings) -> str:
    exp = datetime.now(UTC) + timedelta(hours=settings.jwt_expiry_hours)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise AppError("UNAUTHENTICATED", "Session expired or invalid. Please log in again.", 401)
