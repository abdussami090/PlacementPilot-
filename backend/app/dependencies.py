"""Shared authentication and role dependencies for API routes."""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import oauth2_scheme, verify_token


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    email = verify_token(token)
    if not email:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User associated with token was not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_student(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(token, db)
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can access this endpoint")
    return user


def admin_required(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(token, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
