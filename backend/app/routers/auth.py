from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..cache import cache
from ..database import get_db
from ..models import User
from ..ratelimit import rate_limit_ip
from ..schemas import RegisterIn, TokenOut, UserOut
from ..security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _token_for(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


def _login(email: str, password: str, db: Session) -> TokenOut:
    email = email.lower()
    fail_key = f"login_fail:{email}"
    attempts = cache.get(fail_key)
    if attempts and int(attempts) >= MAX_FAILED_LOGINS:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        cache.incr(fail_key, LOCKOUT_SECONDS)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")

    cache.delete(fail_key)
    return _token_for(user)


@router.post("/register", response_model=TokenOut, status_code=201,
             dependencies=[Depends(rate_limit_ip(10, 60, "register"))])
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That email is already registered")
    user = User(name=data.name.strip(), email=email, hashed_password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)  # log them in straight away


@router.post("/login", response_model=TokenOut, dependencies=[Depends(rate_limit_ip(20, 60, "login"))])
def login(data: LoginIn, db: Session = Depends(get_db)):
    return _login(data.email, data.password, db)


@router.post("/token", include_in_schema=False)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Form-based login so the 'Authorize' button in /docs works."""
    return _login(form.username, form.password, db)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
