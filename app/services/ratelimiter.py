#create a key in redis 
from redis_cache import redis_client
from fastapi import HTTPException
from models import User
from auth import verify_password,create_access_token

#sliding window ratelimiter

def sliding_rawindow():
    