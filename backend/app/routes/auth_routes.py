from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate
from app.security import hash_password, verify_password, create_access_token, verify_token, oauth2_scheme

router = APIRouter()


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    email = str(user.email).strip().lower()
    existing_user = db.query(User).filter(func.lower(User.email) == email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        name=user.name,
        email=email,
        password=hash_password(user.password),
        role="student",
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from exc

    return {"message": "User registered successfully"}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.strip().lower()
    db_user = db.query(User).filter(func.lower(User.email) == email).first()

    # Use one generic response so callers cannot distinguish unknown emails from wrong passwords.
    if not db_user or not verify_password(form_data.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    email = verify_token(token)
    if not email:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User associated with token was not found")

    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
