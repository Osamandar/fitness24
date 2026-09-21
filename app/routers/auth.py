from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_current_user
from ..models import Client, User, now
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut
from ..security import (create_access_token, hash_password, login_limiter,
                        password_is_strong, verify_password)

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    key = data.email.lower()
    if login_limiter.is_locked(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Слишком много неудачных попыток. Повторите через несколько минут")
    user = db.query(User).filter(User.email == key).first()
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        login_limiter.fail(key)
        audit(db, user, "login_failed", key)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    login_limiter.reset(key)
    audit(db, user, "login", key)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Самостоятельная регистрация клиента. Без согласия на обработку ПДн регистрация невозможна."""
    if not data.pd_consent:
        raise HTTPException(400, "Нужно согласие на обработку персональных данных")
    if not password_is_strong(data.password):
        raise HTTPException(400, "Пароль должен быть не короче 8 символов и содержать буквы и цифры")
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Пользователь с таким email уже зарегистрирован")
    user = User(email=email, full_name=data.full_name, password_hash=hash_password(data.password), role="client")
    db.add(user)
    db.flush()
    db.add(Client(user_id=user.id, full_name=data.full_name, phone=data.phone, email=email,
                  pd_consent=True, consent_at=now()))
    audit(db, user, "register", email)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
