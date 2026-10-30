from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.db.models import User
from app.schemas.auth import RegisterRequest, UserResponse
from app.security import password_hasher


router = APIRouter(prefix="/auth", tags=["Authentication"])


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
