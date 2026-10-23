"""The only place that decides whether a payment counts. Both the M-Pesa callback and the
status-query fallback go through apply_result(), so the rules can't drift apart."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Payment, User
from .plans import PLAN_DAYS, PLANS, RANK, effective_plan
from .utils import as_utc

log = logging.getLogger(__name__)

FINAL = {"success", "failed", "cancelled", "expired", "review"}


def _grant_plan(user: User, plan: str, now: datetime) -> None:
    current_expiry = as_utc(user.plan_expires_at)
    if user.plan == plan and current_expiry and current_expiry > now:
        user.plan_expires_at = current_expiry + timedelta(days=PLAN_DAYS)  # renewing: add on top, lose no days
    else:
        user.plan, user.plan_expires_at = plan, now + timedelta(days=PLAN_DAYS)


def apply_result(db: Session, payment: Payment, result_code: int, result_desc: str,
                 receipt: str | None = None, amount=None) -> Payment:
    """Idempotent: calling this twice with the same result changes nothing the second time.
    Callers should load `payment` with with_for_update() so two requests can't race."""
    now = datetime.now(timezone.utc)

    if payment.status == "success":
        # Callback replay, or the query fallback already succeeded. Never grant days twice;
        # just record the receipt if the earlier path didn't have it.
        if result_code == 0 and receipt and not payment.mpesa_receipt:
            payment.mpesa_receipt = receipt
            _commit_or_review(db, payment)
        return payment
    if payment.status == "review":
        return payment  # a human decides these

    payment.result_code = result_code
    payment.result_desc = (result_desc or "")[:255]
    payment.completed_at = now

    if result_code != 0:
        payment.status = "cancelled" if result_code == 1032 else "failed"
        db.commit()
        return payment

    # --- Money was taken. From here on, never lose track of it. ---
    if amount is not None and int(round(float(amount))) != payment.amount:
        log.error("Payment %s amount mismatch: expected %s got %s", payment.id, payment.amount, amount)
        payment.status = "review"
        db.commit()
        return payment

    if receipt and db.query(Payment).filter(Payment.mpesa_receipt == receipt, Payment.id != payment.id).first():
        log.error("Payment %s receipt %s already used", payment.id, receipt)
        payment.status = "review"
        db.commit()
        return payment

    user = db.query(User).filter(User.id == payment.user_id).with_for_update().one()
    if RANK[payment.plan] < RANK[effective_plan(user, now)]:
        log.error("Payment %s is for a lower plan than the active one", payment.id)
        payment.status = "review"
        db.commit()
        return payment

    _grant_plan(user, payment.plan, now)
    payment.status = "success"
    payment.mpesa_receipt = receipt
    _commit_or_review(db, payment)
    return payment


def _commit_or_review(db: Session, payment: Payment) -> None:
    try:
        db.commit()
    except IntegrityError:  # receipt unique constraint lost a race
        db.rollback()
        payment = db.get(Payment, payment.id)
        payment.status = "review"
        db.commit()


def reconcile(db: Session, payment: Payment, client) -> Payment:
    """Ask Daraja for the outcome. Needed because Safaricom does NOT retry a missed callback."""
    payment.last_query_at = datetime.now(timezone.utc)
    db.commit()
    try:
        result = client.query(payment.checkout_request_id)
    except Exception:
        log.exception("STK query failed for payment %s", payment.id)
        return payment
    if result is None:
        return payment  # still processing
    db.refresh(payment, with_for_update=True)
    return apply_result(db, payment, result["result_code"], result["result_desc"])


def plan_price(plan: str) -> int:
    return PLANS[plan]["price"]
