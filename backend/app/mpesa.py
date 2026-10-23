"""Safaricom Daraja (M-Pesa Express / STK Push) client. Synchronous, small, and easy to fake in tests."""
import base64
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings

BASES = {"sandbox": "https://sandbox.safaricom.co.ke", "production": "https://api.safaricom.co.ke"}
EAT = timezone(timedelta(hours=3))  # Daraja timestamps are Nairobi time


class MpesaError(Exception):
    pass


class MpesaNotConfigured(MpesaError):
    pass


def normalize_phone(raw: str) -> str:
    """0712345678 / +254712345678 / 712345678 / 0112345678  ->  254712345678"""
    s = re.sub(r"[\s\-()]", "", raw or "")
    s = s[1:] if s.startswith("+") else s
    if re.fullmatch(r"0[17]\d{8}", s):
        s = "254" + s[1:]
    elif re.fullmatch(r"[17]\d{8}", s):
        s = "254" + s
    if not re.fullmatch(r"254[17]\d{8}", s):
        raise ValueError("Enter your M-Pesa number like 0712345678")
    return s


def parse_callback(body: dict) -> dict:
    """Pull what we need out of Safaricom's nested callback JSON."""
    cb = body["Body"]["stkCallback"]
    items = {i["Name"]: i.get("Value") for i in (cb.get("CallbackMetadata") or {}).get("Item", [])}
    return {
        "checkout_id": cb["CheckoutRequestID"],
        "result_code": int(cb["ResultCode"]),
        "result_desc": cb.get("ResultDesc", ""),
        "receipt": items.get("MpesaReceiptNumber"),
        "amount": items.get("Amount"),
    }


class DarajaClient:
    def __init__(self):
        self.base = BASES.get(settings.MPESA_ENV, BASES["production"])
        self._token, self._token_exp = None, 0.0

    def _auth(self) -> str:
        if self._token and time.time() < self._token_exp:
            return self._token
        try:
            r = httpx.get(f"{self.base}/oauth/v1/generate", params={"grant_type": "client_credentials"},
                          auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET), timeout=20)
            r.raise_for_status()
            self._token = r.json()["access_token"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise MpesaError(f"Could not authenticate with M-Pesa: {e}")
        self._token_exp = time.time() + 3000  # tokens last 3599s
        return self._token

    def _password(self):
        ts = datetime.now(EAT).strftime("%Y%m%d%H%M%S")
        raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{ts}"
        return base64.b64encode(raw.encode()).decode(), ts

    def _post(self, path: str, payload: dict) -> dict:
        try:
            r = httpx.post(f"{self.base}{path}", json=payload, timeout=30,
                           headers={"Authorization": f"Bearer {self._auth()}"})
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise MpesaError(f"M-Pesa request failed: {e}")
        return data

    def stk_push(self, phone: str, amount: int, reference: str, description: str, callback_url: str) -> dict:
        password, ts = self._password()
        data = self._post("/mpesa/stkpush/v1/processrequest", {
            "BusinessShortCode": settings.MPESA_SHORTCODE, "Password": password, "Timestamp": ts,
            "TransactionType": settings.MPESA_TRANSACTION_TYPE, "Amount": amount,
            "PartyA": phone, "PartyB": settings.MPESA_SHORTCODE, "PhoneNumber": phone,
            "CallBackURL": callback_url, "AccountReference": reference[:12], "TransactionDesc": description[:13],
        })
        if str(data.get("ResponseCode")) != "0" or "CheckoutRequestID" not in data:
            raise MpesaError(data.get("errorMessage") or data.get("ResponseDescription") or "M-Pesa rejected the request")
        return data

    def query(self, checkout_id: str) -> dict | None:
        """Ask Daraja what happened. Returns None while the transaction is still being processed."""
        password, ts = self._password()
        data = self._post("/mpesa/stkpushquery/v1/query", {
            "BusinessShortCode": settings.MPESA_SHORTCODE, "Password": password,
            "Timestamp": ts, "CheckoutRequestID": checkout_id,
        })
        if "ResultCode" not in data:  # e.g. errorCode 500.001.1001 = "still being processed"
            return None
        return {"result_code": int(data["ResultCode"]), "result_desc": data.get("ResultDesc", "")}


class MockDaraja:
    """MPESA_ENV=mock only: pretends every payment succeeds. For demoing the UI, never for real money."""

    n = 0

    def stk_push(self, phone, amount, reference, description, callback_url):
        MockDaraja.n += 1
        return {"MerchantRequestID": f"mock-m-{MockDaraja.n}", "CheckoutRequestID": f"mock-c-{time.time_ns()}"}

    def query(self, checkout_id):
        return {"result_code": 0, "result_desc": "Mock payment accepted"}


def get_client():
    if settings.MPESA_ENV == "mock":
        return MockDaraja()
    needed = [settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET, settings.MPESA_SHORTCODE,
              settings.MPESA_PASSKEY, settings.MPESA_CALLBACK_BASE_URL, settings.MPESA_CALLBACK_SECRET]
    if not all(needed):
        raise MpesaNotConfigured("Payments are not configured yet")
    return DarajaClient()
