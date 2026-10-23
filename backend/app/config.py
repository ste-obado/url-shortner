from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from environment variables / .env (never hard-code secrets)."""

    DATABASE_URL: str = "sqlite:///./kata.db"
    SECRET_KEY: str = "dev-only-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REDIS_URL: str = ""  # empty = use in-memory fallback (fine for local dev)
    BASE_URL: str = "http://localhost:8000"  # what short links start with
    CORS_ORIGINS: str = "http://localhost:5173"
    CACHE_TTL_SECONDS: int = 3600

    # M-Pesa (Daraja). MPESA_ENV: "sandbox" | "production" | "mock" (fake payments for UI demos only)
    MPESA_ENV: str = "sandbox"
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    MPESA_SHORTCODE: str = ""
    MPESA_PASSKEY: str = ""
    MPESA_TRANSACTION_TYPE: str = "CustomerPayBillOnline"  # use CustomerBuyGoodsOnline for a Till number
    MPESA_CALLBACK_BASE_URL: str = ""  # PUBLIC https URL of this API (ngrok in dev)
    MPESA_CALLBACK_SECRET: str = ""    # random string; becomes part of the callback URL

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
