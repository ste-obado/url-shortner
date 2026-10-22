import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..cache import cache
from ..clicks import record_click
from ..config import settings
from ..database import get_db
from ..models import Link
from ..utils import as_utc

router = APIRouter(tags=["Redirect"])


@router.get("/{code}", include_in_schema=False)
def redirect(code: str, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    key = f"code:{code}"
    cached = cache.get(key)

    if cached:
        data = json.loads(cached)  # {"id": 1, "url": "https://..."}
        link_id, url = data["id"], data["url"]
    else:
        link = db.query(Link).filter(Link.code == code).first()
        if link is None or not link.is_active:
            raise HTTPException(404, "Short link not found")
        expires = as_utc(link.expires_at)
        now = datetime.now(timezone.utc)
        if expires and expires <= now:
            raise HTTPException(410, "This link has expired")
        link_id, url = link.id, link.original_url
        ttl = settings.CACHE_TTL_SECONDS
        if expires:
            ttl = max(1, min(ttl, int((expires - now).total_seconds())))  # never cache past expiry
        cache.set(key, json.dumps({"id": link_id, "url": url}), ex=ttl)

    # Count the click on BOTH cache hits and misses, after the response is sent.
    background.add_task(record_click, link_id, request.headers.get("user-agent"), request.headers.get("referer"))
    return RedirectResponse(url, status_code=307)
