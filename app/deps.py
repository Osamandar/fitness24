"""Зависимости FastAPI: текущий пользователь, проверка ролей, аудит."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLog, Client, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется вход в систему")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия недействительна, войдите заново")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Учётная запись недоступна")
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостаточно прав для этого действия")
        return user
    return checker


def get_client_of(user: User, db: Session) -> Client:
    client = db.query(Client).filter(Client.user_id == user.id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Карточка клиента не найдена")
    return client


def audit(db: Session, user: User | None, action: str, details: str = "") -> None:
    db.add(AuditLog(user_id=user.id if user else None, action=action, details=details))
