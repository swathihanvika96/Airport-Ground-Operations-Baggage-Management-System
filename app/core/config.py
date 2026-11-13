"""Application settings loaded from environment variables / .env file."""
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    PROJECT_NAME: str = "Airport Ground Operations & Baggage Management System"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]

    # --- Database (MySQL via PyMySQL) ---
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "airport"
    MYSQL_PASSWORD: str = "airport"
    MYSQL_DB: str = "airport_ground_ops"
    DATABASE_URL: str | None = None  # full override, e.g. sqlite:///./dev.db for quick local runs
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    AUTO_CREATE_TABLES: bool = False  # use Alembic in real deployments

    # --- Security / JWT ---
    SECRET_KEY: str = "change-this-secret-key-in-production-please-32+chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    REGISTRATION_REQUIRES_APPROVAL: bool = False
    EXPOSE_RESET_TOKEN: bool = True  # dev only: return reset token in API response (no email service)

    # --- First super admin (created at startup) ---
    FIRST_SUPERUSER_EMAIL: str = "admin@airportops.com"
    FIRST_SUPERUSER_PASSWORD: str = "Admin@12345"
    FIRST_SUPERUSER_NAME: str = "Super Admin"

    # --- OAuth2 social login (Google) - optional ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"
    OAUTH_DEFAULT_ROLE: str = "CHECKIN_AGENT"

    # --- Optional ---
    REDIS_URL: str | None = None
    REPORTS_DIR: str = "generated_reports"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{quote_plus(self.MYSQL_PASSWORD)}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
