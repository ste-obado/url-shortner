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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
