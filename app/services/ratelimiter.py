#create a key in redis 
from redis_cache import redis_client
from fastapi import HTTPException
from models import User
from auth import verify_password,create_access_token


def rate_limiting(user_login,db):
    rate_key=f"login_attemps:{user_login.email}"
    attempts = redis_client.get(rate_key)
    if attempts and int(attempts) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in a minute."
        )
    existing_user = db.query(User).filter(User.email == user_login.email).first()
  
    if not existing_user or not verify_password(user_login.password, existing_user.password):
    # Failed attempt — increment the counter
        new_count = redis_client.incr(rate_key)
        if new_count == 1:
              redis_client.expire(rate_key, 60)  # only set TTL on the first failure,more than 5 failures in that ttl window "too many requests"
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Successful login — clear any failed attempt count
    redis_client.delete(rate_key)
    access_token=create_access_token(data={"sub": existing_user.email})
    return {"access_token": access_token, "token_type": "bearer"}