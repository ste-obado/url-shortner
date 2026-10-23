import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Link, Payment, User
from ..mpesa import MpesaError, MpesaNotConfigured, get_client, normalize_phone, parse_callback
from ..payments import apply_result, plan_price, reconcile
from ..plans import PLANS, RANK, effective_plan
from ..ratelimit import rate_limit_user
from ..security import get_current_user
from ..utils import as_utc

router = APIRouter(prefix="/api/billing", tags=["Billing"])
log = logging.getLogger(__name__)

PENDING_EXPIRES_AFTER = timedelta(minutes=5)
ACK = {"ResultCode": 0, "ResultDesc": "Accepted"}  # what Safaricom expects back


class CheckoutIn(BaseModel):
    plan: Literal["pro", "enterprise"]  # "free" can't be bought. NOTE: there is no amount field on purpose.
    phone: str

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v):
        return normalize_phone(v)


def payment_out(p: Payment) -> dict:
    return {"id": p.id, "plan": p.plan, "amount": p.amount, "status": p.status,
            "message": p.result_desc, "receipt": p.mpesa_receipt}


@router.get("/plans")
def list_plans():
    return [{"id": k, **v} for k, v in PLANS.items()]


@router.get("/me")
def my_billing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = effective_plan(user)
    used = db.query(func.count(Link.id)).filter(Link.owner_id == user.id).scalar() or 0
    pending = db.query(Payment).filter(Payment.user_id == user.id, Payment.status == "pending").first()
    return {"plan": plan, "plan_name": PLANS[plan]["name"], "link_limit": PLANS[plan]["link_limit"],
            "links_used": used, "expires_at": user.plan_expires_at if plan != "free" else None,
            "pending_payment_id": pending.id if pending else None}


@router.post("/checkout", status_code=202, dependencies=[Depends(rate_limit_user(5, 60, "checkout"))])
def checkout(data: CheckoutIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        client = get_client()
    except MpesaNotConfigured:
        raise HTTPException(503, "Payments are not available right now")

    if RANK[data.plan] < RANK[effective_plan(user)]:
        raise HTTPException(409, f"You already have a higher plan active ({PLANS[effective_plan(user)]['name']})")

    # Old pending attempts: first ask Daraja what really happened (the customer may have paid and our
    # callback got lost), and only then give up on them. This prevents charging someone twice.
    now = datetime.now(timezone.utc)
    stale = db.query(Payment).filter(Payment.user_id == user.id, Payment.status == "pending").all()
    for old in stale:
        if now - as_utc(old.created_at) < PENDING_EXPIRES_AFTER:
            raise HTTPException(409, "A payment is already in progress. Check your phone for the M-Pesa prompt.")
        if old.checkout_request_id:
            db.refresh(old, with_for_update=True)
            reconcile(db, old, client)
        if old.status == "success":
            return payment_out(old)  # it had actually gone through, don't ask them to pay again
        if old.status == "pending":
            old.status, old.result_desc, old.completed_at = "expired", "No response from M-Pesa", now
            db.commit()

    # Insert BEFORE calling Daraja. The partial unique index makes a second simultaneous request fail here.
    payment = Payment(user_id=user.id, plan=data.plan, amount=plan_price(data.plan), phone=data.phone)
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A payment is already in progress. Check your phone for the M-Pesa prompt.")
    db.refresh(payment)

    callback = f"{settings.MPESA_CALLBACK_BASE_URL.rstrip('/')}/api/billing/mpesa/callback/{settings.MPESA_CALLBACK_SECRET}"
    try:
        res = client.stk_push(data.phone, payment.amount, f"KATA-{data.plan.upper()}",
                              f"Kata {PLANS[data.plan]['name']}", callback)
    except MpesaError as e:
        payment.status, payment.result_desc, payment.completed_at = "failed", str(e)[:255], now
        db.commit()
        raise HTTPException(502, "Could not start the M-Pesa prompt. Please try again.")

    payment.checkout_request_id = res["CheckoutRequestID"]
    payment.merchant_request_id = res.get("MerchantRequestID")
    db.commit()
    return payment_out(payment)


@router.get("/payments/{payment_id}")
def payment_status(payment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == user.id).first()
    if payment is None:
        raise HTTPException(404, "Payment not found")

    if payment.status == "pending" and payment.checkout_request_id:
        now = datetime.now(timezone.utc)
        min_age = 3 if settings.MPESA_ENV == "mock" else 20  # give the callback a head start
        old_enough = now - as_utc(payment.created_at) >= timedelta(seconds=min_age)
        last = as_utc(payment.last_query_at)
        throttled = last is not None and now - last < timedelta(seconds=10)
        if old_enough and not throttled:
            try:
                client = get_client()
            except MpesaError:
                return payment_out(payment)
            db.refresh(payment, with_for_update=True)
            reconcile(db, payment, client)
    return payment_out(payment)


@router.post("/mpesa/callback/{secret}", include_in_schema=False)
async def mpesa_callback(secret: str, request: Request, db: Session = Depends(get_db)):
    """Safaricom calls this. It can't send a login token, so the URL itself carries a secret."""
    if not settings.MPESA_CALLBACK_SECRET or not hmac.compare_digest(secret, settings.MPESA_CALLBACK_SECRET):
        raise HTTPException(403, "Forbidden")
    try:
        result = parse_callback(await request.json())
    except Exception:
        log.exception("Unreadable M-Pesa callback")
        return ACK

    payment = (db.query(Payment).filter(Payment.checkout_request_id == result["checkout_id"])
               .with_for_update().first())
    if payment is None:
        log.warning("Callback for unknown checkout id %s", result["checkout_id"])
        return ACK  # still acknowledge, otherwise Safaricom keeps complaining

    try:
        apply_result(db, payment, result["result_code"], result["result_desc"], result["receipt"], result["amount"])
    except Exception:
        db.rollback()
        log.exception("Failed to apply callback for payment %s", payment.id)
    return ACK
