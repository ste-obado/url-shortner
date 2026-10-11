from database import  get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter,Depends,HTTPException,status
from schema import register,Userlogin
#from protection import get_current_user
from models import User
from  auth import hash_password,verify_password,create_access_token
from ratelimiter import rate_limiting


router=APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)
@router.post("register")
def register_user(user: register, db: Session = Depends(get_db)):
    # Check if user already exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Create new user
    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password)  # Hash the password before saving
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("login")
def auth(user_login:Userlogin,db:Session=Depends(get_db)):
    return rate_limiting(user_login, db)
   
