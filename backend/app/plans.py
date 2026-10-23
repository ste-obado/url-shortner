from datetime import datetime, timezone

from .models import User
from .utils import as_utc

PLAN_DAYS = 30

# Prices are in KES. link_limit None = unlimited.
PLANS = {
    "free": {"name": "Free", "price": 0, "link_limit": 5},
    "pro": {"name": "Pro", "price": 500, "link_limit": 100},
    "enterprise": {"name": "Enterprise", "price": 1000, "link_limit": None},
}
RANK = {"free": 0, "pro": 1, "enterprise": 2}


def effective_plan(user: User, now: datetime | None = None) -> str:
    """The plan the user actually gets right now. An expired paid plan counts as free."""
    now = now or datetime.now(timezone.utc)
    expires = as_utc(user.plan_expires_at)
    if user.plan in PLANS and user.plan != "free" and expires and expires > now:
        return user.plan
    return "free"
