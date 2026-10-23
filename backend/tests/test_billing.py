from datetime import datetime, timedelta, timezone

import pytest

from app.models import Payment, User
from app.mpesa import normalize_phone

SECRET = "testsecret"


def checkout(client, auth, plan="pro", phone="0712345678"):
    return client.post("/api/billing/checkout", json={"plan": plan, "phone": phone}, headers=auth)


def callback(client, checkout_id, code=0, amount=500, receipt="NLJ7RT61SV", secret=SECRET):
    cb = {"MerchantRequestID": "m", "CheckoutRequestID": checkout_id, "ResultCode": code,
          "ResultDesc": "The service request is processed successfully." if code == 0 else "Request cancelled by user"}
    if code == 0:
        cb["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": amount}, {"Name": "MpesaReceiptNumber", "Value": receipt},
            {"Name": "TransactionDate", "Value": 20261022120000}, {"Name": "PhoneNumber", "Value": 254712345678}]}
    return client.post(f"/api/billing/mpesa/callback/{secret}", json={"Body": {"stkCallback": cb}})


def billing(client, auth):
    return client.get("/api/billing/me", headers=auth).json()


def make_links(client, auth, n, start=0):
    """Create links directly in the DB path via API but without tripping the 10/min rate limit."""
    from app.cache import cache
    for i in range(n):
        cache.flush()
        assert client.post("/api/links", json={"original_url": f"https://e.com/{start + i}"}, headers=auth).status_code == 201


