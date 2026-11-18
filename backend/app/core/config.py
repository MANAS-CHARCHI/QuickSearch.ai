from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vault City AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Database (PostgreSQL + pgvector)
    DATABASE_URL: str = "postgresql+asyncpg://vault_user:vault_secure_password@db:5432/vault_db"
    VECTOR_DIMENSION: int = 384

    # AWS SAM Local Lambda Pipeline & MinIO (Local S3)
    SAM_API_URL: str = "http://host.docker.internal:3001"
    SAM_LAMBDA_ENDPOINT_URL: str = "http://host.docker.internal:3002"
    MINIO_ENDPOINT_URL: str = "http://minio:9000"
    MINIO_BUCKET: str = "vault-uploads"
    
    # Redis Cache, Token Map & Distributed Rate Limiting (pylimitx)
    REDIS_URL: str = "redis://redis:6379/0"
    RATE_LIMIT_FAIL_OPEN: bool = True

    # Security & JWT (5-min Access, 7-day Refresh)
    SECRET_KEY: str = "default_insecure_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 5  # 5 minutes
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days (10080 minutes)

    # HttpOnly Cookie Settings
    COOKIE_ACCESS_NAME: str = "vault_access_token"
    COOKIE_REFRESH_NAME: str = "vault_refresh_token"
    COOKIE_SECURE: bool = False  # Set to True in production (HTTPS)
    COOKIE_SAMESITE: str = "lax"  # 'lax', 'strict', or 'none'
    COOKIE_DOMAIN: Optional[str] = None

    # Google Social Auth
    GOOGLE_CLIENT_ID: Optional[str] = "105470440264-7ep9hin2tddk14jba8agmbddbcl6j12r.apps.googleusercontent.com"

    # Cloudflare Turnstile
    TURNSTILE_ENABLED: bool = True
    TURNSTILE_SITE_KEY: str = "0x4AAAAAAGDGaHDA7lQB_a7O"
    TURNSTILE_SECRET_KEY: str = "0x4AAAAAAGDGaBY2ZuBeRJzSHM3qBN27njY"
    TURNSTILE_VERIFY_URL: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    # SMTP Email Delivery (Gmail STARTTLS default: smtp.gmail.com:587)
    SMTP_ENABLED: bool = True
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "Vault City AI"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_VERIFY_SSL: bool = True  # Keep True in production; set False only for local dev behind antivirus TLS proxies
    SMTP_CA_BUNDLE: Optional[str] = None  # Optional path to custom PEM CA certificate bundle
    FRONTEND_URL: str = "http://localhost:3000"

    # Email Verification OTP Settings
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_RESENDS: int = 5
    OTP_RESEND_WINDOW_SECONDS: int = 3600  # 1 hour window for resend cap
    SMTP_MAX_RETRIES: int = 2
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:80",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
