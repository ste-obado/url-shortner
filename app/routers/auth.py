from database import  get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter,Depends,HTTPException,status
from schema import register,Userlogin
#from protection import get_current_user
from models import User
from  auth import hash_password,verify_password,create_access_token
from redis_cache import redis_client

router=APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

NUMBER_OF_ATTEMPTS=5
TIME_WINDOW=60

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
    rate_key=f"login_attemps:{user_login.email}"
    attempts = redis_client.get(rate_key)
    if attempts and int(attempts) >= NUMBER_OF_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in a minute."
        )
    existing_user = db.query(User).filter(User.email == user_login.email).first()
  
    if not existing_user or not verify_password(user_login.password, existing_user.password):
    # Failed attempt — increment the counter
        new_count = redis_client.incr(rate_key)
        if new_count == 1:
              redis_client.expire(rate_key, TIME_WINDOW)  # only set TTL on the first failure,more than 5 failures in that ttl window "too many requests"
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Successful login — clear any failed attempt count
    redis_client.delete(rate_key)
    access_token=create_access_token(data={"sub": existing_user.email})
    return {"access_token": access_token, "token_type": "bearer"}
   
