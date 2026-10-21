"""Password hashing (bcrypt) and JWT access tokens (HS256)."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, role: str, secret: str, expire_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> int | None:
    """Return the user id, or None if the token is invalid, tampered with or expired."""
    try:
        # Pinning algorithms stops "alg: none" and algorithm-confusion attacks.
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
