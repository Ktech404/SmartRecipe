from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_session
from app.db.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.security import create_access_token, dummy_hash, password_hasher, verify_password


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=UserResponse)
def profile(user: User = Depends(get_current_user)):
    return user


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    user = User(username=payload.username, email=str(payload.email),
                password_hash=password_hasher.hash(payload.password.get_secret_value()))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, "Username or email already registered") from None
        raise HTTPException(500, "Registration could not be completed") from None
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.username == payload.username))
    valid = verify_password(payload.password.get_secret_value(),
                            user.password_hash if user else dummy_hash)
    if not user or not valid:
        raise HTTPException(401, "Invalid username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    token, lifetime = create_access_token(user.user_id)
    return TokenResponse(access_token=token, expires_in=lifetime)
