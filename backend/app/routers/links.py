from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..cache import cache
from ..config import settings
from ..database import get_db
from ..models import Click, Link, User
from ..ratelimit import rate_limit_user
from ..schemas import LinkCreate, LinkOut, LinkUpdate
from ..security import get_current_user
from ..utils import as_utc, generate_code

router = APIRouter(prefix="/api/links", tags=["Links"])


def to_out(link: Link, clicks: int = 0) -> LinkOut:
    return LinkOut(
        id=link.id, code=link.code, short_url=f"{settings.BASE_URL.rstrip('/')}/{link.code}",
        original_url=link.original_url, title=link.title, is_active=link.is_active,
        expires_at=link.expires_at, created_at=link.created_at, total_clicks=clicks,
    )


def get_owned_link(code: str, db: Session, user: User) -> Link:
    link = db.query(Link).filter(Link.code == code).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    if link.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This link belongs to someone else")
    return link


@router.post("", response_model=LinkOut, status_code=201, dependencies=[Depends(rate_limit_user(10, 60, "shorten"))])
def create_link(data: LinkCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    expires_at = as_utc(data.expires_at)
    if data.custom_code and db.query(Link).filter(Link.code == data.custom_code).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That code is taken, try another")

    for _ in range(5):  # random codes can (very rarely) collide: retry
        code = data.custom_code or generate_code()
        link = Link(owner_id=user.id, original_url=str(data.original_url), code=code,
                    title=data.title, expires_at=expires_at)
        db.add(link)
        try:
            db.commit()
            db.refresh(link)
            return to_out(link)
        except IntegrityError:
            db.rollback()
            if data.custom_code:
                raise HTTPException(status.HTTP_409_CONFLICT, "That code is taken, try another")
    raise HTTPException(500, "Could not generate a unique code, please retry")


@router.get("", response_model=list[LinkOut])
def list_links(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    links = db.query(Link).filter(Link.owner_id == user.id).order_by(Link.created_at.desc(), Link.id.desc()).all()
    counts = dict(
        db.query(Click.link_id, func.count(Click.id))
        .join(Link, Link.id == Click.link_id).filter(Link.owner_id == user.id)
        .group_by(Click.link_id).all()
    )
    return [to_out(l, counts.get(l.id, 0)) for l in links]


@router.patch("/{code}", response_model=LinkOut)
def update_link(code: str, data: LinkUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = get_owned_link(code, db, user)
    changes = data.model_dump(exclude_unset=True)
    if "expires_at" in changes:
        changes["expires_at"] = as_utc(changes["expires_at"])
    for field, value in changes.items():
        setattr(link, field, value)
    db.commit()
    db.refresh(link)
    cache.delete(f"code:{code}")  # redirects must see the change immediately
    return to_out(link)


@router.delete("/{code}", status_code=204)
def delete_link(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = get_owned_link(code, db, user)
    db.delete(link)
    db.commit()
    cache.delete(f"code:{code}")
