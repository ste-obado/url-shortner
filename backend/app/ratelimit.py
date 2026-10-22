from fastapi import Depends, HTTPException, Request

from .cache import cache
from .models import User
from .security import get_current_user


def _check(key: str, limit: int, window: int):
    allowed, retry_after = cache.window_hit(key, limit, window)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Slow down a little.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit_user(limit: int = 10, window: int = 60, name: str = "api"):
    """Limit per logged-in user."""

    def dependency(user: User = Depends(get_current_user)):
        _check(f"rate:{name}:u{user.id}", limit, window)

    return dependency


def rate_limit_ip(limit: int = 20, window: int = 60, name: str = "ip"):
    """Limit per client IP (for routes without a logged-in user)."""

    def dependency(request: Request):
        ip = request.client.host if request.client else "unknown"
        _check(f"rate:{name}:{ip}", limit, window)

    return dependency
