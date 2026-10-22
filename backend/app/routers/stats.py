from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Click, User
from ..schemas import DayCount, NameCount, StatsOut
from ..security import get_current_user
from .links import get_owned_link

router = APIRouter(prefix="/api/stats", tags=["Statistics"])


@router.get("/{code}", response_model=StatsOut)
def get_stats(code: str, days: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = get_owned_link(code, db, user)  # ownership check FIRST, before any data is returned
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)

    total = db.query(func.count(Click.id)).filter(Click.link_id == link.id).scalar() or 0

    per_day = dict(
        (str(d), n) for d, n in db.query(func.date(Click.clicked_at), func.count(Click.id))
        .filter(Click.link_id == link.id, Click.clicked_at >= since)
        .group_by(func.date(Click.clicked_at)).all()
    )
    start = since.date()
    series = [DayCount(date=str(start + timedelta(days=i)), clicks=per_day.get(str(start + timedelta(days=i)), 0))
              for i in range(days)]  # include zero-click days so charts have no gaps

    def breakdown(column, limit=8):
        rows = (db.query(column, func.count(Click.id)).filter(Click.link_id == link.id)
                .group_by(column).order_by(func.count(Click.id).desc()).limit(limit).all())
        return [NameCount(name=n or "unknown", clicks=c) for n, c in rows]

    return StatsOut(code=code, total_clicks=total, clicks_per_day=series,
                    devices=breakdown(Click.device), referrers=breakdown(Click.referrer))