@pytest.mark.parametrize("raw,expected", [
    ("0712345678", "254712345678"), ("+254712345678", "254712345678"), ("254712345678", "254712345678"),
    ("712345678", "254712345678"), ("0112345678", "254112345678"), ("0712 345 678", "254712345678"),
])
def test_phone_normalising(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "12345", "0812345678", "07123456789", "abcdefghij", "254212345678"])
def test_bad_phones_rejected(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_plans_have_the_right_prices(client):
    plans = {p["id"]: p["price"] for p in client.get("/api/billing/plans").json()}
    assert plans == {"free": 0, "pro": 500, "enterprise": 1000}


def test_checkout_uses_server_price_and_clean_phone(client, auth, daraja):
    # A client that tries to sneak in its own amount is simply ignored
    r = client.post("/api/billing/checkout", json={"plan": "pro", "phone": "0712345678", "amount": 1},
                    headers=auth)
    assert r.status_code == 202 and r.json()["amount"] == 500 and r.json()["status"] == "pending"
    push = daraja.pushes[0]
    assert push["amount"] == 500 and push["phone"] == "254712345678"
    assert push["callback_url"] == f"https://example.test/api/billing/mpesa/callback/{SECRET}"
    assert checkout(client, auth, "enterprise").status_code == 409  # still pending (see below test)


def test_enterprise_costs_1000(client, auth, daraja):
    assert checkout(client, auth, "enterprise").json()["amount"] == 1000


@pytest.mark.parametrize("body", [{"plan": "free", "phone": "0712345678"}, {"plan": "gold", "phone": "0712345678"},
                                  {"plan": "pro", "phone": "123"}, {"plan": "pro"}])
def test_checkout_validation(client, auth, daraja, body):
    assert client.post("/api/billing/checkout", json=body, headers=auth).status_code == 422
    assert daraja.pushes == []  # nothing was sent to M-Pesa


def test_checkout_needs_login(client, daraja):
    assert client.post("/api/billing/checkout", json={"plan": "pro", "phone": "0712345678"}).status_code == 401


def test_successful_payment_activates_plan(client, auth, daraja, db):
    pid = checkout(client, auth).json()["id"]
    assert billing(client, auth)["plan"] == "free"  # nothing yet: STK prompt isn't a payment
    assert callback(client, "ws_CO_1").json()["ResultCode"] == 0
    b = billing(client, auth)
    assert b["plan"] == "pro" and b["link_limit"] == 500
    expiry = datetime.fromisoformat(b["expires_at"].replace("Z", "+00:00"))
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    assert timedelta(days=29, hours=23) < expiry - datetime.now(timezone.utc) <= timedelta(days=30)
    p = client.get(f"/api/billing/payments/{pid}", headers=auth).json()
    assert p["status"] == "success" and p["receipt"] == "NLJ7RT61SV"


def test_callback_replay_does_not_extend_twice(client, auth, daraja, db):
    checkout(client, auth)
    callback(client, "ws_CO_1")
    first = db.query(User).one().plan_expires_at
    for _ in range(3):  # Safaricom (or an attacker who saw the URL) re-sending the same callback
        assert callback(client, "ws_CO_1").status_code == 200
    db.expire_all()
    assert db.query(User).one().plan_expires_at == first
    assert db.query(Payment).count() == 1


def test_cancelled_payment_does_not_activate_and_allows_retry(client, auth, daraja):
    pid = checkout(client, auth).json()["id"]
    callback(client, "ws_CO_1", code=1032)
    assert client.get(f"/api/billing/payments/{pid}", headers=auth).json()["status"] == "cancelled"
    assert billing(client, auth)["plan"] == "free"
    assert checkout(client, auth).status_code == 202  # can try again straight away


@pytest.mark.parametrize("code", [1, 2001, 1037])
def test_other_failures(client, auth, daraja, code):
    pid = checkout(client, auth).json()["id"]
    callback(client, "ws_CO_1", code=code)
    assert client.get(f"/api/billing/payments/{pid}", headers=auth).json()["status"] == "failed"
    assert billing(client, auth)["plan"] == "free"


def test_wrong_callback_secret_is_rejected(client, auth, daraja):
    checkout(client, auth)
    assert callback(client, "ws_CO_1", secret="guess").status_code == 403
    assert billing(client, auth)["plan"] == "free"


def test_wrong_amount_goes_to_review_not_activation(client, auth, daraja):
    pid = checkout(client, auth).json()["id"]
    callback(client, "ws_CO_1", amount=1)  # paid KES 1 for a KES 500 plan
    assert client.get(f"/api/billing/payments/{pid}", headers=auth).json()["status"] == "review"
    assert billing(client, auth)["plan"] == "free"


def test_unknown_checkout_id_is_ignored(client, auth, daraja):
    assert callback(client, "ws_CO_999").json()["ResultCode"] == 0
    assert billing(client, auth)["plan"] == "free"


def test_garbage_callback_does_not_crash(client):
    r = client.post(f"/api/billing/mpesa/callback/{SECRET}", json={"hello": "world"})
    assert r.status_code == 200


def test_same_receipt_cannot_pay_twice(client, auth, daraja, db):
    checkout(client, auth)
    callback(client, "ws_CO_1", receipt="SAMEREC")
    other = client.post("/api/auth/register", json={"name": "O", "email": "o@example.com",
                                                    "password": "password123", "confirm_password": "password123"})
    h = {"Authorization": f"Bearer {other.json()['access_token']}"}
    checkout(client, h)
    callback(client, "ws_CO_2", receipt="SAMEREC")
    assert billing(client, h)["plan"] == "free"
    db.expire_all()
    assert db.query(Payment).filter(Payment.id == 2).one().status == "review"


def test_double_click_sends_only_one_prompt(client, auth, daraja):
    assert checkout(client, auth).status_code == 202
    assert checkout(client, auth).status_code == 409
    assert len(daraja.pushes) == 1


def test_daraja_down_marks_failed_and_allows_retry(client, auth, daraja):
    daraja.fail_push = True
    assert checkout(client, auth).status_code == 502
    daraja.fail_push = False
    assert checkout(client, auth).status_code == 202


def test_payments_not_configured_gives_503(client, auth, monkeypatch):
    from app.mpesa import MpesaNotConfigured

    def boom():
        raise MpesaNotConfigured("x")
    monkeypatch.setattr("app.routers.billing.get_client", boom)
    assert checkout(client, auth).status_code == 503


def test_renewal_adds_days_on_top(client, auth, daraja, db):
    checkout(client, auth); callback(client, "ws_CO_1", receipt="R1")
    first = db.query(User).one().plan_expires_at
    checkout(client, auth); callback(client, "ws_CO_2", receipt="R2")
    db.expire_all()
    gained = db.query(User).one().plan_expires_at - first
    assert timedelta(days=29, hours=23) < gained <= timedelta(days=30, minutes=1)


def test_upgrade_to_enterprise_and_no_downgrade(client, auth, daraja):
    checkout(client, auth); callback(client, "ws_CO_1", receipt="R1")
    checkout(client, auth, "enterprise"); callback(client, "ws_CO_2", amount=1000, receipt="R2")
    b = billing(client, auth)
    assert b["plan"] == "enterprise" and b["link_limit"] is None
    assert checkout(client, auth, "pro").status_code == 409  # can't accidentally buy a lower plan


def test_free_plan_link_limit_and_upgrade_unlocks(client, auth, daraja):
    make_links(client, auth, 10)
    r = client.post("/api/links", json={"original_url": "https://e.com/over"}, headers=auth)
    assert r.status_code == 402 and "Upgrade" in r.json()["detail"]
    assert billing(client, auth)["links_used"] == 10
    checkout(client, auth); callback(client, "ws_CO_1")
    make_links(client, auth, 1, start=100)  # now allowed


def test_expired_plan_falls_back_to_free(client, auth, daraja, db):
    checkout(client, auth); callback(client, "ws_CO_1")
    make_links(client, auth, 11)  # fine on Pro
    user = db.query(User).one()
    user.plan_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    assert billing(client, auth)["plan"] == "free"
    from app.cache import cache
    cache.flush()
    assert client.post("/api/links", json={"original_url": "https://e.com/x"}, headers=auth).status_code == 402


def test_lost_callback_is_recovered_by_query(client, auth, daraja, db):
    pid = checkout(client, auth).json()["id"]
    daraja.query_result = {"result_code": 0, "result_desc": "ok"}
    # too early: we give the real callback a head start
    assert client.get(f"/api/billing/payments/{pid}", headers=auth).json()["status"] == "pending"
    p = db.get(Payment, pid)
    p.created_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    db.commit()
    assert client.get(f"/api/billing/payments/{pid}", headers=auth).json()["status"] == "success"
    assert billing(client, auth)["plan"] == "pro"


def test_query_still_processing_keeps_pending_and_late_callback_fills_receipt(client, auth, daraja, db):
    pid = checkout(client, auth).json()["id"]
    p = db.get(Payment, pid); p.created_at = datetime.now(timezone.utc) - timedelta(seconds=60); db.commit()
    daraja.query_result = None
    assert client.get(f"/api/billing/payments/{pid}", headers=auth).json()["status"] == "pending"
    daraja.query_result = {"result_code": 0, "result_desc": "ok"}
    db.expire_all(); p = db.get(Payment, pid); p.last_query_at = None; db.commit()
    client.get(f"/api/billing/payments/{pid}", headers=auth)  # success via query (no receipt available)
    expiry = db.query(User).one().plan_expires_at
    callback(client, "ws_CO_1", receipt="LATEREC")  # the real callback finally shows up
    db.expire_all()
    assert db.get(Payment, pid).mpesa_receipt == "LATEREC"
    assert db.query(User).one().plan_expires_at == expiry  # and did NOT add a second 30 days


def test_query_failure_marks_failed(client, auth, daraja, db):
    pid = checkout(client, auth).json()["id"]
    p = db.get(Payment, pid); p.created_at = datetime.now(timezone.utc) - timedelta(seconds=60); db.commit()
    daraja.query_result = {"result_code": 1032, "result_desc": "Request cancelled by user"}
    assert client.get(f"/api/billing/payments/{pid}", headers=auth).json()["status"] == "cancelled"


def test_stale_pending_is_checked_before_charging_again(client, auth, daraja, db):
    """User paid, callback was lost, they come back after 6 minutes and press Pay again."""
    pid = checkout(client, auth).json()["id"]
    p = db.get(Payment, pid); p.created_at = datetime.now(timezone.utc) - timedelta(minutes=6); db.commit()
    daraja.query_result = {"result_code": 0, "result_desc": "ok"}
    r = checkout(client, auth)
    assert r.json()["status"] == "success" and r.json()["id"] == pid
    assert len(daraja.pushes) == 1  # no second STK prompt, no double charge
    assert billing(client, auth)["plan"] == "pro"


def test_stale_pending_with_no_answer_expires_and_new_attempt_works(client, auth, daraja, db):
    pid = checkout(client, auth).json()["id"]
    p = db.get(Payment, pid); p.created_at = datetime.now(timezone.utc) - timedelta(minutes=6); db.commit()
    daraja.query_result = None
    assert checkout(client, auth).status_code == 202
    db.expire_all()
    assert db.get(Payment, pid).status == "expired"


def test_late_success_after_expiry_still_activates(client, auth, daraja, db):
    pid = checkout(client, auth).json()["id"]
    p = db.get(Payment, pid); p.created_at = datetime.now(timezone.utc) - timedelta(minutes=6); db.commit()
    daraja.query_result = None
    checkout(client, auth)  # expires the first, starts a second
    callback(client, "ws_CO_1")  # the FIRST one turns out to have been paid after all
    assert billing(client, auth)["plan"] == "pro"


def test_cannot_see_someone_elses_payment(client, auth, daraja):
    pid = checkout(client, auth).json()["id"]
    other = client.post("/api/auth/register", json={"name": "O", "email": "o@example.com",
                                                    "password": "password123", "confirm_password": "password123"})
    h = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get(f"/api/billing/payments/{pid}", headers=h).status_code == 404
