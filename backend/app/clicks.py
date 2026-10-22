import logging

from .database import SessionLocal
from .models import Click
from .utils import detect_device, referrer_host

log = logging.getLogger(__name__)


def record_click(link_id: int, user_agent: str | None, referer: str | None):
    """Runs after the redirect response is sent. Opens its OWN session:
    the request's session is closed by then. (Never use SessionLocal() as a default argument -
    it would be created once at import time and shared by every call.)"""
    db = SessionLocal()
    try:
        db.add(Click(
            link_id=link_id,
            user_agent=(user_agent or "")[:512],
            referrer=referrer_host(referer)[:255],
            device=detect_device(user_agent),
        ))
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Failed to record click for link %s", link_id)
    finally:
        db.close()
