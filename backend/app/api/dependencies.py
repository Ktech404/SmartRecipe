from collections.abc import Generator

from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.db.session import SessionLocal
from app.db.models import User
from app.security import token_settings


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                     session: Session = Depends(get_session)) -> User:
    denied = HTTPException(401, "Invalid or expired access token",
                           headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise denied
    secret, _ = token_settings()
    try:
        claims = jwt.decode(credentials.credentials, secret, algorithms=["HS256"],
                            issuer="smartrecipe", audience="smartrecipe-api",
                            options={"require": ["sub", "exp", "iat", "iss", "aud", "token_type"]})
        subject = claims["sub"]
        if (claims["token_type"] != "access" or not subject.isascii()
                or not subject.isdecimal() or len(subject) > 19):
            raise denied
        user_id = int(subject)
        if not 0 < user_id <= 9223372036854775807:
            raise denied
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise denied from None
    user = session.get(User, user_id)
    if user is None:
        raise denied
    return user
