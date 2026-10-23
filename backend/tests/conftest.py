import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = ""  # use in-memory cache/rate limiter
os.environ["MPESA_CALLBACK_SECRET"] = "testsecret"
os.environ["MPESA_CALLBACK_BASE_URL"] = "https://example.test"

import pytest
from fastapi.testclient import TestClient

from app.cache import cache
from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    cache.flush()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    r = client.post("/api/auth/register", json={
        "name": "Test", "email": "t@example.com", "password": "password123", "confirm_password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class FakeDaraja:
    """Stands in for Safaricom so tests never touch the network."""

    def __init__(self):
        self.pushes, self.n = [], 0
        self.fail_push = False
        self.query_result = None  # None = "still processing"

    def stk_push(self, phone, amount, reference, description, callback_url):
        from app.mpesa import MpesaError
        if self.fail_push:
            raise MpesaError("Daraja is down")
        self.n += 1
        self.pushes.append({"phone": phone, "amount": amount, "callback_url": callback_url})
        return {"MerchantRequestID": f"m{self.n}", "CheckoutRequestID": f"ws_CO_{self.n}"}

    def query(self, checkout_id):
        return self.query_result


@pytest.fixture()
def daraja(monkeypatch):
    fake = FakeDaraja()
    monkeypatch.setattr("app.routers.billing.get_client", lambda: fake)
    return fake


@pytest.fixture()
def db():
    from app.database import SessionLocal
    session = SessionLocal()
    yield session
    session.close()
