import secrets
import string
from datetime import datetime, timezone
from urllib.parse import urlparse

ALPHABET = string.ascii_letters + string.digits  # base62


def generate_code(length: int = 7) -> str:
    """Random base62 code. 62^7 = 3.5 trillion combos and it isn't guessable
    (a counter-based code like base62(id) lets anyone walk through every link)."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def detect_device(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    if any(b in ua for b in ("bot", "crawler", "spider", "preview")):
        return "bot"
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if any(m in ua for m in ("mobi", "android", "iphone")):
        return "mobile"
    return "desktop"


def referrer_host(referer: str | None) -> str:
    if not referer:
        return "direct"
    return urlparse(referer).netloc or "direct"
