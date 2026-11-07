from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from datetime import datetime, timedelta, timezone
import os
import secrets

import jwt


password_hasher = PasswordHash.recommended()
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


def token_settings() -> tuple[str, int]:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret.encode()) < 32 or secret.startswith("replace-"):
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 bytes of random secret data")
    try:
        minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        if not 1 <= minutes <= 1440:
            raise ValueError
    except ValueError:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440") from None
    return secret, minutes * 60


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return password_hasher.verify(password, stored_hash)
    except UnknownHashError:
        return False


def create_access_token(user_id: int) -> tuple[str, int]:
    secret, lifetime = token_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(user_id), "iat": now,
                        "exp": now + timedelta(seconds=lifetime),
                        "iss": "smartrecipe", "aud": "smartrecipe-api",
                        "token_type": "access"}, secret, algorithm="HS256")
    return token, lifetime
