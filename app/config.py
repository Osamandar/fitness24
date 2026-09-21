"""Настройки приложения. Все секреты берутся из переменных окружения."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./fitness24.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    qr_secret: str = os.getenv("QR_SECRET", "dev-qr-secret-change-me")
    device_key: str = os.getenv("DEVICE_KEY", "dev-turnstile-key")
    token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "60"))
    qr_ttl_seconds: int = int(os.getenv("QR_TTL_SECONDS", "60"))
    # Часы доступа для «дневных» тарифов: с 07:00 до 23:00
    day_open_hour: int = 7
    day_close_hour: int = 23
    # Защита от подбора пароля
    max_login_attempts: int = 5
    lockout_minutes: int = 5


settings = Settings()
