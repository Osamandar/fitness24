"""Механизмы защиты: хеширование паролей, JWT, подписанные QR-коды, ограничение попыток входа."""
import hashlib
import hmac
import re
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def password_is_strong(password: str) -> bool:
    """Минимум 8 символов, есть буквы и цифры, не длиннее 72 байт (ограничение bcrypt)."""
    return 8 <= len(password) and len(password.encode()) <= 72 and bool(re.search(r"[A-Za-zА-Яа-я]", password)) and bool(re.search(r"\d", password))


def create_access_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.token_ttl_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def _qr_signature(message: str) -> str:
    return hmac.new(settings.qr_secret.encode(), message.encode(), hashlib.sha256).hexdigest()[:32]


def make_qr_token(client_id: int, ts: float | None = None) -> str:
    """Одноразовый по времени QR-токен: <id клиента>.<время>.<HMAC-подпись>."""
    message = f"{client_id}.{int(ts if ts is not None else time.time())}"
    return f"{message}.{_qr_signature(message)}"


def verify_qr_token(token: str, now: float | None = None) -> int:
    """Возвращает id клиента или выбрасывает ValueError с причиной отказа."""
    parts = token.strip().split(".")
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError("Неверный формат QR-кода")
    client_id, ts, signature = parts
    if not hmac.compare_digest(signature, _qr_signature(f"{client_id}.{ts}")):
        raise ValueError("Подпись QR-кода недействительна")
    current = now if now is not None else time.time()
    age = current - int(ts)
    if age > settings.qr_ttl_seconds or age < -5:
        raise ValueError("Срок действия QR-кода истёк")
    return int(client_id)


class LoginLimiter:
    """Блокирует вход после N неудачных попыток на заданное время (защита от перебора)."""

    def __init__(self):
        self._fails: dict[str, list] = {}

    def is_locked(self, key: str) -> bool:
        fails, until = self._fails.get(key, [0, 0.0])
        return until > time.time()

    def fail(self, key: str) -> None:
        fails, until = self._fails.get(key, [0, 0.0])
        fails += 1
        if fails >= settings.max_login_attempts:
            self._fails[key] = [0, time.time() + settings.lockout_minutes * 60]
        else:
            self._fails[key] = [fails, until]

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


login_limiter = LoginLimiter()
