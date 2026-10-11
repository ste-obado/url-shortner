import redis

redis_client = redis.Redis(host='localhost', port=6379, decode_response=True)