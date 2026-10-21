#create a key in redis 
from redis_cache import redis_client
from fastapi import HTTPException
from models import User


#sliding window ratelimiter



import math
import time
import uuid

from fastapi import Depends, HTTPException
from protection  import get_current_user  # your JWT dependency, returns the user


def rate_limit(limit: int = 10, window: int = 60):
    async def dependency(user=Depends(get_current_user)):
        key = f"rate:{user.id}"
        now = time.time()
        member = f"{now}-{uuid.uuid4()}"  # unique, so two requests never overwrite each other

        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)  # 1. drop entries older than the window
        pipe.zadd(key, {member: now})                # 2. record this request
        pipe.zcard(key)                              # 3. count requests in the window
        pipe.expire(key, window)                     # 4. auto-clean idle keys
        _, _, count, _ = await pipe.execute()

        if count > limit:
            await redis_client.zrem(key, member)  # rejected requests don't count
            oldest = await redis_client.zrange(key, 0, 0, withscores=True)
            retry_after = math.ceil(oldest[0][1] + window - now) if oldest else window
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

    return dependency